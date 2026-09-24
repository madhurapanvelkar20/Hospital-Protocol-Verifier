"""
Runs the benchmark dataset against three systems and reports adherence /
false-positive / missed-violation metrics for each, matching the
evaluation design described in the project synopsis:

  1. no_agent baseline   -- always predicts "no violations" (a naive floor;
                             shows what you'd get with zero safety checking)
  2. retrieval_only baseline -- runs retrieval, but skips the Cross-Check
                             and Missing-Test agents entirely (shows what a
                             plain-RAG system with no structured knowledge
                             graph would catch -- i.e. nothing, since this
                             system's factual checks all live in agents 3-4,
                             not in retrieved text)
  3. full_pipeline        -- the complete 5-agent system

Metrics (per system, and per category):
  - case_accuracy       : did predicted violation TYPES (as a multiset)
                           exactly match the expected ones for this case?
  - violation_recall     : of all expected violations across the dataset,
                           what fraction did this system predict? (misses
                           = dangerous false negatives)
  - false_positive_rate  : fraction of *clean* cases where the system
                           incorrectly flagged something

Run with:
    python benchmark/run_evaluation.py
Writes benchmark/evaluation_report.json and prints a summary table.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.state import VerifierState
from src.agents.parser_agent import parse_prescription
from src.agents.retriever_agent import retrieve_protocol
from src.agents.cross_check_agent import cross_check
from src.agents.missing_test_agent import detect_missing_tests
from src.agents.explanation_agent import explain_violations

DATASET_FILE = Path(__file__).resolve().parent / "benchmark_dataset.json"
REPORT_FILE = Path(__file__).resolve().parent / "evaluation_report.json"


def load_cases():
    with open(DATASET_FILE, encoding="utf-8") as f:
        return json.load(f)


def run_full_pipeline(case) -> list:
    """Agents 1-5, in the same order as src/graph.py, run inline here
    (rather than via LangGraph) so this script has no extra dependency
    and stays easy to read top-to-bottom."""
    state: VerifierState = {
        "raw_text": case["raw_text"],
        "diagnosis_hint": case["diagnosis_hint"],
        "ordered_tests": case["ordered_tests"],
    }
    state.update(parse_prescription(state))
    state.update(retrieve_protocol(state))
    state.update(cross_check(state))
    state.update(detect_missing_tests(state))
    state.update(explain_violations(state))
    return [v["type"] for v in state["violations"]]


def run_retrieval_only(case) -> list:
    """Same as full pipeline, but Cross-Check and Missing-Test agents are
    skipped entirely -- approximates a plain-RAG system with no
    structured knowledge graph behind it."""
    state: VerifierState = {
        "raw_text": case["raw_text"],
        "diagnosis_hint": case["diagnosis_hint"],
        "ordered_tests": case["ordered_tests"],
    }
    state.update(parse_prescription(state))
    state.update(retrieve_protocol(state))
    state["drug_drug_flags"] = []
    state["drug_diagnosis_flags"] = []
    state["missing_tests"] = []
    state.update(explain_violations(state))
    return [v["type"] for v in state["violations"]]


def run_no_agent(case) -> list:
    """Naive floor: never flags anything."""
    return []


SYSTEMS = {
    "no_agent": run_no_agent,
    "retrieval_only": run_retrieval_only,
    "full_pipeline": run_full_pipeline,
}


def evaluate(system_fn, cases):
    total_expected = 0
    total_recalled = 0
    exact_match_count = 0
    clean_cases = [c for c in cases if c["category"] == "clean"]
    false_positive_count = 0

    per_category = defaultdict(lambda: {"total": 0, "exact_match": 0})

    for case in cases:
        predicted = system_fn(case)
        expected = case["expected_violation_types"]

        predicted_counter = Counter(predicted)
        expected_counter = Counter(expected)

        # recall: how many expected violations did we predict at least once
        # per type (capped at the expected count for that type)
        for vtype, count in expected_counter.items():
            total_recalled += min(predicted_counter.get(vtype, 0), count)
        total_expected += sum(expected_counter.values())

        is_exact_match = predicted_counter == expected_counter
        if is_exact_match:
            exact_match_count += 1

        per_category[case["category"]]["total"] += 1
        if is_exact_match:
            per_category[case["category"]]["exact_match"] += 1

    for case in clean_cases:
        predicted = system_fn(case)
        if predicted:
            false_positive_count += 1

    n = len(cases)
    return {
        "case_accuracy": round(exact_match_count / n, 3),
        "violation_recall": round(total_recalled / total_expected, 3) if total_expected else None,
        "false_positive_rate": round(false_positive_count / len(clean_cases), 3) if clean_cases else None,
        "per_category_accuracy": {
            cat: round(v["exact_match"] / v["total"], 3) for cat, v in per_category.items()
        },
    }


if __name__ == "__main__":
    cases = load_cases()
    results = {name: evaluate(fn, cases) for name, fn in SYSTEMS.items()}

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Evaluated {len(cases)} benchmark cases across {len(SYSTEMS)} systems\n")
    header = f"{'System':<18}{'Case Accuracy':<16}{'Violation Recall':<18}{'False Positive Rate':<20}"
    print(header)
    print("-" * len(header))
    for name, metrics in results.items():
        print(
            f"{name:<18}{metrics['case_accuracy']:<16}"
            f"{metrics['violation_recall']:<18}{metrics['false_positive_rate']:<20}"
        )

    print("\nPer-category case accuracy (full_pipeline):")
    for cat, acc in results["full_pipeline"]["per_category_accuracy"].items():
        print(f"  {cat:<16}{acc}")

    print(f"\nFull report written to {REPORT_FILE}")
