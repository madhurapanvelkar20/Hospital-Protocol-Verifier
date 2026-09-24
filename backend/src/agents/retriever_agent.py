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

from src.config import RETRIEVAL_CONFIDENCE_THRESHOLD, LIVE_FDA_RETRIEVAL_ENABLED
from src.state import VerifierState
from src.vector_store import get_retriever
from src.live_data import fetch_fda_label_chunks


def _build_query(state: VerifierState) -> str:
    drugs = [d["name"] for d in state.get("parsed_drugs", [])]
    diagnosis = state.get("parsed_diagnosis") or ""
    return f"{diagnosis} treatment with {', '.join(drugs)}".strip()


def _reformulate_query(original_query: str, state: VerifierState) -> str:
    # Broaden the query by dropping the diagnosis and querying on drug names
    # alone -- a simple but effective reformulation when the narrow query
    # (drug + diagnosis together) doesn't match any single guideline well.
    drugs = [d["name"] for d in state.get("parsed_drugs", [])]
    return " ".join(drugs) if drugs else original_query


def _fetch_live_chunks(state: VerifierState) -> list:
    """Queries the live openFDA label API for each parsed drug. Never raises
    -- any failure (network, rate limit, drug not found) just yields no
    live chunks for that drug, and the local corpus results still stand."""
    chunks = []
    for drug in state.get("parsed_drugs", []):
        chunks.extend(fetch_fda_label_chunks(drug["name"]))
    return chunks


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
    results = retriever.query(query)
    confidence = results[0]["score"] if results else 0.0
    attempts = 1

    if confidence < RETRIEVAL_CONFIDENCE_THRESHOLD:
        # Self-correction loop: reformulate and re-query once.
        reformulated = _reformulate_query(query, state)
        retry_results = retriever.query(reformulated)
        retry_confidence = retry_results[0]["score"] if retry_results else 0.0
        attempts = 2
        if retry_confidence > confidence:
            query, results, confidence = reformulated, retry_results, retry_confidence

    live_chunks = _fetch_live_chunks(state) if LIVE_FDA_RETRIEVAL_ENABLED else []
    if live_chunks:
        results = live_chunks + results
        confidence = 1.0

    return {
        "retrieval_query": query,
        "retrieved_chunks": results,
        "retrieval_confidence": confidence,
        "retrieval_attempts": attempts,
    }
