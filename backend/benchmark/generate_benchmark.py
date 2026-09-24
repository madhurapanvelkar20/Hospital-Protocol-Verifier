"""
Generates a synthetic benchmark of prescriptions with known, injected
violations, derived directly from the interaction/monitoring knowledge
graph so every label is guaranteed correct by construction (no manual
labeling error possible).

Five categories, matching the project synopsis's evaluation design:
  - clean          : no violation should be flagged
  - missing_test    : a required monitoring test is withheld
  - drug_drug       : two interacting drugs prescribed together
  - drug_diagnosis  : a drug prescribed against a contraindicated diagnosis
  - multiple        : a drug-drug interaction AND a missing test at once

Run with:
    python benchmark/generate_benchmark.py
Writes benchmark/benchmark_dataset.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import INTERACTIONS_FILE, MONITORING_FILE

OUTPUT_FILE = Path(__file__).resolve().parent / "benchmark_dataset.json"

# Dose/route/frequency/indication used to synthesize natural-sounding
# prescription text for each known drug. Frequencies are restricted to
# phrases the (regex-based) Prescription Parser Agent recognizes.
DRUG_META = {
    "lisinopril":    {"dose": "10mg",   "freq": "once daily",          "diagnosis": "hypertension"},
    "metformin":     {"dose": "500mg",  "freq": "twice daily",         "diagnosis": "type 2 diabetes"},
    "warfarin":      {"dose": "5mg",    "freq": "once daily",          "diagnosis": "atrial fibrillation"},
    "methotrexate":  {"dose": "10mg",   "freq": "once weekly",         "diagnosis": "rheumatoid arthritis"},
    "simvastatin":   {"dose": "20mg",   "freq": "once daily",          "diagnosis": "hyperlipidemia"},
    "furosemide":    {"dose": "40mg",   "freq": "once daily",          "diagnosis": "heart failure"},
    "ibuprofen":     {"dose": "400mg",  "freq": "three times daily",   "diagnosis": "rheumatoid arthritis"},
    "amoxicillin":   {"dose": "500mg",  "freq": "three times daily",   "diagnosis": "coronary artery disease"},
    "digoxin":       {"dose": "0.25mg", "freq": "once daily",          "diagnosis": "heart failure"},
    "levothyroxine": {"dose": "100mcg", "freq": "once daily",          "diagnosis": "hypothyroidism"},
    "omeprazole":    {"dose": "20mg",   "freq": "once daily",          "diagnosis": "gastroesophageal reflux disease"},
    "clopidogrel":   {"dose": "75mg",   "freq": "once daily",          "diagnosis": "coronary artery disease"},
    "insulin":       {"dose": "10mg",   "freq": "once daily",          "diagnosis": "type 2 diabetes"},
    "losartan":      {"dose": "50mg",   "freq": "once daily",          "diagnosis": "hypertension"},
    "prednisone":    {"dose": "10mg",   "freq": "once daily",          "diagnosis": "rheumatoid arthritis"},
    "amlodipine":    {"dose": "5mg",    "freq": "once daily",          "diagnosis": "hypertension"},
}


def _drug_sentence(drug: str) -> str:
    meta = DRUG_META[drug]
    return f"{drug.title()} {meta['dose']} oral {meta['freq']}"


def load_kg():
    with open(INTERACTIONS_FILE, encoding="utf-8") as f:
        interactions = json.load(f)
    with open(MONITORING_FILE, encoding="utf-8") as f:
        monitoring = json.load(f)
    return interactions, monitoring


def build_cases():
    interactions, monitoring = load_kg()
    cases = []
    case_id = 0

    def next_id(prefix):
        nonlocal case_id
        case_id += 1
        return f"{prefix}_{case_id:03d}"

    # ---- clean cases: every known drug, prescribed alone, all required
    # tests already ordered -> should yield zero violations ----
    for drug, meta in DRUG_META.items():
        required_tests = [r["test"] for r in monitoring.get(drug, [])]
        cases.append({
            "id": next_id("clean"),
            "category": "clean",
            "raw_text": f"Prescribe {_drug_sentence(drug)} for {meta['diagnosis']}.",
            "diagnosis_hint": meta["diagnosis"],
            "ordered_tests": required_tests,
            "expected_violation_types": [],
        })

    # ---- missing_test cases: same drug, but withhold the required test(s) ----
    for drug, meta in DRUG_META.items():
        requirements = monitoring.get(drug, [])
        if not requirements:
            continue  # nothing to withhold
        cases.append({
            "id": next_id("missing_test"),
            "category": "missing_test",
            "raw_text": f"Prescribe {_drug_sentence(drug)} for {meta['diagnosis']}.",
            "diagnosis_hint": meta["diagnosis"],
            "ordered_tests": [],
            "expected_violation_types": ["missing monitoring test"] * len(requirements),
        })

    # ---- drug_drug cases: every interaction rule, both drugs' required
    # tests already ordered -> isolates the interaction flag ----
    for rule in interactions["drug_drug"]:
        d1, d2 = rule["drugs"]
        ordered = [r["test"] for r in monitoring.get(d1, [])] + [r["test"] for r in monitoring.get(d2, [])]
        diagnosis = DRUG_META[d1]["diagnosis"]
        cases.append({
            "id": next_id("drug_drug"),
            "category": "drug_drug",
            "raw_text": (
                f"Patient on {_drug_sentence(d1)} is additionally prescribed {_drug_sentence(d2)}."
            ),
            "diagnosis_hint": diagnosis,
            "ordered_tests": ordered,
            "expected_violation_types": ["drug-drug interaction"],
        })

    # ---- drug_diagnosis cases: every contraindication rule, required
    # tests already ordered -> isolates the contraindication flag ----
    for rule in interactions["drug_diagnosis"]:
        drug = rule["drug"]
        ordered = [r["test"] for r in monitoring.get(drug, [])]
        cases.append({
            "id": next_id("drug_diagnosis"),
            "category": "drug_diagnosis",
            "raw_text": f"Prescribe {_drug_sentence(drug)}.",
            "diagnosis_hint": rule["diagnosis"],
            "ordered_tests": ordered,
            "expected_violation_types": ["drug-diagnosis contraindication"],
        })

    # ---- multiple cases: a drug-drug interaction with tests withheld,
    # so both the interaction AND missing-test flags should fire ----
    for rule in interactions["drug_drug"][:5]:
        d1, d2 = rule["drugs"]
        expected = ["drug-drug interaction"]
        expected += ["missing monitoring test"] * len(monitoring.get(d1, []))
        expected += ["missing monitoring test"] * len(monitoring.get(d2, []))
        cases.append({
            "id": next_id("multiple"),
            "category": "multiple",
            "raw_text": (
                f"Patient on {_drug_sentence(d1)} is additionally prescribed {_drug_sentence(d2)}."
            ),
            "diagnosis_hint": DRUG_META[d1]["diagnosis"],
            "ordered_tests": [],
            "expected_violation_types": expected,
        })

    return cases


if __name__ == "__main__":
    cases = build_cases()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)

    by_category = {}
    for c in cases:
        by_category[c["category"]] = by_category.get(c["category"], 0) + 1

    print(f"Generated {len(cases)} benchmark cases -> {OUTPUT_FILE}")
    for cat, count in by_category.items():
        print(f"  {cat}: {count}")
