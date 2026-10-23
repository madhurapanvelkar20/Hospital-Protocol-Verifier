"""
Regression tests for the prescription-photo workflow:
OCR text -> structured fields -> parser -> verification pipeline -> /api/verify.

Background: a typed prescription image produced a result with ONE medicine
(Lisinopril, dose/frequency "unspecified") and header/footer text in the
ordered-investigations field. Causes (found by following the data stage by
stage): (1) the parser silently dropped unrecognized drugs, (2) it only read
a frequency written directly after the dose,
(3) the "tests ordered" section had no end, so letterhead/footer lines were
swallowed, (4) /api/verify merged in a re-scan of the entire OCR text, and
(5) the frontend kept stale sample-case values when OCR found no fields.

OCR output is MOCKED here so these tests are deterministic; real image
processing is covered separately (test_ocr.py and the one skippable OCR
test at the bottom of this file). Synthetic data only.
"""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.config as config

config.EMBEDDING_BACKEND = "tfidf"  # offline retrieval; findings don't depend on it

from src.agents.parser_agent import parse_prescription
from src.prescription_extract import extract_structured_fields

# Exactly what Tesseract returned for a clean typed image of the test
# prescription (blank lines between entries, wrapped "before food" line,
# letterhead above and doctor/registration/hospital footer below).
OCR_TYPED = """CITY GENERAL HOSPITAL
Dr. Anil Sharma, MD (Medicine) Reg. No: MH-48213
Patient: Rohan Deshmukh Age/Sex: 48/M Date: 21/10/2026

DIAGNOSIS
Hypertension

Rx

1. Apixaban 5 mg - one tablet twice daily

2. Lisinopril 10 mg - one tablet once daily

3. Atorvastatin 20 mg - one tablet at night

4. Pantoprazole 40 mg - one tablet once daily
before food

INVESTIGATIONS ORDERED
1. Serum Potassium
2. Lipid Profile

Dr. Anil Sharma
Reg. No: MH-48213
City General Hospital, Pune - Ph: 020-5551234"""

# Same prescription written with common abbreviations and different layout.
OCR_ABBREVIATED = """Dx: Hypertension
Rx
1) Tab Apixaban 5mg BD
2) Tab Lisinopril 10mg OD
3) Tab Atorvastatin 20mg HS
4) Tab Pantoprazole 40mg OD before food
Investigations: Serum Potassium, Lipid Profile
Signature: ________"""

EXPECTED = {
    "apixaban": ("5", "twice daily"),
    "lisinopril": ("10", "once daily"),
    "atorvastatin": ("20", "at night"),
    "pantoprazole": ("40", "once daily, before food"),
}


def _by_name(drugs):
    return {d["name"]: d for d in drugs}


def _check_four_drugs(drugs):
    assert [d["name"] for d in drugs] == list(EXPECTED), drugs  # all four, in order
    by_name = _by_name(drugs)
    for name, (dose_number, frequency) in EXPECTED.items():
        assert by_name[name]["dose"].replace(" ", "").startswith(dose_number + "mg"), by_name[name]
        assert by_name[name]["frequency"] == frequency, by_name[name]


# ---------------------------------------------------------------- parser

def test_all_four_medicines_preserved_with_dose_and_frequency():
    parsed = parse_prescription({"raw_text": OCR_TYPED, "diagnosis_hint": "hypertension"})
    _check_four_drugs(parsed["parsed_drugs"])
    assert parsed["parsed_diagnosis"] == "hypertension"


def test_multiline_instruction_is_attached_to_its_medicine():
    drugs = _by_name(parse_prescription({"raw_text": OCR_TYPED})["parsed_drugs"])
    assert "before food" in drugs["pantoprazole"]["frequency"]
    # the wrapped line must not leak onto the previous or next medicine
    assert "before food" not in drugs["atorvastatin"]["frequency"]


def test_abbreviations_and_tab_prefix_are_handled():
    _check_four_drugs(parse_prescription({"raw_text": OCR_ABBREVIATED})["parsed_drugs"])


def test_unrecognised_drugs_are_kept_and_flagged_not_dropped():
    drugs = _by_name(parse_prescription({"raw_text": OCR_TYPED})["parsed_drugs"])
    assert drugs["lisinopril"].get("recognized", True) is True
    assert drugs["atorvastatin"]["recognized"] is True
    for name in ("apixaban", "pantoprazole"):
        assert drugs[name]["recognized"] is False


def test_missing_fields_are_unknown_not_invented():
    text = "Rx\n1. Apixaban 5 mg\n2. Lisinopril"
    drugs = _by_name(parse_prescription({"raw_text": text})["parsed_drugs"])
    assert drugs["apixaban"]["frequency"] == "unspecified"
    assert drugs["lisinopril"]["dose"] == "unspecified"
    assert drugs["lisinopril"]["frequency"] == "unspecified"


def test_header_and_footer_numbers_are_not_parsed_as_medicines():
    names = [d["name"] for d in parse_prescription({"raw_text": OCR_TYPED})["parsed_drugs"]]
    assert len(names) == 4, names


