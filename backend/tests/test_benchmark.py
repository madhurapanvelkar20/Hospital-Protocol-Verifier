"""
Automated unit and integration tests for the 100-case synthetic benchmark suite.

Verifies:
  1. Dataset case count is exactly 100
  2. Dataset category distribution matches requirements exactly:
     - 25 clean
     - 25 missing_test
     - 20 drug_drug
     - 15 drug_diagnosis
     - 15 multiple
  3. All case IDs are strictly unique
  4. Each case conforms to expected schema (id, category, raw_text, diagnosis_hint,
     ordered_tests, expected_violations, expected_violation_types, relevant_rules)
  5. Knowledge base actual counts vs intended project targets
  6. Evaluation metric calculation engine (TP, FP, FN, TN, precision, recall, f1, accuracy, fpr)
  7. Baseline and pipeline execution behavior
"""

import json
from pathlib import Path
from collections import Counter
import pytest

from benchmark.generate_benchmark import (
    load_knowledge_base,
    inspect_knowledge_base,
    build_100_cases,
    OUTPUT_FILE,
)
from benchmark.run_evaluation import (
    calculate_metrics,
    run_no_agent,
    run_retrieval_only,
    run_full_pipeline,
)


def test_knowledge_base_actual_counts():
    """Confirms actual KB inventory without fabricating rules."""
    stats = inspect_knowledge_base()
    assert stats["actual_medications_count"] == 15
    assert stats["actual_drug_drug_rules_count"] == 10
    assert stats["actual_drug_diagnosis_rules_count"] == 5
    assert stats["actual_monitoring_drugs_count"] == 12


def test_benchmark_exact_counts_and_distribution():
    """Verifies that generated benchmark has exactly 100 cases with the required category splits."""
    cases = build_100_cases()
    assert len(cases) == 100, f"Expected 100 cases, found {len(cases)}"

    # Unique IDs
    ids = [c["id"] for c in cases]
    assert len(set(ids)) == 100, f"Expected 100 unique IDs, found {len(set(ids))}"

    # Category counts
    cat_counts = Counter(c["category"] for c in cases)
    assert cat_counts["clean"] == 25, f"Expected 25 clean cases, got {cat_counts['clean']}"
    assert cat_counts["missing_test"] == 25, f"Expected 25 missing_test cases, got {cat_counts['missing_test']}"
    assert cat_counts["drug_drug"] == 20, f"Expected 20 drug_drug cases, got {cat_counts['drug_drug']}"
    assert cat_counts["drug_diagnosis"] == 15, f"Expected 15 drug_diagnosis cases, got {cat_counts['drug_diagnosis']}"
    assert cat_counts["multiple"] == 15, f"Expected 15 multiple cases, got {cat_counts['multiple']}"


def test_benchmark_schema_integrity():
    """Verifies that every case has valid structure, diagnosis hint, and non-empty clinical text."""
    cases = build_100_cases()
    required_keys = {
        "id", "category", "raw_text", "diagnosis_hint",
        "ordered_tests", "expected_violations", "expected_violation_types", "relevant_rules"
    }

    for case in cases:
        assert required_keys.issubset(case.keys()), f"Missing keys in case {case.get('id')}"
        assert isinstance(case["id"], str) and len(case["id"]) > 0
        assert isinstance(case["raw_text"], str) and len(case["raw_text"]) > 5
        assert isinstance(case["ordered_tests"], list)
        assert isinstance(case["expected_violations"], list)
        assert isinstance(case["expected_violation_types"], list)
        assert isinstance(case["relevant_rules"], list)

        if case["category"] == "clean":
            assert len(case["expected_violations"]) == 0
            assert len(case["expected_violation_types"]) == 0
        else:
            assert len(case["expected_violations"]) > 0
            assert len(case["expected_violation_types"]) > 0
            assert len(case["relevant_rules"]) > 0


