"""
Tests for src/prescription_extract.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.prescription_extract import extract_structured_fields

SAMPLE_PRESCRIPTION_TEXT = """Sunrise Medical Centre

PATIENT NAME : Rohan Deshmukh
AGE / GENDER : 48 years / Male

DIAGNOSIS
1. Hypertension
2. Type 2 Diabetes Mellitus

PRESCRIPTION

Rx
1. Telmisartan 40 mg - 1 tablet once daily (morning)
2. Metformin 500 mg - 1 tablet twice daily (after meals)
3. Atorvastatin 10 mg - 1 tablet once daily (night)
4. Amlodipine 5 mg - 1 tablet once daily (morning)

TESTS ORDERED
1. Fasting Blood Sugar (FBS)

ADDITIONAL ADVICE
- Follow a low-salt, low-sugar diet.
- Monitor blood pressure at home.
"""


def test_extracts_multiple_diagnoses_from_numbered_section():
    result = extract_structured_fields(SAMPLE_PRESCRIPTION_TEXT)
    assert result["diagnoses"] == ["Hypertension", "Type 2 Diabetes Mellitus"], result["diagnoses"]
    print("PASS: extracts both diagnoses from a numbered DIAGNOSIS section")


def test_extracts_tests_ordered_section():
    result = extract_structured_fields(SAMPLE_PRESCRIPTION_TEXT)
    assert result["ordered_tests"] == ["Fasting Blood Sugar (FBS)"], result["ordered_tests"]
    print("PASS: extracts the TESTS ORDERED section correctly")


def test_extracts_exact_blank_line_separated_investigations():
    text = (
        "Continue lisinopril 10 mg once daily.\n\n"
        "Investigations advised:\n\n"
        "Serum Creatinine\n\n"
        "Serum Potassium"
    )
    result = extract_structured_fields(text)
    assert result["ordered_tests"] == ["Serum Creatinine", "Serum Potassium"]


def test_section_stops_at_next_header_not_blank_line_only():
    # Regression check: the PRESCRIPTION header right after DIAGNOSIS (no
    # blank line separating them in some formats) must still end the
    # diagnosis section rather than swallowing the Rx list into it.
    text = "DIAGNOSIS\n1. Hypertension\nPRESCRIPTION\n1. Amlodipine 5mg\n"
    result = extract_structured_fields(text)
    assert result["diagnoses"] == ["Hypertension"], result["diagnoses"]
    print("PASS: a section correctly ends at the next header even with no blank line between them")


def test_no_explicit_section_falls_back_to_keyword_match():
    text = "Prescribe Metformin 500mg oral twice daily for type 2 diabetes."
    result = extract_structured_fields(text)
    assert "type 2 diabetes" in result["diagnoses"], result["diagnoses"]
    print("PASS: falls back to keyword matching when no DIAGNOSIS section exists")


def test_no_tests_section_returns_empty_not_guessed():
    text = "Prescribe Metformin 500mg oral twice daily for type 2 diabetes."
    result = extract_structured_fields(text)
    assert result["ordered_tests"] == [], result["ordered_tests"]
    print("PASS: no TESTS ORDERED section correctly returns an empty list, not a guess")


def test_bulleted_and_hyphenated_markers_are_stripped():
    text = "DIAGNOSIS\n- Hypertension\n* Type 2 Diabetes\n\n"
    result = extract_structured_fields(text)
    assert result["diagnoses"] == ["Hypertension", "Type 2 Diabetes"], result["diagnoses"]
    print("PASS: strips bullet/dash/asterisk markers, not just numbered-list markers")


if __name__ == "__main__":
    test_extracts_multiple_diagnoses_from_numbered_section()
    test_extracts_tests_ordered_section()
    test_section_stops_at_next_header_not_blank_line_only()
    test_no_explicit_section_falls_back_to_keyword_match()
    test_no_tests_section_returns_empty_not_guessed()
    test_bulleted_and_hyphenated_markers_are_stripped()
    print("\nAll prescription extraction tests passed.")
