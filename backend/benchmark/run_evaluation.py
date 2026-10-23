"""
Runs the 100-case synthetic benchmark across three systems:
  1. no_agent baseline: Naive floor; never flags any violations.
  2. retrieval_only baseline: Runs real LangGraph parser + hybrid retriever,
     bypassing Cross-Check and Missing-Test agents. Approximates plain-RAG
     without structured knowledge verification.
  3. full_pipeline: The complete 5-agent LangGraph verifier.

Calculates:
  - Case accuracy (exact multi-set match of violation findings)
  - Violation-level True Positives (TP), False Positives (FP), False Negatives (FN), True Negatives (TN)
  - Violation Precision, Recall, F1-score
  - False Positive Rate (FPR) on clean cases
  - Per-category metrics across all 5 benchmark categories
  - Case-level expected-versus-actual predictions

Outputs:
  - benchmark/evaluation_report.json
  - benchmark/benchmark_results.csv (case-level granular results)
  - benchmark/summary_metrics.csv (comparative system metrics)
  - benchmark/figure_5_10_comparison.png (high-resolution Matplotlib grouped bar chart)
"""

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.state import VerifierState
from src.graph import get_graph
from src.agents.parser_agent import parse_prescription
from src.agents.retriever_agent import retrieve_protocol
from src.agents.explanation_agent import explain_violations

BENCHMARK_DIR = Path(__file__).resolve().parent
DATASET_FILE = BENCHMARK_DIR / "benchmark_dataset.json"
REPORT_FILE = BENCHMARK_DIR / "evaluation_report.json"
CASE_CSV_FILE = BENCHMARK_DIR / "benchmark_results.csv"
SUMMARY_CSV_FILE = BENCHMARK_DIR / "summary_metrics.csv"
CHART_FILE = BENCHMARK_DIR / "figure_5_10_comparison.png"


