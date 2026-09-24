"""
Lightweight sanity tests (no pytest dependency needed -- run directly with
`python tests/test_pipeline.py` from the project root, or `pytest` if you
have it installed).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.graph import run_pipeline


def test_clean_case_has_no_violations():
    result = run_pipeline(
        raw_text="Prescribe Lisinopril 10mg oral once daily for hypertension.",
        diagnosis_hint="hypertension",
        ordered_tests=["Serum Creatinine", "Serum Potassium"],
    )
    assert result["violations"] == [], f"Expected no violations, got {result['violations']}"
    print("PASS: clean case has no violations")


def test_missing_test_is_flagged():
    result = run_pipeline(
        raw_text="Prescribe Metformin 500mg oral twice daily for type 2 diabetes.",
        diagnosis_hint="type 2 diabetes",
        ordered_tests=[],
    )
    types = [v["type"] for v in result["violations"]]
    assert "missing monitoring test" in types, f"Expected a missing-test flag, got {types}"
    print("PASS: missing test correctly flagged")


def test_drug_drug_interaction_is_flagged():
    result = run_pipeline(
        raw_text="Patient on Warfarin 5mg oral once daily is additionally prescribed Ibuprofen 400mg oral three times daily.",
        diagnosis_hint="atrial fibrillation",
        ordered_tests=["INR"],
    )
    types = [v["type"] for v in result["violations"]]
    assert "drug-drug interaction" in types, f"Expected a drug-drug interaction flag, got {types}"
    print("PASS: drug-drug interaction correctly flagged")


def test_drug_diagnosis_contraindication_is_flagged():
    result = run_pipeline(
        raw_text="Prescribe Metformin 500mg oral twice daily for type 2 diabetes.",
        diagnosis_hint="renal impairment",
        ordered_tests=["eGFR"],
    )
    types = [v["type"] for v in result["violations"]]
    assert "drug-diagnosis contraindication" in types, f"Expected a contraindication flag, got {types}"
    print("PASS: drug-diagnosis contraindication correctly flagged")


def test_retrieval_returns_citation():
    result = run_pipeline(
        raw_text="Prescribe Warfarin 5mg oral once daily.",
        diagnosis_hint="atrial fibrillation",
        ordered_tests=["INR"],
    )
    assert result["retrieved_chunks"], "Expected at least one retrieved chunk"
    assert result["retrieved_chunks"][0]["source"], "Expected retrieved chunk to carry a source citation"
    print("PASS: retrieval returns a cited chunk")


if __name__ == "__main__":
    test_clean_case_has_no_violations()
    test_missing_test_is_flagged()
    test_drug_drug_interaction_is_flagged()
    test_drug_diagnosis_contraindication_is_flagged()
    test_retrieval_returns_citation()
    print("\nAll sanity tests passed.")
