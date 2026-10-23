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
from pathlib import Path
import re
from typing import Dict, Any, List

from src.config import INTERACTIONS_FILE, MONITORING_FILE, KNOWN_DRUGS, KNOWN_DIAGNOSES
from src.state import VerifierState

with open(INTERACTIONS_FILE, encoding="utf-8") as f:
    _INTERACTIONS = json.load(f)

with open(MONITORING_FILE, encoding="utf-8") as f:
    _MONITORING = json.load(f)

_RULED_DRUGS = {
    drug
    for rule in _INTERACTIONS["drug_drug"]
    for drug in rule["drugs"]
} | {
    rule["drug"] for rule in _INTERACTIONS["drug_diagnosis"]
} | set(_MONITORING)


def _check_drug_drug(drug_names: List[str]) -> List[Dict[str, Any]]:
    flags = []
    drug_set = set(drug_names)
    for rule in _INTERACTIONS["drug_drug"]:
        if set(rule["drugs"]).issubset(drug_set):
            flags.append(rule)
    return flags


def _check_drug_diagnosis(drug_names: List[str], diagnoses: List[str]) -> List[Dict[str, Any]]:
    flags = []
    diagnosis_set = {diagnosis.casefold().strip() for diagnosis in diagnoses}
    for rule in _INTERACTIONS["drug_diagnosis"]:
        if rule["drug"] in drug_names and rule["diagnosis"].casefold() in diagnosis_set:
            flags.append(rule)
    return flags


def _diagnoses_from_state(state: VerifierState) -> List[str]:
    diagnoses = state.get("parsed_diagnoses")
    if diagnoses is not None:
        return [diagnosis.strip().casefold() for diagnosis in diagnoses if diagnosis.strip()]
    diagnosis = state.get("parsed_diagnosis") or ""
    return [item.strip().casefold() for item in re.split(r"[;,]", diagnosis) if item.strip()]


def cross_check(state: VerifierState) -> Dict[str, Any]:
    """LangGraph node: flags drug-drug and drug-diagnosis interaction issues."""
    drugs = state.get("parsed_drugs", [])
    drug_names = [drug["name"].casefold() for drug in drugs]
    diagnoses = _diagnoses_from_state(state)
    recognized_diagnoses = {diagnosis.casefold() for diagnosis in KNOWN_DIAGNOSES}

    return {
        "drug_drug_flags": _check_drug_drug(drug_names),
        "drug_diagnosis_flags": _check_drug_diagnosis(drug_names, diagnoses),
        "unassessed_drugs": [
            drug["name"]
            for drug in drugs
            if drug.get("recognized") is False or drug["name"].casefold() not in _RULED_DRUGS
        ],
        "unassessed_diagnoses": [
            diagnosis for diagnosis in diagnoses if diagnosis not in recognized_diagnoses
        ],
    }
