"""Regressions for supported medication, monitoring, and assessment behavior."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.config as config

config.EMBEDDING_BACKEND = "tfidf"

from src.agents.missing_test_agent import detect_missing_tests
from src.agents.parser_agent import parse_prescription
from src.agents.retriever_agent import retrieve_protocol
from src.graph import run_pipeline


def _parsed_drugs(text):
    return parse_prescription({"raw_text": text})["parsed_drugs"]


def test_reference_medicine_vocabulary_matches_all_18_names_without_duplicates():
    expected = {
        "lisinopril", "metformin", "warfarin", "methotrexate", "simvastatin",
        "furosemide", "ibuprofen", "amoxicillin", "digoxin", "levothyroxine",
        "omeprazole", "clopidogrel", "insulin", "losartan", "prednisone",
        "amlodipine", "telmisartan", "atorvastatin",
    }
    assert len(config.KNOWN_DRUGS) == 18
    assert len(config.KNOWN_DRUGS) == len(set(config.KNOWN_DRUGS))
    assert set(config.KNOWN_DRUGS) == expected


def test_atorvastatin_is_recognized_with_supplied_details():
    drug, = _parsed_drugs("Atorvastatin 20 mg oral once daily")
    assert drug == {
        "name": "atorvastatin",
        "dose": "20 mg",
        "route": "oral",
        "frequency": "once daily",
        "recognized": True,
    }


def test_atorvastatin_retrieves_the_configured_statin_guideline():
    state = parse_prescription({
        "raw_text": "Atorvastatin 20 mg oral once daily",
        "diagnosis_hint": "Hyperlipidemia",
    })
    state["raw_text"] = "Atorvastatin 20 mg oral once daily"
    result = retrieve_protocol(state)
    assert result["retrieved_chunks"]
    assert result["retrieved_chunks"][0]["title"] == "Statin Therapy for Lipid Management Guideline"


def test_lisinopril_and_mult_word_potassium_supplement_are_preserved():
    drugs = _parsed_drugs(
        "Lisinopril — 10 mg, oral, once daily\n"
        "Potassium chloride supplement — 10 mEq, oral, once daily"
    )
    assert [drug["name"] for drug in drugs] == [
        "lisinopril",
        "potassium chloride supplement",
    ]
    assert drugs[0]["dose"] == "10 mg"
    assert drugs[1]["dose"] == "10 mEq"
    assert all(drug["route"] == "oral" for drug in drugs)
    assert all(drug["frequency"] == "once daily" for drug in drugs)
    assert drugs[1]["recognized"] is False


def test_api_preserves_lisinopril_and_potassium_chloride_and_only_flags_missing_component(monkeypatch):
    from types import SimpleNamespace

    import main
    from fastapi.testclient import TestClient

    user = SimpleNamespace(id=1, email="testdoctor@hospital.org", display_name="Dr. Test")
    monkeypatch.setitem(main.app.dependency_overrides, main.get_current_user, lambda: user)
    monkeypatch.setattr(main, "save_verification", lambda *args, **kwargs: None)
    with TestClient(main.app) as api_client:
        response = api_client.post("/api/verify", json={
            "raw_text": (
                "Lisinopril — 10 mg, oral, once daily\n"
                "Potassium chloride supplement — 10 mEq, oral, once daily"
            ),
            "diagnosis_hint": "Hypertension",
            "ordered_tests": ["Serum Potassium"],
        })

    assert response.status_code == 200, response.text
    data = response.json()
    assert [drug["name"] for drug in data["parsed_drugs"]] == [
        "lisinopril",
        "potassium chloride supplement",
    ]
    assert data["unassessed_drugs"] == ["potassium chloride supplement"]
    missing = [
        finding for finding in data["violations"]
        if finding["type"] == "missing monitoring test"
    ]
    assert len(missing) == 1
    assert "Serum Creatinine" in missing[0]["description"]
    assert not any(finding["type"] == "drug-drug interaction" for finding in data["violations"])


@pytest.mark.parametrize(
    ("ordered", "missing"),
    [
        ([], {"Serum Creatinine", "Potassium"}),
        (["Serum Potassium"], {"Serum Creatinine"}),
        (["serum.potassium!"], {"Serum Creatinine"}),
        (["Serum Creatinine"], {"Potassium"}),
        (["Serum Creatinine", "Potassium"], set()),
        (["Lipid Profile"], {"Serum Creatinine", "Potassium"}),
    ],
)
def test_lisinopril_monitoring_components_are_matched_independently(ordered, missing):
    result = detect_missing_tests({
        "parsed_drugs": [{"name": "lisinopril"}],
        "ordered_tests": ordered,
    })
    assert {item["test"] for item in result["missing_tests"]} == missing


def test_egfr_is_an_explicit_alternative_for_the_metformin_requirement():
    result = detect_missing_tests({
        "parsed_drugs": [{"name": "metformin"}],
        "ordered_tests": ["eGFR"],
    })
    assert result["missing_tests"] == []


def test_digoxin_and_furosemide_multi_component_monitoring():
    digoxin = detect_missing_tests({
        "parsed_drugs": [{"name": "digoxin"}],
        "ordered_tests": ["Serum Digoxin Level"],
    })
    assert {item["test"] for item in digoxin["missing_tests"]} == {
        "Potassium",
        "Renal Function",
    }

    furosemide = detect_missing_tests({
        "parsed_drugs": [{"name": "furosemide"}],
        "ordered_tests": ["Serum Potassium"],
    })
    assert {item["test"] for item in furosemide["missing_tests"]} == {
        "Sodium",
        "Renal Function",
    }

    complete_panel = detect_missing_tests({
        "parsed_drugs": [{"name": "furosemide"}],
        "ordered_tests": ["Serum Electrolytes (Potassium, Sodium)", "Renal Function"],
    })
    assert complete_panel["missing_tests"] == []


def test_prednisone_components_are_not_satisfied_by_a_partial_match():
    result = detect_missing_tests({
        "parsed_drugs": [{"name": "prednisone"}],
        "ordered_tests": ["Blood Glucose"],
    })
    assert {item["test"] for item in result["missing_tests"]} == {"Blood Pressure"}


def test_multiple_diagnoses_are_retained_and_rules_evaluated_independently():
    result = run_pipeline(
        "Lisinopril 10 mg oral once daily",
        "Hypertension, Pregnancy",
        ["Serum Creatinine", "Serum Potassium"],
    )
    assert result["parsed_diagnoses"] == ["hypertension", "pregnancy"]
    contraindications = [
        violation for violation in result["violations"]
        if violation["type"] == "drug-diagnosis contraindication"
    ]
    assert len(contraindications) == 1
    assert "pregnancy" in contraindications[0]["description"].lower()


def test_multiple_medicines_and_diagnoses_trigger_each_configured_contraindication():
    result = run_pipeline(
        "Metformin 500 mg oral twice daily\nLisinopril 10 mg oral once daily",
        "Renal impairment, Pregnancy",
        ["eGFR", "Serum Creatinine", "Serum Potassium"],
    )
    findings = [
        violation for violation in result["violations"]
        if violation["type"] == "drug-diagnosis contraindication"
    ]
    assert len(findings) == 2
    assert any("metformin" in item["description"].lower() for item in findings)
    assert any("lisinopril" in item["description"].lower() for item in findings)


def test_all_applicable_drug_pairs_are_checked_in_one_prescription():
    result = run_pipeline(
        "Rx\n"
        "1. Warfarin 5 mg oral once daily\n"
        "2. Ibuprofen 400 mg oral three times daily\n"
        "3. Amoxicillin 500 mg oral three times daily\n"
        "4. Clopidogrel 75 mg oral once daily",
        "",
        ["INR", "CBC"],
    )
    findings = [
        violation for violation in result["violations"]
        if violation["type"] == "drug-drug interaction"
    ]
    assert len(findings) == 4


def test_unrecognized_medicine_is_visible_and_does_not_report_clear_result():
    result = run_pipeline(
        "Rx\n1. Exampletab 10 mg oral once daily",
        "",
        [],
    )
    assert result["parsed_drugs"][0]["name"] == "exampletab"
    assert result["unassessed_drugs"] == ["exampletab"]
    assert "assessment incomplete" in result["explanation_report"].lower()
    assert result["retrieved_chunks"] == []


def test_no_medicine_extraction_does_not_retrieve_or_claim_no_violations():
    result = run_pipeline("Unrecognized text without a medicine", "Hypertension", [])
    assert result["parsed_drugs"] == []
    assert result["retrieved_chunks"] == []
    assert "assessment incomplete" in result["explanation_report"].lower()
