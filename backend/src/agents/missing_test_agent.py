"""
Missing-Test Detector Agent.

Checks each prescribed drug against a monitoring-requirement table
(data/monitoring_requirements.json) and flags any required baseline or
periodic test that the clinician has not indicated as already ordered.
"""

import json
import re
from typing import Dict, Any, List

from src.config import MONITORING_FILE
from src.state import VerifierState

with open(MONITORING_FILE, encoding="utf-8") as f:
    _MONITORING = json.load(f)


def _normalize_test_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _component_specs(requirement: str):
    """Return independent required components and explicitly supported labels."""
    normalized = _normalize_test_name(requirement)
    combined_requirement = (requirement,)

    if normalized == "egfr serum creatinine":
        return [("eGFR / Serum Creatinine", ("eGFR", "Serum Creatinine", *combined_requirement))]
    if normalized == "serum creatinine potassium":
        return [
            ("Serum Creatinine", ("Serum Creatinine", *combined_requirement)),
            ("Potassium", ("Potassium", "Serum Potassium", *combined_requirement)),
        ]
    if normalized == "serum electrolytes potassium sodium renal function":
        electrolyte_panel = "Serum Electrolytes (Potassium, Sodium)"
        return [
            ("Potassium", ("Potassium", "Serum Potassium", electrolyte_panel, *combined_requirement)),
            ("Sodium", ("Sodium", electrolyte_panel, *combined_requirement)),
            ("Renal Function", ("Renal Function", *combined_requirement)),
        ]
    if normalized == "serum digoxin level potassium renal function":
        return [
            ("Serum Digoxin Level", ("Serum Digoxin Level", *combined_requirement)),
            ("Potassium", ("Potassium", "Serum Potassium", *combined_requirement)),
            ("Renal Function", ("Renal Function", *combined_requirement)),
        ]
    if normalized == "blood glucose blood pressure":
        return [
            ("Blood Glucose", ("Blood Glucose", *combined_requirement)),
            ("Blood Pressure", ("Blood Pressure", *combined_requirement)),
        ]

    parts = [part.strip() for part in re.split(r"\s*(?:&|,)\s*", requirement) if part.strip()]
    return [(part, (part,)) for part in parts]


def detect_missing_tests(state: VerifierState) -> Dict[str, Any]:
    """LangGraph node: flags required tests not present in ordered_tests."""
    drug_names = [d["name"] for d in state.get("parsed_drugs", [])]
    ordered = {_normalize_test_name(test) for test in state.get("ordered_tests", [])}

    missing = []
    for drug in drug_names:
        for requirement in _MONITORING.get(drug, []):
            for component, accepted_names in _component_specs(requirement["test"]):
                accepted = {_normalize_test_name(name) for name in accepted_names}
                if not ordered.intersection(accepted):
                    missing.append({
                        "drug": drug,
                        **{key: value for key, value in requirement.items() if key != "test"},
                        "test": component,
                        "requirement": requirement["test"],
                    })

    return {"missing_tests": missing}
