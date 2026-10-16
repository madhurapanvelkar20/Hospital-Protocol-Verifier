"""Regression tests for typed prescription text flowing into verification."""
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.explanation_agent import explain_violations
from src.agents.missing_test_agent import (
    _MONITORING,
    _normalize_test_name,
    detect_missing_tests,
)
from src.prescription_extract import extract_structured_fields


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"raw_text": " \n\t", "ordered_tests": []}, 422),
        ({"ordered_tests": []}, 422),
        ({"raw_text": "synthetic prescription", "ordered_tests": "not-an-array"}, 422),
    ],
)
def test_verify_rejects_blank_or_malformed_requests_before_pipeline(
    monkeypatch, payload, expected_status
):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    main = importlib.import_module("main")
    monkeypatch.setitem(
        main.app.dependency_overrides,
        main.get_current_user,
        lambda: SimpleNamespace(id=1, email="test@example.invalid"),
    )
    monkeypatch.setitem(main.app.dependency_overrides, main.get_db, lambda: object())

    def fail_if_pipeline_runs(*_args):
        pytest.fail("Invalid verification input must not enter the pipeline")

    monkeypatch.setattr(main, "run_pipeline", fail_if_pipeline_runs)

    with TestClient(main.app) as client:
        response = client.post("/api/verify", json=payload)

    assert response.status_code == expected_status
    if "raw_text" in payload and not payload["raw_text"].strip():
        assert response.json()["detail"] == "Prescription text cannot be empty."


def test_verify_route_passes_extracted_and_explicit_tests_to_pipeline(
    monkeypatch,
):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    main = importlib.import_module("main")
    captured = {}
    raw_text = (
        "Continue lisinopril 10 mg once daily.\n\n"
        "Investigations advised:\n\n"
        "Serum Creatinine\n\n"
        "Serum Potassium"
    )
    request_payload = {
        "raw_text": raw_text,
        "diagnosis_hint": None,
        "ordered_tests": [],
    }
    extracted_tests = extract_structured_fields(raw_text)["ordered_tests"]
    required_components = _MONITORING["lisinopril"][0]["required_components"]
    detected_components = [
        _normalize_test_name(test) for test in extracted_tests
    ]

    def actual_rule_pipeline(_raw_text, _diagnosis_hint, ordered_tests):
        captured["raw_text"] = _raw_text
        captured["diagnosis_hint"] = _diagnosis_hint
        captured["ordered_tests"] = ordered_tests
        matching_state = {
            "parsed_drugs": [{"name": "lisinopril"}],
            "ordered_tests": ordered_tests,
        }
        matched = detect_missing_tests(matching_state)
        explained = explain_violations({
            **matching_state,
            **matched,
            "parser_warnings": [],
            "retrieval_warnings": [],
            "drug_drug_flags": [],
            "drug_diagnosis_flags": [],
            "retrieved_chunks": [],
        })
        return {**matched, **explained}

    def capture_save_call(*args):
        captured["save_args"] = args

    monkeypatch.setattr(main, "run_pipeline", actual_rule_pipeline)
    monkeypatch.setattr(main, "save_verification", capture_save_call)

    result = main.verify(
        main.VerifyRequest(**request_payload),
        user=SimpleNamespace(id=1),
        db=object(),
    )

    print("Verification diagnostic:")
    print(json.dumps({
        "request_payload": request_payload,
        "extracted_ordered_tests": extracted_tests,
        "normalized_required_components": [
            [_normalize_test_name(alias) for alias in aliases]
            for aliases in required_components
        ],
        "normalized_detected_components": detected_components,
        "final_missing_components": [
            finding.get("missing_components", [])
            for finding in result["missing_tests"]
        ],
    }, indent=2))

    assert captured["raw_text"] == raw_text
    assert captured["diagnosis_hint"] == ""
    assert captured["ordered_tests"] == extracted_tests
    assert captured["ordered_tests"] == ["Serum Creatinine", "Serum Potassium"]
    assert captured["save_args"][2] == raw_text
    assert result["missing_tests"] == []
    assert not any(
        violation["type"] == "missing monitoring test"
        for violation in result["violations"]
    )

    separate_field_payload = {
        "raw_text": (
            "Continue lisinopril 10 mg once daily.\n\n"
            "Investigations advised:\n\n"
            "Serum Creatinine"
        ),
        "diagnosis_hint": None,
        "ordered_tests": ["Serum Potassium"],
    }
    merged_result = main.verify(
        main.VerifyRequest(**separate_field_payload),
        user=SimpleNamespace(id=1),
        db=object(),
    )

    assert captured["ordered_tests"] == ["Serum Potassium", "Serum Creatinine"]
    assert merged_result["missing_tests"] == []
