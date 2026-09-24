"""
Cross-Check Agent.

Checks the parsed prescription against a structured drug-drug and
drug-diagnosis interaction knowledge graph (data/interactions.json), rather
than relying on an LLM to recall interactions from memory. This mirrors the
Rx Strategist approach: offloading factual interaction checks to a
structured knowledge source is both more auditable and cheaper than a large
general-purpose LLM call for the same check.
"""

import json
from itertools import combinations
from typing import Dict, Any, List

from src.config import INTERACTIONS_FILE
from src.state import VerifierState

with open(INTERACTIONS_FILE, encoding="utf-8") as f:
    _INTERACTIONS = json.load(f)


def _check_drug_drug(drug_names: List[str]) -> List[Dict[str, Any]]:
    flags = []
    drug_set = set(drug_names)
    for rule in _INTERACTIONS["drug_drug"]:
        if set(rule["drugs"]).issubset(drug_set):
            flags.append(rule)
    return flags


def _check_drug_diagnosis(drug_names: List[str], diagnosis: str) -> List[Dict[str, Any]]:
    flags = []
    if not diagnosis:
        return flags
    for rule in _INTERACTIONS["drug_diagnosis"]:
        if rule["drug"] in drug_names and rule["diagnosis"] in diagnosis:
            flags.append(rule)
    return flags


def cross_check(state: VerifierState) -> Dict[str, Any]:
    """LangGraph node: flags drug-drug and drug-diagnosis interaction issues."""
    drug_names = [d["name"] for d in state.get("parsed_drugs", [])]
    diagnosis = state.get("parsed_diagnosis") or ""

    return {
        "drug_drug_flags": _check_drug_drug(drug_names),
        "drug_diagnosis_flags": _check_drug_diagnosis(drug_names, diagnosis),
    }