def test_existing_single_sentence_prescriptions_still_parse():
    drugs = parse_prescription(
        {"raw_text": "Patient on Warfarin 5mg oral once daily is additionally "
                     "prescribed Ibuprofen 400mg oral three times daily."}
    )["parsed_drugs"]
    assert [(d["name"], d["dose"], d["frequency"]) for d in drugs] == [
        ("warfarin", "5mg", "once daily"),
        ("ibuprofen", "400mg", "three times daily"),
    ]


# ------------------------------------------------- investigation extraction

def test_only_the_two_ordered_investigations_are_extracted():
    fields = extract_structured_fields(OCR_TYPED)
    assert fields["ordered_tests"] == ["Serum Potassium", "Lipid Profile"]
    assert fields["diagnoses"] == ["Hypertension"]


def test_header_and_footer_text_is_excluded_from_investigations():
    tests = " | ".join(extract_structured_fields(OCR_TYPED)["ordered_tests"]).lower()
    for junk in ("dr.", "anil", "reg", "mh-48213", "hospital", "ph:", "rohan", "21/10/2026"):
        assert junk not in tests, tests


def test_inline_comma_separated_investigations_and_abbreviated_layout():
    fields = extract_structured_fields(OCR_ABBREVIATED)
    assert fields["ordered_tests"] == ["Serum Potassium", "Lipid Profile"]


def test_no_investigations_section_returns_empty_list():
    assert extract_structured_fields(OCR_TYPED.split("INVESTIGATIONS ORDERED")[0])["ordered_tests"] == []


# ------------------------------------------------------ verification pipeline

def test_pipeline_preserves_all_four_medicines_and_adds_no_artificial_findings():
    from src.graph import run_pipeline

    tests = ["Serum Potassium", "Lipid Profile"]
    result = run_pipeline(OCR_TYPED, "hypertension", tests)
    assert [d["name"] for d in result["parsed_drugs"]] == list(EXPECTED)
    assert result["ordered_tests"] == tests

    # OCR/unrecognised drugs must not create or hide findings: the result is
    # identical to typing only the drug that has configured rules.
    baseline = run_pipeline("Prescribe Lisinopril 10 mg once daily for hypertension.", "hypertension", tests)
    assert result["violations"] == baseline["violations"]


# ------------------------------------------------------------------ API

@pytest.fixture
def client(monkeypatch):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    import main

    user = SimpleNamespace(id=1, email="testdoctor@hospital.org", display_name="Dr. Test")
    monkeypatch.setitem(main.app.dependency_overrides, main.get_current_user, lambda: user)
    monkeypatch.setattr(main, "save_verification", lambda *a, **k: None)
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


def test_api_verify_returns_all_four_medicines(client):
    res = client.post("/api/verify", json={
        "raw_text": OCR_TYPED,
        "diagnosis_hint": "Hypertension",
        "ordered_tests": ["Serum Potassium", "Lipid Profile"],
    })
    assert res.status_code == 200, res.text
    data = res.json()
    _check_four_drugs(data["parsed_drugs"])
    assert data["ordered_tests"] == ["Serum Potassium", "Lipid Profile"]


def test_api_confirmed_investigations_are_authoritative(client):
    """Junk the user removed from the field must not be re-added from raw_text."""
    res = client.post("/api/verify", json={
        "raw_text": OCR_TYPED + "\nSerum Potassium",
        "diagnosis_hint": "hypertension",
        "ordered_tests": ["Lipid Profile"],
    })
    assert res.json()["ordered_tests"] == ["Lipid Profile"]


def test_api_without_ordered_tests_falls_back_to_the_text_section(client):
    res = client.post("/api/verify", json={"raw_text": OCR_TYPED, "diagnosis_hint": "hypertension"})
    assert res.json()["ordered_tests"] == ["Serum Potassium", "Lipid Profile"]


def test_api_manual_and_sample_style_requests_still_work(client):
    res = client.post("/api/verify", json={
        "raw_text": "Prescribe Metformin 500mg oral twice daily for type 2 diabetes.",
        "diagnosis_hint": "type 2 diabetes",
        "ordered_tests": [],
    })
    assert res.status_code == 200
    assert "missing monitoring test" in [v["type"] for v in res.json()["violations"]]


# ------------------------------------- OCR noise + every drug in the system

# Real Tesseract output for a photographed "City Care Hospital" prescription:
# the big Rx symbol was read as "OM" on the same line as the first medicine,
# and the printed bullet dots were read as the letter "e".
OCR_CITY_CARE = """City Care Hospital Dr. R. Kulkarni

General Medicine Department MD (Internal Medicine)
Pune, Maharashtra Weg Nes MASAO
Name: Mrs. Anita Sharma UHID: CC12345
Age/Sex: 68/F
Date: 14/10/2026

OM 1) Apixaban 5 mg

1 tab twice daily

2) Lisinopril 10 mg
1 tab once daily

3) Atorvastatin 20 mg
1 tab at night

4) Pantoprazole 40 mg
1 tab once daily (before food)

Investigations:
e Serum Potassium
e Lipid Profile

Dr. R. Kulkarni"""


