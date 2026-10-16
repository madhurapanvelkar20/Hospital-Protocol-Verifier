"""Compare TF-IDF with the real BGE/Chroma + BM25 retriever.

Judgments are protocol-title relevance labels, not clinical-validation labels.
This script prints results only and never overwrites the checked-in synthetic
rule-regression report.
"""

import json
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.vector_store import HybridBgeRetriever, TfidfRetriever

JUDGMENTS_FILE = Path(__file__).resolve().parent / "retrieval_judgments.json"
CUTOFF = 5


def _ranked_unique_titles(results):
    titles = []
    seen = set()
    for result in results:
        title = result["title"]
        if title not in seen:
            titles.append(title)
            seen.add(title)
    return titles


def _metrics(retriever, cases, initialization_seconds):
    timings_ms = []
    query_metrics = []
    retriever.query(cases[0]["query"], top_k=10)

    for case in cases:
        start = time.perf_counter()
        results = retriever.query(case["query"], top_k=10)
        timings_ms.append((time.perf_counter() - start) * 1000)
        ranked_titles = _ranked_unique_titles(results)[:CUTOFF]
        relevant = set(case["relevant_titles"])
        hits = [title for title in ranked_titles if title in relevant]
        reciprocal_rank = (
            1.0 / (ranked_titles.index(hits[0]) + 1) if hits else 0.0
        )
        dcg = sum(
            1.0 / math.log2(rank + 2)
            for rank, title in enumerate(ranked_titles)
            if title in relevant
        )
        ideal_hits = min(len(relevant), CUTOFF)
        idcg = sum(1.0 / math.log2(rank + 2) for rank in range(ideal_hits))
        query_metrics.append({
            "precision_at_5": len(hits) / CUTOFF,
            "recall_at_5": len(hits) / len(relevant),
            "mrr_at_5": reciprocal_rank,
            "ndcg_at_5": dcg / idcg if idcg else 0.0,
        })

    ordered_times = sorted(timings_ms)
    p95_index = max(0, math.ceil(0.95 * len(ordered_times)) - 1)
    metric_names = query_metrics[0]
    return {
        "initialization_seconds": round(initialization_seconds, 3),
        "query_latency_ms_mean": round(statistics.mean(timings_ms), 2),
        "query_latency_ms_median": round(statistics.median(timings_ms), 2),
        "query_latency_ms_p95": round(ordered_times[p95_index], 2),
        **{
            name: round(statistics.mean(row[name] for row in query_metrics), 3)
            for name in metric_names
        },
    }


def _initialize(factory):
    start = time.perf_counter()
    retriever = factory()
    return retriever, time.perf_counter() - start


if __name__ == "__main__":
    cases = json.loads(JUDGMENTS_FILE.read_text(encoding="utf-8"))
    bge, bge_init_seconds = _initialize(HybridBgeRetriever)
    tfidf, tfidf_init_seconds = _initialize(TfidfRetriever)
    print(json.dumps({
        "queries": len(cases),
        "cutoff": CUTOFF,
        "judgment_basis": "retrieved guideline title; not clinical validation",
        "bge_chroma_bm25": _metrics(bge, cases, bge_init_seconds),
        "tfidf": _metrics(tfidf, cases, tfidf_init_seconds),
    }, indent=2))
