from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.missing_test_agent import detect_missing_tests
from src.agents.parser_agent import parse_prescription
from src.agents.explanation_agent import explain_violations
from src.prescription_extract import extract_structured_fields


def _missing_tests(drug, ordered_tests):
    return detect_missing_tests({
        "parsed_drugs": [{"name": drug}],
        "ordered_tests": ordered_tests,
    })["missing_tests"]


def test_unknown_drug_is_preserved_and_warned_as_unsupported():
    result = parse_prescription({
        "raw_text": "Prescribe Apixaban 5mg orally twice daily.",
        "diagnosis_hint": None,
    })

    assert result["parsed_drugs"][0]["name"] == "apixaban"
    assert result["parsed_drugs"][0]["recognition_status"] == "unsupported"
    assert result["parser_warnings"][0]["type"] == "unsupported_drug"
    assert "absence of findings as evidence of safety" in result["parser_warnings"][0]["message"]


def test_unknown_drug_without_dose_is_still_preserved():
    result = parse_prescription({
        "raw_text": "Please prescribe Apixaban for atrial fibrillation.",
        "diagnosis_hint": None,
    })

    assert result["parsed_drugs"][0]["name"] == "apixaban"
    assert result["parsed_drugs"][0]["dose"] == "unspecified"
    assert result["parser_warnings"][0]["type"] == "unsupported_drug"


def test_itemized_prescription_preserves_unsupported_drugs_and_ordered_tests():
    raw_text = (
        "- Apixaban 5 mg twice daily\n"
        "- Lisinopril 10 mg daily\n"
        "- Atorvastatin 20 mg at night\n"
        "- Pantoprazole 40 mg daily before food\n\n"
        "Investigations advised:\n"
        "- Serum Potassium\n"
        "- Lipid Profile"
    )
    parsed = parse_prescription({"raw_text": raw_text, "diagnosis_hint": None})
    parsed_by_name = {drug["name"]: drug for drug in parsed["parsed_drugs"]}

    assert set(parsed_by_name) == {
        "apixaban",
        "lisinopril",
        "atorvastatin",
        "pantoprazole",
    }
    assert parsed_by_name["apixaban"]["dose"] == "5 mg"
    assert parsed_by_name["apixaban"]["frequency"] == "twice daily"
    assert parsed_by_name["lisinopril"]["frequency"] == "daily"
    assert parsed_by_name["atorvastatin"]["frequency"] == "at night"
    assert parsed_by_name["pantoprazole"]["dose"] == "40 mg"
    assert parsed_by_name["pantoprazole"]["frequency"] == "daily"
    assert parsed_by_name["pantoprazole"]["recognition_status"] == "unsupported"
    assert parsed_by_name["apixaban"]["recognition_status"] == "unsupported"
    assert {
        warning["drug"]
        for warning in parsed["parser_warnings"]
        if warning["type"] == "unsupported_drug"
    } == {"apixaban", "pantoprazole"}

    ordered_tests = extract_structured_fields(raw_text)["ordered_tests"]
    assert ordered_tests == ["Serum Potassium", "Lipid Profile"]
    missing = detect_missing_tests({
        "parsed_drugs": parsed["parsed_drugs"],
        "ordered_tests": ordered_tests,
    })["missing_tests"]
    missing_by_drug = {finding["drug"]: finding for finding in missing}
    assert missing_by_drug["lisinopril"]["missing_components"] == ["Serum Creatinine"]
    assert missing_by_drug["atorvastatin"]["test"] == "LFT"
    assert "apixaban" not in missing_by_drug
    assert "pantoprazole" not in missing_by_drug


def test_unknown_drug_and_known_drug_are_not_merged_across_conjunction():
    result = parse_prescription({
        "raw_text": "The patient takes Apixaban and Lisinopril.",
        "diagnosis_hint": None,
    })

    assert {drug["name"] for drug in result["parsed_drugs"]} == {
        "apixaban",
        "lisinopril",
    }
    assert any(warning["type"] == "unsupported_drug" for warning in result["parser_warnings"])


def test_unreadable_additional_medication_warns_even_when_another_drug_parses():
    result = parse_prescription({
        "raw_text": (
            "The chart lists lisinopril and a new medication whose name is illegible."
        ),
        "diagnosis_hint": None,
    })

    assert [drug["name"] for drug in result["parsed_drugs"]] == ["lisinopril"]
    assert any(warning["type"] == "drug_parse_failure" for warning in result["parser_warnings"])
    assert not any(
        drug["name"] == "a new medication" for drug in result["parsed_drugs"]
    )


