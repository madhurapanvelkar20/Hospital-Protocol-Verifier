"""
Generates exactly 100 unique synthetic prescription benchmark cases derived from
the existing knowledge base and verified against clinical guideline rules.

Target distribution:
  - 25 clean prescriptions (no configured violations)
  - 25 missing-investigation cases (required baseline/periodic test withheld)
  - 20 drug-drug interaction cases (contraindicated / high/med/low interaction pairs)
  - 15 drug-diagnosis cases (contraindication against patient condition)
  - 15 multiple-condition cases (compound scenarios with multiple violations)

Each case contains:
  - id: unique string identifier
  - category: benchmark category
  - raw_text: clinical prescription input text
  - diagnosis_hint: patient working diagnosis / condition
  - ordered_tests: list of tests already ordered / completed
  - expected_violations: structured expected finding objects (type, severity, description, source, rule_id)
  - expected_violation_types: list of violation type strings
  - relevant_rules: configured knowledge-base rules relevant to this case
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import INTERACTIONS_FILE, MONITORING_FILE

OUTPUT_FILE = Path(__file__).resolve().parent / "benchmark_dataset.json"

# Medication templates with realistic doses, frequencies (compatible with parser), and standard indications
MED_TEMPLATES = {
    "lisinopril": [
        {"dose": "10mg", "freq": "once daily", "indication": "hypertension"},
        {"dose": "20mg", "freq": "once daily", "indication": "hypertension"},
        {"dose": "5mg", "freq": "once daily", "indication": "hypertension"},
    ],
    "metformin": [
        {"dose": "500mg", "freq": "twice daily", "indication": "type 2 diabetes"},
        {"dose": "1000mg", "freq": "twice daily", "indication": "type 2 diabetes"},
        {"dose": "850mg", "freq": "once daily", "indication": "type 2 diabetes"},
    ],
    "warfarin": [
        {"dose": "5mg", "freq": "once daily", "indication": "atrial fibrillation"},
        {"dose": "2.5mg", "freq": "once daily", "indication": "atrial fibrillation"},
        {"dose": "4mg", "freq": "once daily", "indication": "atrial fibrillation"},
    ],
    "methotrexate": [
        {"dose": "10mg", "freq": "once weekly", "indication": "rheumatoid arthritis"},
        {"dose": "15mg", "freq": "once weekly", "indication": "rheumatoid arthritis"},
        {"dose": "7.5mg", "freq": "once weekly", "indication": "rheumatoid arthritis"},
    ],
    "simvastatin": [
        {"dose": "20mg", "freq": "once daily", "indication": "hyperlipidemia"},
        {"dose": "40mg", "freq": "once daily", "indication": "hyperlipidemia"},
        {"dose": "10mg", "freq": "once daily", "indication": "hyperlipidemia"},
    ],
    "furosemide": [
        {"dose": "40mg", "freq": "once daily", "indication": "heart failure"},
        {"dose": "20mg", "freq": "once daily", "indication": "heart failure"},
        {"dose": "80mg", "freq": "once daily", "indication": "heart failure"},
    ],
    "ibuprofen": [
        {"dose": "400mg", "freq": "three times daily", "indication": "rheumatoid arthritis"},
        {"dose": "600mg", "freq": "three times daily", "indication": "rheumatoid arthritis"},
        {"dose": "200mg", "freq": "as needed", "indication": "rheumatoid arthritis"},
    ],
    "amoxicillin": [
        {"dose": "500mg", "freq": "three times daily", "indication": "coronary artery disease"},
        {"dose": "250mg", "freq": "three times daily", "indication": "coronary artery disease"},
        {"dose": "875mg", "freq": "twice daily", "indication": "coronary artery disease"},
    ],
    "digoxin": [
        {"dose": "0.25mg", "freq": "once daily", "indication": "heart failure"},
        {"dose": "0.125mg", "freq": "once daily", "indication": "heart failure"},
    ],
    "levothyroxine": [
        {"dose": "100mcg", "freq": "once daily", "indication": "hypothyroidism"},
        {"dose": "50mcg", "freq": "once daily", "indication": "hypothyroidism"},
        {"dose": "75mcg", "freq": "once daily", "indication": "hypothyroidism"},
    ],
    "omeprazole": [
        {"dose": "20mg", "freq": "once daily", "indication": "gastroesophageal reflux disease"},
        {"dose": "40mg", "freq": "once daily", "indication": "gastroesophageal reflux disease"},
    ],
    "clopidogrel": [
        {"dose": "75mg", "freq": "once daily", "indication": "coronary artery disease"},
        {"dose": "150mg", "freq": "once daily", "indication": "coronary artery disease"},
    ],
    "insulin": [
        {"dose": "10mg", "freq": "once daily", "indication": "type 2 diabetes"},
        {"dose": "20mg", "freq": "once daily", "indication": "type 2 diabetes"},
    ],
    "losartan": [
        {"dose": "50mg", "freq": "once daily", "indication": "hypertension"},
        {"dose": "100mg", "freq": "once daily", "indication": "hypertension"},
        {"dose": "25mg", "freq": "once daily", "indication": "hypertension"},
    ],
    "prednisone": [
        {"dose": "10mg", "freq": "once daily", "indication": "rheumatoid arthritis"},
        {"dose": "20mg", "freq": "once daily", "indication": "rheumatoid arthritis"},
        {"dose": "5mg", "freq": "once daily", "indication": "rheumatoid arthritis"},
    ],
    "amlodipine": [
        {"dose": "5mg", "freq": "once daily", "indication": "hypertension"},
        {"dose": "10mg", "freq": "once daily", "indication": "hypertension"},
        {"dose": "2.5mg", "freq": "once daily", "indication": "hypertension"},
    ],
}


def load_knowledge_base():
    with open(INTERACTIONS_FILE, encoding="utf-8") as f:
        interactions = json.load(f)
    with open(MONITORING_FILE, encoding="utf-8") as f:
        monitoring = json.load(f)
    return interactions, monitoring


def inspect_knowledge_base():
    interactions, monitoring = load_knowledge_base()
    all_meds = set()
    for rule in interactions.get("drug_drug", []):
        all_meds.update(rule["drugs"])
    for rule in interactions.get("drug_diagnosis", []):
        all_meds.add(rule["drug"])
    all_meds.update(monitoring.keys())

    stats = {
        "actual_medications_count": len(all_meds),
        "actual_medications": sorted(all_meds),
        "actual_drug_drug_rules_count": len(interactions.get("drug_drug", [])),
        "actual_drug_diagnosis_rules_count": len(interactions.get("drug_diagnosis", [])),
        "actual_monitoring_drugs_count": len(monitoring),
    }
    return stats


def _format_drug(drug: str, variant_idx: int = 0) -> str:
    variants = MED_TEMPLATES.get(drug)
    if not variants:
        return f"{drug.title()} 10mg oral once daily"
    var = variants[variant_idx % len(variants)]
    return f"{drug.title()} {var['dose']} oral {var['freq']}"


def build_100_cases() -> List[Dict[str, Any]]:
    interactions, monitoring = load_knowledge_base()
    cases = []
    case_counter = 0

    def make_id(category: str) -> str:
        nonlocal case_counter
        case_counter += 1
        return f"{category}_{case_counter:03d}"

    def get_monitoring_tests(drug: str) -> List[str]:
        return [req["test"] for req in monitoring.get(drug, [])]

    # =========================================================================
    # 1. CLEAN PRESCRIPTIONS (Exactly 25 cases)
    # Prescriptions with all monitoring tests already ordered, no interactions,
    # no contraindications. Should yield 0 violations.
    # =========================================================================
    clean_specs = [
        # (drugs, diagnosis, description_note)
        (["lisinopril"], "hypertension", 0),
        (["lisinopril"], "hypertension", 1),
        (["metformin"], "type 2 diabetes", 0),
        (["metformin"], "type 2 diabetes", 1),
        (["warfarin"], "atrial fibrillation", 0),
        (["warfarin"], "atrial fibrillation", 1),
        (["methotrexate"], "rheumatoid arthritis", 0),
        (["methotrexate"], "rheumatoid arthritis", 1),
        (["simvastatin"], "hyperlipidemia", 0),
        (["simvastatin"], "hyperlipidemia", 1),
        (["furosemide"], "heart failure", 0),
        (["furosemide"], "heart failure", 1),
        (["ibuprofen"], "rheumatoid arthritis", 0),
        (["amoxicillin"], "coronary artery disease", 0),
        (["digoxin"], "heart failure", 0),
        (["digoxin"], "heart failure", 1),
        (["levothyroxine"], "hypothyroidism", 0),
        (["levothyroxine"], "hypothyroidism", 1),
        (["omeprazole"], "gastroesophageal reflux disease", 0),
        (["clopidogrel"], "coronary artery disease", 0),
        (["insulin"], "type 2 diabetes", 0),
        (["losartan"], "hypertension", 0),
        (["losartan"], "hypertension", 1),
        (["prednisone"], "rheumatoid arthritis", 0),
        (["amlodipine"], "hypertension", 0),
    ]
    assert len(clean_specs) == 25, f"Expected 25 clean specs, got {len(clean_specs)}"

    for drugs, diag, var_idx in clean_specs:
        cid = make_id("clean")
        ordered = []
        for d in drugs:
            ordered.extend(get_monitoring_tests(d))
        # Unique list preserving order
        seen_tests = set()
        unique_ordered = [t for t in ordered if not (t in seen_tests or seen_tests.add(t))]

        med_phrases = [_format_drug(d, var_idx) for d in drugs]
        if len(med_phrases) == 1:
            raw_text = f"Prescribe {med_phrases[0]} for {diag}."
        else:
            raw_text = f"Prescribe {med_phrases[0]} and {med_phrases[1]} for {diag}."

        cases.append({
            "id": cid,
            "category": "clean",
            "raw_text": raw_text,
            "diagnosis_hint": diag,
            "ordered_tests": unique_ordered,
            "expected_violations": [],
            "expected_violation_types": [],
            "relevant_rules": [],
        })

    # =========================================================================
    # 2. MISSING-INVESTIGATION CASES (Exactly 25 cases)
    # Required monitoring tests withheld.
    # =========================================================================
    missing_specs = [
        # (drug, diagnosis, tests_to_provide, tests_missing_expected, variant_idx)
        ("warfarin", "atrial fibrillation", [], ["INR"], 0),
        ("warfarin", "atrial fibrillation", [], ["INR"], 1),
        ("metformin", "type 2 diabetes", [], ["eGFR / Serum Creatinine"], 0),
        ("metformin", "type 2 diabetes", [], ["eGFR / Serum Creatinine"], 1),
        ("methotrexate", "rheumatoid arthritis", [], ["CBC", "LFT"], 0),
        ("methotrexate", "rheumatoid arthritis", ["CBC"], ["LFT"], 1),
        ("methotrexate", "rheumatoid arthritis", ["LFT"], ["CBC"], 2),
        ("simvastatin", "hyperlipidemia", [], ["LFT"], 0),
        ("simvastatin", "hyperlipidemia", [], ["LFT"], 1),
        ("furosemide", "heart failure", [], ["Serum Electrolytes (Potassium, Sodium) & Renal Function"], 0),
        ("furosemide", "heart failure", [], ["Serum Electrolytes (Potassium, Sodium) & Renal Function"], 1),
        ("lisinopril", "hypertension", [], ["Serum Creatinine & Potassium"], 0),
        ("lisinopril", "hypertension", [], ["Serum Creatinine & Potassium"], 1),
        ("digoxin", "heart failure", [], ["Serum Digoxin Level, Potassium & Renal Function"], 0),
        ("digoxin", "heart failure", [], ["Serum Digoxin Level, Potassium & Renal Function"], 1),
        ("levothyroxine", "hypothyroidism", [], ["TSH"], 0),
        ("levothyroxine", "hypothyroidism", [], ["TSH"], 1),
        ("clopidogrel", "coronary artery disease", [], ["CBC"], 0),
        ("clopidogrel", "coronary artery disease", [], ["CBC"], 1),
        ("insulin", "type 2 diabetes", [], ["Blood Glucose", "HbA1c"], 0),
        ("insulin", "type 2 diabetes", ["Blood Glucose"], ["HbA1c"], 1),
        ("insulin", "type 2 diabetes", ["HbA1c"], ["Blood Glucose"], 2),
        ("losartan", "hypertension", [], ["Serum Creatinine & Potassium"], 0),
        ("losartan", "hypertension", [], ["Serum Creatinine & Potassium"], 1),
        ("prednisone", "rheumatoid arthritis", [], ["Blood Glucose & Blood Pressure"], 0),
    ]
    assert len(missing_specs) == 25, f"Expected 25 missing specs, got {len(missing_specs)}"

    for drug, diag, provided_tests, missing_tests, var_idx in missing_specs:
        cid = make_id("missing_test")
        med_str = _format_drug(drug, var_idx)
        raw_text = f"Prescribe {med_str} for {diag}."

        expected_viols = []
        for req in monitoring.get(drug, []):
            if req["test"] in missing_tests:
                expected_viols.append({
                    "type": "missing monitoring test",
                    "severity": "medium",
                    "drug": drug,
                    "test": req["test"],
                    "frequency": req["frequency"],
                    "guideline_source": req["guideline_source"],
                })

        cases.append({
            "id": cid,
            "category": "missing_test",
            "raw_text": raw_text,
            "diagnosis_hint": diag,
            "ordered_tests": provided_tests,
            "expected_violations": expected_viols,
            "expected_violation_types": [v["type"] for v in expected_viols],
            "relevant_rules": [f"monitoring:{drug}:{t}" for t in missing_tests],
        })

    # =========================================================================
    # 3. DRUG-DRUG INTERACTION CASES (Exactly 20 cases)
    # Covering all 10 configured DD rules across 2 distinct variants each.
    # Required monitoring tests are supplied to isolate the drug-drug violation.
    # =========================================================================
    dd_rules = interactions["drug_drug"]
    assert len(dd_rules) == 10, f"Expected 10 DD rules, found {len(dd_rules)}"

    for r_idx, rule in enumerate(dd_rules):
        d1, d2 = rule["drugs"]
        diag = MED_TEMPLATES[d1][0]["indication"]
        ordered = get_monitoring_tests(d1) + get_monitoring_tests(d2)
        unique_ordered = list(dict.fromkeys(ordered))

        # Variant 1: standard order (d1 then d2)
        cid1 = make_id("drug_drug")
        d1_str = _format_drug(d1, 0)
        d2_str = _format_drug(d2, 0)
        raw_text1 = f"Patient on {d1_str} is additionally prescribed {d2_str} for {diag}."
        exp_viol1 = [{
            "type": "drug-drug interaction",
            "severity": rule["severity"],
            "drugs": [d1, d2],
            "guideline_source": rule["guideline_source"],
        }]
        cases.append({
            "id": cid1,
            "category": "drug_drug",
            "raw_text": raw_text1,
            "diagnosis_hint": diag,
            "ordered_tests": unique_ordered,
            "expected_violations": exp_viol1,
            "expected_violation_types": ["drug-drug interaction"],
            "relevant_rules": [f"drug_drug:{d1}+{d2}"],
        })

        # Variant 2: reversed/altered formulation order and dose variant
        cid2 = make_id("drug_drug")
        d1_str_v2 = _format_drug(d1, 1)
        d2_str_v2 = _format_drug(d2, 1)
        raw_text2 = f"Prescribe combination therapy: {d2_str_v2} co-administered with {d1_str_v2} for {diag}."
        cases.append({
            "id": cid2,
            "category": "drug_drug",
            "raw_text": raw_text2,
            "diagnosis_hint": diag,
            "ordered_tests": unique_ordered,
            "expected_violations": exp_viol1,
            "expected_violation_types": ["drug-drug interaction"],
            "relevant_rules": [f"drug_drug:{d1}+{d2}"],
        })

    # =========================================================================
    # 4. DRUG-DIAGNOSIS CONTRAINDICATION CASES (Exactly 15 cases)
    # Covering all 5 configured DC rules across 3 distinct clinical variants each.
    # Required monitoring tests are supplied to isolate the contraindication.
    # =========================================================================
    dc_rules = interactions["drug_diagnosis"]
    assert len(dc_rules) == 5, f"Expected 5 DC rules, found {len(dc_rules)}"

    for rule in dc_rules:
        drug = rule["drug"]
        contraindicated_diag = rule["diagnosis"]
        ordered = get_monitoring_tests(drug)

        for var_idx in range(3):
            cid = make_id("drug_diagnosis")
            drug_str = _format_drug(drug, var_idx)
            if var_idx == 0:
                raw_text = f"Prescribe {drug_str} for patient diagnosed with {contraindicated_diag}."
            elif var_idx == 1:
                raw_text = f"Patient with underlying {contraindicated_diag} presents for therapy. Prescribe {drug_str}."
            else:
                raw_text = f"Prescribe {drug_str}. Patient medical history positive for {contraindicated_diag}."

            exp_viol = [{
                "type": "drug-diagnosis contraindication",
                "severity": rule["severity"],
                "drug": drug,
                "diagnosis": contraindicated_diag,
                "guideline_source": rule["guideline_source"],
            }]
            cases.append({
                "id": cid,
                "category": "drug_diagnosis",
                "raw_text": raw_text,
                "diagnosis_hint": contraindicated_diag,
                "ordered_tests": ordered,
                "expected_violations": exp_viol,
                "expected_violation_types": ["drug-diagnosis contraindication"],
                "relevant_rules": [f"drug_diagnosis:{drug}->{contraindicated_diag}"],
            })

    # =========================================================================
    # 5. MULTIPLE-CONDITION CASES (Exactly 15 cases)
    # Compound scenarios with multiple simultaneous violations:
    #   - 10 cases: Drug-Drug interaction + missing monitoring tests
    #   - 3 cases: Drug-Diagnosis contraindication + missing monitoring tests
    #   - 2 cases: Drug-Drug interaction + Drug-Diagnosis contraindication
    # =========================================================================
    multi_specs = [
        # (type, rule_ref, diag, tests_provided, var_idx)
        # 1-10: DD + missing monitoring tests
        ("dd_missing", dd_rules[0], "atrial fibrillation", [], 0),  # warfarin + ibuprofen (missing INR)
        ("dd_missing", dd_rules[1], "coronary artery disease", [], 0),  # warfarin + amoxicillin (missing INR)
        ("dd_missing", dd_rules[2], "rheumatoid arthritis", [], 0),  # methotrexate + ibuprofen (missing CBC, LFT)
        ("dd_missing", dd_rules[3], "heart failure", [], 0),  # lisinopril + furosemide (missing electrolyte/creatinine)
        ("dd_missing", dd_rules[4], "heart failure", [], 0),  # digoxin + furosemide (missing digoxin level/electrolytes)
        ("dd_missing", dd_rules[5], "coronary artery disease", [], 0),  # clopidogrel + omeprazole (missing CBC)
        ("dd_missing", dd_rules[6], "atrial fibrillation", [], 0),  # clopidogrel + warfarin (missing CBC, INR)
        ("dd_missing", dd_rules[7], "coronary artery disease", [], 0),  # clopidogrel + ibuprofen (missing CBC)
        ("dd_missing", dd_rules[8], "rheumatoid arthritis", [], 0),  # prednisone + ibuprofen (missing glucose/BP)
        ("dd_missing", dd_rules[9], "hypertension", [], 0),  # lisinopril + losartan (missing creatinine/K)
        # 11-13: DC + missing monitoring tests
        ("dc_missing", dc_rules[0], "renal impairment", [], 0),  # metformin + renal impairment (missing eGFR)
        ("dc_missing", dc_rules[1], "pregnancy", [], 0),  # lisinopril + pregnancy (missing creatinine/K)
        ("dc_missing", dc_rules[4], "renal impairment", [], 0),  # digoxin + renal impairment (missing digoxin level)
        # 14-15: DD + DC combined
        ("dd_dc", (dd_rules[3], dc_rules[1]), "pregnancy", "provide_all_tests", 0),  # lisinopril + furosemide in pregnancy
        ("dd_dc", (dd_rules[4], dc_rules[4]), "renal impairment", "provide_all_tests", 0),  # digoxin + furosemide in renal impairment
    ]
    assert len(multi_specs) == 15, f"Expected 15 multi specs, got {len(multi_specs)}"

    for spec_type, ref, diag, test_mode, var_idx in multi_specs:
        cid = make_id("multiple")
        if spec_type == "dd_missing":
            rule = ref
            d1, d2 = rule["drugs"]
            d1_str = _format_drug(d1, var_idx)
            d2_str = _format_drug(d2, var_idx)
            raw_text = f"Patient diagnosed with {diag} is prescribed {d1_str} together with {d2_str}."
            expected_viols = [{
                "type": "drug-drug interaction",
                "severity": rule["severity"],
                "drugs": [d1, d2],
                "guideline_source": rule["guideline_source"],
            }]
            rel_rules = [f"drug_drug:{d1}+{d2}"]
            for d in [d1, d2]:
                for req in monitoring.get(d, []):
                    expected_viols.append({
                        "type": "missing monitoring test",
                        "severity": "medium",
                        "drug": d,
                        "test": req["test"],
                        "frequency": req["frequency"],
                        "guideline_source": req["guideline_source"],
                    })
                    rel_rules.append(f"monitoring:{d}:{req['test']}")
            cases.append({
                "id": cid,
                "category": "multiple",
                "raw_text": raw_text,
                "diagnosis_hint": diag,
                "ordered_tests": [],
                "expected_violations": expected_viols,
                "expected_violation_types": [v["type"] for v in expected_viols],
                "relevant_rules": rel_rules,
            })

        elif spec_type == "dc_missing":
            rule = ref
            drug = rule["drug"]
            drug_str = _format_drug(drug, var_idx)
            raw_text = f"Prescribe {drug_str} for patient with documented {diag}."
            expected_viols = [{
                "type": "drug-diagnosis contraindication",
                "severity": rule["severity"],
                "drug": drug,
                "diagnosis": diag,
                "guideline_source": rule["guideline_source"],
            }]
            rel_rules = [f"drug_diagnosis:{drug}->{diag}"]
            for req in monitoring.get(drug, []):
                expected_viols.append({
                    "type": "missing monitoring test",
                    "severity": "medium",
                    "drug": drug,
                    "test": req["test"],
                    "frequency": req["frequency"],
                    "guideline_source": req["guideline_source"],
                })
                rel_rules.append(f"monitoring:{drug}:{req['test']}")
            cases.append({
                "id": cid,
                "category": "multiple",
                "raw_text": raw_text,
                "diagnosis_hint": diag,
                "ordered_tests": [],
                "expected_violations": expected_viols,
                "expected_violation_types": [v["type"] for v in expected_viols],
                "relevant_rules": rel_rules,
            })

        elif spec_type == "dd_dc":
            dd_rule, dc_rule = ref
            d1, d2 = dd_rule["drugs"]
            d1_str = _format_drug(d1, var_idx)
            d2_str = _format_drug(d2, var_idx)
            raw_text = f"Prescribe {d1_str} and {d2_str} for patient with confirmed {diag}."
            ordered = list(dict.fromkeys(get_monitoring_tests(d1) + get_monitoring_tests(d2)))
            expected_viols = [
                {
                    "type": "drug-drug interaction",
                    "severity": dd_rule["severity"],
                    "drugs": [d1, d2],
                    "guideline_source": dd_rule["guideline_source"],
                },
                {
                    "type": "drug-diagnosis contraindication",
                    "severity": dc_rule["severity"],
                    "drug": dc_rule["drug"],
                    "diagnosis": diag,
                    "guideline_source": dc_rule["guideline_source"],
                },
            ]
            cases.append({
                "id": cid,
                "category": "multiple",
                "raw_text": raw_text,
                "diagnosis_hint": diag,
                "ordered_tests": ordered,
                "expected_violations": expected_viols,
                "expected_violation_types": [v["type"] for v in expected_viols],
                "relevant_rules": [f"drug_drug:{d1}+{d2}", f"drug_diagnosis:{dc_rule['drug']}->{diag}"],
            })

    assert len(cases) == 100, f"Expected exactly 100 cases, got {len(cases)}"
    return cases


def main():
    kb_stats = inspect_knowledge_base()
    print("=== Knowledge Base Inspection ===")
    print(f"Target vs Actual Medications: Target=30 | Actual={kb_stats['actual_medications_count']}")
    print(f"Target vs Actual DD Rules:    Target=25 | Actual={kb_stats['actual_drug_drug_rules_count']}")
    print(f"Target vs Actual DC Rules:    Target=12 | Actual={kb_stats['actual_drug_diagnosis_rules_count']}")
    print(f"Actual medications in KB: {', '.join(kb_stats['actual_medications'])}")
    print("-" * 50)

    cases = build_100_cases()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)

    cat_counts = {}
    for c in cases:
        cat_counts[c["category"]] = cat_counts.get(c["category"], 0) + 1

    print(f"Successfully generated {len(cases)} benchmark cases saved to {OUTPUT_FILE}")
    print("Category breakdown:")
    for cat, count in cat_counts.items():
        print(f"  - {cat:20}: {count}")


if __name__ == "__main__":
    main()
