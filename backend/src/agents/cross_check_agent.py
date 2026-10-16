"""
Cross-Check Agent.

Checks the parsed prescription against a structured drug-drug and
drug-diagnosis interaction knowledge base, rather than relying on an LLM
to recall interactions from memory. This mirrors the Rx Strategist
approach: offloading factual interaction checks to a structured knowledge
source is both more auditable and cheaper than a large general-purpose
LLM call for the same check.

Loads TWO sources and merges them:
  - data/interactions.json: the small, hand-curated set covering the
    drugs with full local guideline documents.
  - data/interactions_ddinter.json: real interaction data ingested from
    DDInter 2.0 (see scripts/ingest_ddinter.py), if that file exists.
    This is how coverage scales beyond hand-writing individual rules --
    the second file is generated from a real, pharmacist-curated database
    rather than authored one entry at a time.
Both files use the identical schema, so merging is a simple concatenation.
"""

import json
from pathlib import Path
from typing import Dict, Any, List

from src.config import INTERACTIONS_FILE, DATA_DIR
from src.state import VerifierState

DDINTER_FILE = DATA_DIR / "interactions_ddinter.json"


def _load_interactions() -> Dict[str, list]:
    with open(INTERACTIONS_FILE, encoding="utf-8") as f:
        merged = json.load(f)

    if DDINTER_FILE.exists():
        with open(DDINTER_FILE, encoding="utf-8") as f:
            ddinter_data = json.load(f)
        merged["drug_drug"] = merged.get("drug_drug", []) + ddinter_data.get("drug_drug", [])
        merged["drug_diagnosis"] = merged.get("drug_diagnosis", []) + ddinter_data.get("drug_diagnosis", [])

    return merged


_INTERACTIONS = _load_interactions()


def _check_drug_drug(drug_names: List[str]) -> List[Dict[str, Any]]:
    flags = []
    drug_set = set(drug_names)
    for rule in _INTERACTIONS["drug_drug"]:
        if set(rule["drugs"]).issubset(drug_set):
            flags.append(rule)
    return flags


def _check_drug_diagnosis(drug_names: List[str], diagnoses: List[str]) -> List[Dict[str, Any]]:
    """Checks every parsed drug against EVERY parsed diagnosis, not just
    one -- a prescription commonly treats more than one condition at once
    (e.g. hypertension AND type 2 diabetes), and a contraindication
    against the second-listed diagnosis is just as real as one against
    the first."""
    flags = []
    for rule in _INTERACTIONS["drug_diagnosis"]:
        if rule["drug"] not in drug_names:
            continue
        for diagnosis in diagnoses:
            if rule["diagnosis"] in diagnosis:
                flags.append(rule)
                break  # one flag per rule, even if it matches >1 diagnosis phrase
    return flags


def cross_check(state: VerifierState) -> Dict[str, Any]:
    """LangGraph node: flags drug-drug and drug-diagnosis interaction issues."""
    drug_names = [d["name"] for d in state.get("parsed_drugs", [])]
    diagnoses = state.get("parsed_diagnoses", [])

    return {
        "drug_drug_flags": _check_drug_drug(drug_names),
        "drug_diagnosis_flags": _check_drug_diagnosis(drug_names, diagnoses),
    }
