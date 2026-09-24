"""
Missing-Test Detector Agent.

Checks each prescribed drug against a monitoring-requirement table
(data/monitoring_requirements.json) and flags any required baseline or
periodic test that the clinician has not indicated as already ordered.
"""

import json
from typing import Dict, Any, List

from src.config import MONITORING_FILE
from src.state import VerifierState

with open(MONITORING_FILE, encoding="utf-8") as f:
    _MONITORING = json.load(f)


def detect_missing_tests(state: VerifierState) -> Dict[str, Any]:
    """LangGraph node: flags required tests not present in ordered_tests."""
    drug_names = [d["name"] for d in state.get("parsed_drugs", [])]
    ordered = {t.lower() for t in state.get("ordered_tests", [])}

    missing = []
    for drug in drug_names:
        for requirement in _MONITORING.get(drug, []):
            test_name = requirement["test"]
            # Match loosely: if any ordered test name is a substring match
            # (e.g. "eGFR" covers "eGFR / Serum Creatinine"), treat as covered.
            covered = any(
                ordered_test in test_name.lower() or test_name.lower() in ordered_test
                for ordered_test in ordered
            )
            if not covered:
                missing.append({"drug": drug, **requirement})

    return {"missing_tests": missing}