def test_rx_symbol_noise_does_not_hide_the_first_medicine():
    drugs = parse_prescription({"raw_text": OCR_CITY_CARE})["parsed_drugs"]
    _check_four_drugs(drugs)


def test_misread_bullets_and_signature_are_not_investigations():
    assert extract_structured_fields(OCR_CITY_CARE)["ordered_tests"] == ["Serum Potassium", "Lipid Profile"]


def test_real_test_names_starting_with_a_single_letter_are_kept():
    text = "Investigations:\n- C Reactive Protein\n- B12 Level\nDr. X"
    assert extract_structured_fields(text)["ordered_tests"] == ["C Reactive Protein", "B12 Level"]


@pytest.mark.parametrize("prefix", ["", "OM ", "Rx ", "R/ ", "Wx "])
def test_every_vocabulary_drug_is_identified_in_a_numbered_layout(prefix):
    for drug in sorted(config.KNOWN_DRUGS):
        text = f"{prefix}1) {drug.title()} 10 mg\n\n1 tab twice daily\n\n2) Zzzdrug 5 mg\n1 tab once daily"
        parsed = _by_name(parse_prescription({"raw_text": text})["parsed_drugs"])
        assert drug in parsed, (prefix, drug, parsed)
        assert parsed[drug]["dose"] == "10 mg" and parsed[drug]["frequency"] == "twice daily", parsed[drug]
        assert parsed[drug].get("recognized", True) is True
        assert parsed["zzzdrug"]["recognized"] is False  # unknown drugs are kept, never dropped


def _rules():
    import json
    data = json.loads((Path(__file__).resolve().parent.parent / "data" / "interactions.json").read_text(encoding="utf-8"))
    monitoring = json.loads((Path(__file__).resolve().parent.parent / "data" / "monitoring_requirements.json").read_text(encoding="utf-8"))
    return data, monitoring


def _numbered(drugs):
    return "OM " + "\n\n".join(f"{i}) {d.title()} 10 mg\n1 tab once daily" for i, d in enumerate(drugs, 1))


def test_every_configured_drug_drug_rule_fires_from_a_numbered_prescription():
    from src.graph import run_pipeline

    data, monitoring = _rules()
    for rule in data["drug_drug"]:
        a, b = rule["drugs"]
        tests = [t["test"] for d in (a, b) for t in monitoring.get(d, [])]  # isolate the interaction
        for order in ([a, b], [b, a]):
            result = run_pipeline(_numbered(order), "", tests)
            assert {a, b} <= {d["name"] for d in result["parsed_drugs"]}, rule
            hits = [v for v in result["violations"] if v.get("severity") == rule["severity"]
                    and a in v["description"].lower() and b in v["description"].lower()]
            assert hits, (order, result["violations"])


def test_every_configured_drug_diagnosis_rule_fires_from_a_numbered_prescription():
    from src.graph import run_pipeline

    data, monitoring = _rules()
    for rule in data["drug_diagnosis"]:
        tests = [t["test"] for t in monitoring.get(rule["drug"], [])]
        result = run_pipeline(_numbered([rule["drug"]]), rule["diagnosis"], tests)
        hits = [v for v in result["violations"] if v.get("severity") == rule["severity"]
                and rule["drug"] in v["description"].lower()]
        assert hits, (rule, result["violations"])


def test_every_monitoring_requirement_is_checked_from_a_numbered_prescription():
    from src.graph import run_pipeline

    _, monitoring = _rules()
    for drug, requirements in monitoring.items():
        result = run_pipeline(_numbered([drug]), "", [])
        missing = [v for v in result["violations"] if v["type"] == "missing monitoring test"]
        assert len(missing) >= len(requirements), (drug, result["violations"])


# ------------------------------------------------------- real image (OCR)

def _typed_prescription_png():
    from PIL import Image, ImageDraw, ImageFont

    font = None
    for name in ("arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(name, 26)
            break
        except Exception:
            continue
    if font is None:
        pytest.skip("no TrueType font available to render a readable test image")

    lines = [l for l in OCR_TYPED.splitlines()]
    img = Image.new("RGB", (1200, 60 + 40 * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((30, 25 + 40 * i), line, font=font, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_image_to_fields_end_to_end_with_real_tesseract():
    from src.ocr import extract_text_from_image, OcrUnavailableError

    try:
        text = extract_text_from_image(_typed_prescription_png())
    except OcrUnavailableError:
        pytest.skip("Tesseract engine not installed")

    names = [d["name"] for d in parse_prescription({"raw_text": text})["parsed_drugs"]]
    assert names == list(EXPECTED), (names, text)
    fields = extract_structured_fields(text)
    assert fields["ordered_tests"] == ["Serum Potassium", "Lipid Profile"], fields