def load_cases() -> List[Dict[str, Any]]:
    with open(DATASET_FILE, encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# Pipeline Execution Functions
# =============================================================================

def run_no_agent(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """System 1: No safety check baseline. Returns 0 findings."""
    return []


def run_retrieval_only(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    System 2: Retrieval-only baseline.
    Executes parsing and hybrid retrieval over clinical protocol guidelines,
    but bypasses the Cross-Check Agent and Missing-Test Agent.
    Simulates standard RAG retrieval without structured rule inference.
    """
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
    return state.get("violations", [])


def run_full_pipeline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    System 3: Full ProtocolVerify 5-stage LangGraph pipeline.
    Invokes the compiled StateGraph via src.graph.get_graph().
    """
    graph = get_graph()
    initial_state: VerifierState = {
        "raw_text": case["raw_text"],
        "diagnosis_hint": case["diagnosis_hint"],
        "ordered_tests": case["ordered_tests"],
    }
    result = graph.invoke(initial_state)
    return result.get("violations", [])


SYSTEMS = {
    "no_agent": run_no_agent,
    "retrieval_only": run_retrieval_only,
    "full_pipeline": run_full_pipeline,
}


# =============================================================================
# Evaluation Metrics Engine
# =============================================================================

def calculate_metrics(predicted_violations_list: List[List[Dict[str, Any]]], cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates system predictions against ground-truth benchmark cases.
    Computes rigorous case-level and finding-level metrics.
    """
    n_cases = len(cases)
    exact_match_count = 0
    clean_cases_count = 0
    clean_cases_fp = 0

    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_tn = 0  # Clean cases correctly identified with 0 violations

    per_category = defaultdict(lambda: {
        "total": 0,
        "exact_match": 0,
        "tp": 0,
        "fp": 0,
        "fn": 0,
    })

    case_records = []

    for case, predicted_violations in zip(cases, predicted_violations_list):
        category = case["category"]
        expected_types = case["expected_violation_types"]
        predicted_types = [v["type"] for v in predicted_violations]

        exp_counter = Counter(expected_types)
        pred_counter = Counter(predicted_types)

        is_exact_match = (exp_counter == pred_counter)
        if is_exact_match:
            exact_match_count += 1

        # Calculate violation-level TP, FP, FN for this case
        all_types = set(exp_counter.keys()) | set(pred_counter.keys())
        case_tp = 0
        case_fp = 0
        case_fn = 0

        for vtype in all_types:
            c_exp = exp_counter.get(vtype, 0)
            c_pred = pred_counter.get(vtype, 0)
            case_tp += min(c_exp, c_pred)
            if c_pred > c_exp:
                case_fp += (c_pred - c_exp)
            if c_exp > c_pred:
                case_fn += (c_exp - c_pred)

        total_tp += case_tp
        total_fp += case_fp
        total_fn += case_fn

        per_category[category]["total"] += 1
        if is_exact_match:
            per_category[category]["exact_match"] += 1
        per_category[category]["tp"] += case_tp
        per_category[category]["fp"] += case_fp
        per_category[category]["fn"] += case_fn

        if category == "clean":
            clean_cases_count += 1
            if len(predicted_types) > 0:
                clean_cases_fp += 1
            else:
                total_tn += 1

        case_records.append({
            "case_id": case["id"],
            "category": category,
            "raw_text": case["raw_text"],
            "expected_count": len(expected_types),
            "predicted_count": len(predicted_types),
            "expected_types": "; ".join(expected_types) if expected_types else "None",
            "predicted_types": "; ".join(predicted_types) if predicted_types else "None",
            "exact_match": is_exact_match,
            "tp": case_tp,
            "fp": case_fp,
            "fn": case_fn,
        })

    # Summary metrics calculation
    case_accuracy = exact_match_count / n_cases if n_cases > 0 else 0.0

    # Violation-level Precision, Recall, F1
    precision = (total_tp / (total_tp + total_fp)) if (total_tp + total_fp) > 0 else None
    recall = (total_tp / (total_tp + total_fn)) if (total_tp + total_fn) > 0 else None
    
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = (2 * precision * recall / (precision + recall))
    elif precision == 0.0 or recall == 0.0:
        f1 = 0.0
    else:
        f1 = None

    # False Positive Rate on clean cases: FP_clean / (FP_clean + TN_clean)
    fpr = (clean_cases_fp / clean_cases_count) if clean_cases_count > 0 else 0.0

    # Category breakdown
    cat_results = {}
    for cat, data in per_category.items():
        c_acc = data["exact_match"] / data["total"] if data["total"] > 0 else 0.0
        c_tp = data["tp"]
        c_fp = data["fp"]
        c_fn = data["fn"]
        c_rec = (c_tp / (c_tp + c_fn)) if (c_tp + c_fn) > 0 else (None if c_tp == 0 and c_fp == 0 and c_fn == 0 else 0.0)
        c_prec = (c_tp / (c_tp + c_fp)) if (c_tp + c_fp) > 0 else (None if c_tp == 0 and c_fp == 0 else 0.0)
        cat_results[cat] = {
            "total_cases": data["total"],
            "case_accuracy": round(c_acc, 4),
            "tp": c_tp,
            "fp": c_fp,
            "fn": c_fn,
            "recall": round(c_rec, 4) if c_rec is not None else None,
            "precision": round(c_prec, 4) if c_prec is not None else None,
        }

    return {
        "case_accuracy": round(case_accuracy, 4),
        "violation_precision": round(precision, 4) if precision is not None else None,
        "violation_recall": round(recall, 4) if recall is not None else None,
        "f1_score": round(f1, 4) if f1 is not None else None,
        "false_positive_rate": round(fpr, 4),
        "counts": {
            "total_cases": n_cases,
            "clean_cases": clean_cases_count,
            "clean_false_positives": clean_cases_fp,
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_fn": total_fn,
            "total_tn": total_tn,
        },
        "per_category": cat_results,
        "case_records": case_records,
    }


def generate_chart(results: Dict[str, Any], output_path: Path):
    """
    Generates a high-resolution Matplotlib grouped bar chart comparing
    Case Accuracy, Violation Recall, and False Positive Rate across evaluated systems.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        systems = ["no_agent", "retrieval_only", "full_pipeline"]
        system_labels = ["No-Check Baseline", "Retrieval-Only Baseline", "Full ProtocolVerify"]
        metrics = ["Case Accuracy", "Violation Recall", "False-Positive Rate"]

        # Data matrix: shape (len(metrics), len(systems))
        accuracy_vals = [results[s]["case_accuracy"] for s in systems]
        recall_vals = [results[s]["violation_recall"] for s in systems]
        fpr_vals = [results[s]["false_positive_rate"] for s in systems]

        data = np.array([accuracy_vals, recall_vals, fpr_vals])

        x = np.arange(len(system_labels))
        width = 0.25

        fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

        colors = ["#2b5c8f", "#d95f02", "#7570b3"]

        rects1 = ax.bar(x - width, data[0], width, label="Case Accuracy", color=colors[0], edgecolor="black", linewidth=0.8)
        rects2 = ax.bar(x, data[1], width, label="Violation Recall", color=colors[1], edgecolor="black", linewidth=0.8)
        rects3 = ax.bar(x + width, data[2], width, label="False-Positive Rate", color=colors[2], edgecolor="black", linewidth=0.8)

        ax.set_ylabel("Metric Score (0.0 to 1.0)", fontsize=12, fontweight="bold", labelpad=10)
        ax.set_title("Figure 5.10: Comparative Evaluation of Treatment Protocol Verification Systems", fontsize=13, fontweight="bold", pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels(system_labels, fontsize=11, fontweight="bold")
        ax.set_ylim(0, 1.15)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        ax.legend(loc="upper left", fontsize=10, frameon=True)

        # Attach value labels on bars
        def autolabel(rects):
            for rect in rects:
                height = rect.get_height()
                ax.annotate(
                    f"{height:.2f}",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 4),  # 4 points vertical offset
                    textcoords="offset points",
                    ha="center", va="bottom",
                    fontsize=9, fontweight="bold"
                )

        autolabel(rects1)
        autolabel(rects2)
        autolabel(rects3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300)
        plt.close()
        print(f"Figure 5.10 chart saved to {output_path}")
    except Exception as e:
        print(f"Warning: Could not generate chart: {e}")


def main():
    print("Loading benchmark dataset...")
    cases = load_cases()
    print(f"Loaded {len(cases)} cases.")

    all_results = {}
    detailed_case_records = {}

    for sys_name, sys_fn in SYSTEMS.items():
        print(f"\n--- Running evaluation for: {sys_name} ---")
        preds = []
        for i, case in enumerate(cases):
            if (i + 1) % 25 == 0:
                print(f"  Processed {i + 1}/{len(cases)} cases...")
            preds.append(sys_fn(case))
        metrics = calculate_metrics(preds, cases)
        detailed_case_records[sys_name] = metrics.pop("case_records")
        all_results[sys_name] = metrics

    # Save evaluation report JSON
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nEvaluation report written to {REPORT_FILE}")

    # Save summary metrics CSV
    with open(SUMMARY_CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["System", "Case Accuracy", "Violation Precision", "Violation Recall", "F1 Score", "False Positive Rate"])
        for sys_name, res in all_results.items():
            writer.writerow([
                sys_name,
                res["case_accuracy"],
                res["violation_precision"],
                res["violation_recall"],
                res["f1_score"],
                res["false_positive_rate"]
            ])
    print(f"Summary metrics CSV written to {SUMMARY_CSV_FILE}")

    # Save detailed case results for full_pipeline
    with open(CASE_CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Case ID", "Category", "Expected Violation Count", "Predicted Violation Count",
            "Expected Types", "Predicted Types", "Exact Match", "TP", "FP", "FN", "Prescription Text"
        ])
        for row in detailed_case_records["full_pipeline"]:
            writer.writerow([
                row["case_id"],
                row["category"],
                row["expected_count"],
                row["predicted_count"],
                row["expected_types"],
                row["predicted_types"],
                row["exact_match"],
                row["tp"],
                row["fp"],
                row["fn"],
                row["raw_text"],
            ])
    print(f"Case-level results CSV written to {CASE_CSV_FILE}")

    # Generate Figure 5.10 chart
    generate_chart(all_results, CHART_FILE)

    # Print summary table
    print("\n" + "=" * 80)
    print("BENCHMARK EVALUATION SUMMARY (100 Cases)")
    print("=" * 80)
    header = f"{'System':<25}{'Case Accuracy':<16}{'Precision':<12}{'Recall':<12}{'F1-Score':<12}{'FPR':<8}"
    print(header)
    print("-" * len(header))
    for name, m in all_results.items():
        prec_str = f"{m['violation_precision']:<12.3f}" if m['violation_precision'] is not None else f"{'N/A':<12}"
        rec_str = f"{m['violation_recall']:<12.3f}" if m['violation_recall'] is not None else f"{'N/A':<12}"
        f1_str = f"{m['f1_score']:<12.3f}" if m['f1_score'] is not None else f"{'N/A':<12}"
        print(
            f"{name:<25}{m['case_accuracy']:<16.3f}"
            f"{prec_str}{rec_str}"
            f"{f1_str}{m['false_positive_rate']:<8.3f}"
        )

    print("\nPer-Category Case Accuracy (Full Pipeline):")
    for cat, data in all_results["full_pipeline"]["per_category"].items():
        print(f"  - {cat:20}: {data['case_accuracy']:.3f} (Cases: {data['total_cases']})")


if __name__ == "__main__":
    main()