def test_unparseable_nonempty_text_has_a_distinct_parse_warning():
    result = parse_prescription({
        "raw_text": "Medication details are illegible.",
        "diagnosis_hint": None,
    })

    assert result["parsed_drugs"] == []
    assert result["parser_warnings"][0]["type"] == "drug_parse_failure"
    assert result["parser_warnings"][0]["type"] != "unsupported_drug"


def test_final_report_retains_warnings_and_does_not_claim_safety():
    warning = {
        "type": "unsupported_drug",
        "message": "The drug was not assessed; do not interpret this as safe.",
    }
    result = explain_violations({
        "parser_warnings": [warning],
        "retrieval_warnings": [],
        "drug_drug_flags": [],
        "drug_diagnosis_flags": [],
        "missing_tests": [],
        "retrieved_chunks": [],
    })

    assert result["warnings"] == [warning]
    assert "Warnings require review" in result["explanation_report"]
    assert warning["message"] in result["explanation_report"]


def test_one_component_does_not_satisfy_combined_lisinopril_requirement():
    assert len(_missing_tests("lisinopril", ["Potassium"])) == 1
    assert len(_missing_tests("lisinopril", ["Serum Creatinine"])) == 1


def test_separate_complete_components_satisfy_combined_requirement():
    assert _missing_tests("lisinopril", ["Serum Creatinine", "Potassium"]) == []


def test_neither_lisinopril_component_reports_both_missing():
    missing = _missing_tests("lisinopril", [])

    assert len(missing) == 1
    assert missing[0]["missing_components"] == ["Serum Creatinine", "Potassium"]


def test_only_potassium_reports_serum_creatinine_missing():
    missing = _missing_tests("lisinopril", ["Serum Potassium"])

    assert len(missing) == 1
    assert missing[0]["missing_components"] == ["Serum Creatinine"]
    report = explain_violations({"missing_tests": missing})["violations"]
    unfulfilled = report[0]["description"].split(
        "following required component has not been ordered: "
    )[1]
    assert unfulfilled.startswith("Serum Creatinine ")
    assert "Potassium" not in unfulfilled


def test_only_creatinine_reports_potassium_missing():
    missing = _missing_tests("lisinopril", ["Serum Creatinine"])

    assert len(missing) == 1
    assert missing[0]["missing_components"] == ["Potassium"]
    report = explain_violations({"missing_tests": missing})["violations"]
    assert "required component has not been ordered: Potassium" in report[0]["description"]


def test_supported_short_component_aliases_satisfy_combined_requirement():
    assert _missing_tests("lisinopril", ["creatinine", "potassium"]) == []


def test_punctuation_and_whitespace_variants_match_exact_aliases():
    assert _missing_tests("lisinopril", ["SERUM-CREATININE", "  POTASSIUM! "]) == []


def test_lipid_profile_satisfies_neither_lisinopril_component():
    missing = _missing_tests("lisinopril", ["Lipid Profile"])

    assert len(missing) == 1
    assert missing[0]["missing_components"] == ["Serum Creatinine", "Potassium"]
    report = explain_violations({"missing_tests": missing})["violations"]
    assert "required components have not been ordered:" in report[0]["description"]


def test_different_creatinine_test_does_not_match_serum_creatinine():
    missing = _missing_tests("lisinopril", ["Creatinine Clearance", "Potassium"])

    assert len(missing) == 1
    assert missing[0]["missing_components"] == ["Serum Creatinine"]


def test_combined_furosemide_panel_covers_all_explicit_components():
    panel = "Serum Electrolytes (Potassium, Sodium) & Renal Function"
    assert _missing_tests("furosemide", [panel]) == []
    assert len(_missing_tests("furosemide", ["Potassium"])) == 1


def test_unverified_kft_panel_is_not_accepted_as_a_specific_test():
    assert len(_missing_tests("metformin", ["KFT"])) == 1
    assert len(_missing_tests("lisinopril", ["KFT"])) == 1
    assert _missing_tests("lisinopril", ["eGFR", "Potassium"]) == []


def test_component_aliases_are_case_and_punctuation_insensitive():
    assert _missing_tests("metformin", ["ESTIMATED glomerular filtration rate"]) == []
    assert _missing_tests("lisinopril", ["serum creatinine", "POTASSIUM"]) == []


def test_unrelated_test_does_not_satisfy_required_components():
    assert len(_missing_tests("lisinopril", ["CBC", "LFT"])) == 1