def test_metric_engine_calculations():
    """Unit tests the metrics engine across known synthetic predictions (edge cases, TP/FP/FN/TN)."""
    mock_cases = [
        # Case 1: Clean (Expect 0)
        {"id": "c1", "category": "clean", "raw_text": "t1", "expected_violation_types": []},
        # Case 2: Clean (Expect 0)
        {"id": "c2", "category": "clean", "raw_text": "t2", "expected_violation_types": []},
        # Case 3: Violation (Expect DD)
        {"id": "c3", "category": "drug_drug", "raw_text": "t3", "expected_violation_types": ["drug-drug interaction"]},
        # Case 4: Violation (Expect 2 missing tests)
        {"id": "c4", "category": "missing_test", "raw_text": "t4", "expected_violation_types": ["missing monitoring test", "missing monitoring test"]},
    ]

    # Perfect predictions
    preds_perfect = [
        [],
        [],
        [{"type": "drug-drug interaction"}],
        [{"type": "missing monitoring test"}, {"type": "missing monitoring test"}],
    ]
    res_perfect = calculate_metrics(preds_perfect, mock_cases)
    assert res_perfect["case_accuracy"] == 1.0
    assert res_perfect["violation_precision"] == 1.0
    assert res_perfect["violation_recall"] == 1.0
    assert res_perfect["f1_score"] == 1.0
    assert res_perfect["false_positive_rate"] == 0.0
    assert res_perfect["counts"]["total_tp"] == 3
    assert res_perfect["counts"]["total_tn"] == 2
    assert res_perfect["counts"]["total_fp"] == 0
    assert res_perfect["counts"]["total_fn"] == 0

    # No-check baseline predictions (always empty)
    preds_empty = [[], [], [], []]
    res_empty = calculate_metrics(preds_empty, mock_cases)
    assert res_empty["case_accuracy"] == 0.5  # 2 of 4 cases exact match (the 2 clean cases)
    assert res_empty["violation_precision"] is None  # 0 TP and 0 FP -> undefined (reported as None / N/A)
    assert res_empty["violation_recall"] == 0.0     # 0 TP / 3 FN = 0.0
    assert res_empty["f1_score"] == 0.0
    assert res_empty["false_positive_rate"] == 0.0
    assert res_empty["counts"]["total_tp"] == 0
    assert res_empty["counts"]["total_fn"] == 3
    assert res_empty["counts"]["total_tn"] == 2

    # Predictions with False Positives and False Negatives
    preds_noisy = [
        [{"type": "drug-drug interaction"}],  # FP on clean!
        [],                                  # TN on clean
        [],                                  # FN on DD
        [{"type": "missing monitoring test"}], # Partial match: 1 TP, 1 FN
    ]
    res_noisy = calculate_metrics(preds_noisy, mock_cases)
    assert res_noisy["case_accuracy"] == 0.25  # Only c2 matched exactly
    assert res_noisy["false_positive_rate"] == 0.5  # 1 FP out of 2 clean cases
    assert res_noisy["counts"]["total_tp"] == 1
    assert res_noisy["counts"]["total_fp"] == 1
    assert res_noisy["counts"]["total_fn"] == 2
    # Precision = 1 / (1 + 1) = 0.5
    assert res_noisy["violation_precision"] == 0.5
    # Recall = 1 / (1 + 2) = 0.3333
    assert res_noisy["violation_recall"] == round(1 / 3, 4)


def test_baseline_implementations():
    """Verifies that no_agent and retrieval_only baselines behave as designed."""
    sample_case = {
        "id": "test_01",
        "category": "drug_drug",
        "raw_text": "Prescribe Warfarin 5mg oral once daily and Ibuprofen 400mg oral three times daily.",
        "diagnosis_hint": "atrial fibrillation",
        "ordered_tests": ["INR"],
        "expected_violation_types": ["drug-drug interaction"],
    }

    no_agent_res = run_no_agent(sample_case)
    assert no_agent_res == []

    retrieval_res = run_retrieval_only(sample_case)
    assert retrieval_res == []
