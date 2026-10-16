"""
Retriever Agent.

Builds a retrieval query from the parsed prescription (drug names + working
diagnosis), queries the protocol corpus, and reports a confidence score.

Implements the "self-correction" behaviour from the synopsis: if the top
result's confidence is below RETRIEVAL_CONFIDENCE_THRESHOLD, the query is
reformulated (broadened) and re-queried once before handing off downstream,
which is what should reduce false negatives from an overly narrow query.
"""

from typing import Dict, Any
import re

from src.config import (
    KNOWN_DRUGS,
    LIVE_FDA_RETRIEVAL_ENABLED,
    RETRIEVAL_CONFIDENCE_THRESHOLD,
    TOP_K_CHUNKS,
)
from src.state import VerifierState
from src.vector_store import get_retriever
from src.live_data import fetch_fda_label_chunks_with_status


def _local_protocol_chunks_for_prescription(
    chunks: list,
    parsed_drugs: list,
) -> list:
    """Exclude local drug-specific protocols for drugs not prescribed."""
    prescribed = {
        re.sub(r"\s+", " ", str(drug.get("name", "")).strip().lower())
        for drug in parsed_drugs
    }
    results = []
    for chunk in chunks:
        title = str(chunk.get("title", "")).lower()
        title_drugs = {
            drug
            for drug in KNOWN_DRUGS
            if re.search(rf"(?<![a-z0-9]){re.escape(drug)}(?![a-z0-9])", title)
        }
        if title_drugs and not title_drugs.intersection(prescribed):
            continue
        results.append(chunk)
    return results


def _build_query(state: VerifierState) -> str:
    drugs = [
        d["name"]
        for d in state.get("parsed_drugs", [])
        if d.get("recognition_status") != "unsupported"
    ]
    diagnoses = state.get("parsed_diagnoses", [])
    return f"{', '.join(diagnoses)} treatment with {', '.join(drugs)}".strip()


def _reformulate_query(original_query: str, state: VerifierState) -> str:
    # Broaden the query by dropping the diagnosis and querying on drug names
    # alone -- a simple but effective reformulation when the narrow query
    # (drug + diagnosis together) doesn't match any single guideline well.
    drugs = [d["name"] for d in state.get("parsed_drugs", [])]
    return " ".join(drugs) if drugs else original_query


def _fetch_live_chunks_with_warnings(state: VerifierState) -> tuple[list, list]:
    chunks = []
    warnings = []
    for drug in state.get("parsed_drugs", []):
        drug_chunks, status = fetch_fda_label_chunks_with_status(drug["name"])
        chunks.extend(drug_chunks)
        if status == "unavailable":
            warnings.append({
                "type": "external_data_unavailable",
                "drug": drug["name"],
                "message": (
                    f"The live FDA label lookup for {drug['name']} could not be "
                    "completed. This is a temporary external-data failure; it "
                    "does not establish that the drug is unsupported or safe."
                ),
            })
        elif status == "no_match":
            warnings.append({
                "type": "external_data_no_match",
                "drug": drug["name"],
                "message": (
                    f"No matching live FDA label was returned for {drug['name']}. "
                    "This does not establish that the drug is unsupported or safe."
                ),
            })
    return chunks, warnings


def retrieve_protocol(state: VerifierState) -> Dict[str, Any]:
    """LangGraph node: retrieves relevant protocol chunks for the prescription.

    Always queries the local curated corpus first (self-correcting if
    confidence is low). If LIVE_FDA_RETRIEVAL_ENABLED, also queries the
    live openFDA label API per drug and merges any results in ahead of the
    local ones -- a matched live label is treated as a direct hit rather
    than ranked against the local corpus's similarity scores, since it's
    an exact drug-name match rather than a semantic/keyword guess.
    """
    retriever = get_retriever()
    query = _build_query(state)
    parsed_drugs = state.get("parsed_drugs", [])
    results = _local_protocol_chunks_for_prescription(
        retriever.query(query, top_k=TOP_K_CHUNKS * 3),
        parsed_drugs,
    )[:TOP_K_CHUNKS]
    confidence = results[0]["score"] if results else 0.0
    attempts = 1

    if confidence < RETRIEVAL_CONFIDENCE_THRESHOLD:
        # Self-correction loop: reformulate and re-query once.
        reformulated = _reformulate_query(query, state)
        retry_results = _local_protocol_chunks_for_prescription(
            retriever.query(reformulated, top_k=TOP_K_CHUNKS * 3),
            parsed_drugs,
        )[:TOP_K_CHUNKS]
        retry_confidence = retry_results[0]["score"] if retry_results else 0.0
        attempts = 2
        if retry_confidence > confidence:
            query, results, confidence = reformulated, retry_results, retry_confidence

    if LIVE_FDA_RETRIEVAL_ENABLED:
        live_chunks, retrieval_warnings = _fetch_live_chunks_with_warnings(state)
    else:
        live_chunks, retrieval_warnings = [], []
    if live_chunks:
        results = live_chunks + results
        confidence = 1.0

    return {
        "retrieval_query": query,
        "retrieved_chunks": results,
        "retrieval_confidence": confidence,
        "retrieval_attempts": attempts,
        "retrieval_warnings": retrieval_warnings,
    }
