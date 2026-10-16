"""Measure cold/warm verification latency with synthetic text and temp SQLite.

This script prints results only. It does not read or write the configured
application database or any checked-in benchmark report.
"""

import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import URL

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


RAW_TEXT = (
    "Continue lisinopril 10 mg once daily.\n\n"
    "Investigations advised:\n\n"
    "Serum Creatinine\n\n"
    "Serum Potassium"
)
WARM_REQUESTS = 5


def _measure_ms(function):
    started = time.perf_counter()
    result = function()
    return (time.perf_counter() - started) * 1000, result


def main():
    import os

    original_database_url = os.environ.get("DATABASE_URL")
    api = None
    engine = None
    try:
        with tempfile.TemporaryDirectory(prefix="hpv-api-benchmark-") as temp_dir:
            db_path = Path(temp_dir) / "benchmark.db"
            os.environ["DATABASE_URL"] = URL.create(
                "sqlite", database=str(db_path)
            ).render_as_string(hide_password=False)

            import main as api
            from fastapi.testclient import TestClient
            from src.agents.cross_check_agent import cross_check
            from src.agents.explanation_agent import explain_violations
            from src.agents.llm_parser_agent import get_parser
            from src.agents.missing_test_agent import detect_missing_tests
            from src.agents.retriever_agent import retrieve_protocol
            from src.db import SessionLocal, User, engine
            from src.prescription_extract import extract_structured_fields
            from src.config import EMBEDDING_BACKEND

            db = SessionLocal()
            benchmark_user = User(
                email="benchmark@example.invalid",
                display_name="Synthetic benchmark",
                hashed_password="not-used",
            )
            db.add(benchmark_user)
            db.commit()
            db.refresh(benchmark_user)
            user_id = benchmark_user.id
            db.close()

            api.app.dependency_overrides[api.get_current_user] = lambda: (
                SimpleNamespace(id=user_id, email="benchmark@example.invalid")
            )

            payload = {
                "raw_text": RAW_TEXT,
                "diagnosis_hint": None,
                "ordered_tests": [],
            }
            with TestClient(api.app) as client:
                cold_ms, cold_response = _measure_ms(
                    lambda: client.post("/api/verify", json=payload)
                )
                if cold_response.status_code != 200:
                    raise RuntimeError(
                        f"Cold API request failed: {cold_response.status_code}"
                    )

                warm_ms = []
                for _ in range(WARM_REQUESTS):
                    latency_ms, response = _measure_ms(
                        lambda: client.post("/api/verify", json=payload)
                    )
                    if response.status_code != 200:
                        raise RuntimeError(
                            f"Warm API request failed: {response.status_code}"
                        )
                    warm_ms.append(latency_ms)

            extraction_ms, extracted_fields = _measure_ms(
                lambda: extract_structured_fields(RAW_TEXT)
            )
            parsed_ms, parsed = _measure_ms(
                lambda: get_parser()(
                    {"raw_text": RAW_TEXT, "diagnosis_hint": None}
                )
            )
            state = {
                "raw_text": RAW_TEXT,
                "diagnosis_hint": None,
                "ordered_tests": extracted_fields["ordered_tests"],
                **parsed,
            }
            retrieval_ms, retrieved = _measure_ms(
                lambda: retrieve_protocol(state)
            )
            state.update(retrieved)
            cross_check_ms, checked = _measure_ms(lambda: cross_check(state))
            state.update(checked)
            missing_tests_ms, missing = _measure_ms(
                lambda: detect_missing_tests(state)
            )
            state.update(missing)
            explanation_ms, _ = _measure_ms(lambda: explain_violations(state))

            print(json.dumps({
                "embedding_backend": EMBEDDING_BACKEND,
                "query_type": "synthetic Lisinopril text; no patient identifiers",
                "cold_api_ms": round(cold_ms, 2),
                "warm_api_ms": [round(value, 2) for value in warm_ms],
                "warm_api_mean_ms": round(statistics.mean(warm_ms), 2),
                "warm_api_median_ms": round(statistics.median(warm_ms), 2),
                "warm_api_min_max_ms": [
                    round(min(warm_ms), 2),
                    round(max(warm_ms), 2),
                ],
                "warm_request_count": WARM_REQUESTS,
                "single_stage_sample_ms_after_warm": {
                    "prescription_extraction": round(extraction_ms, 2),
                    "parser": round(parsed_ms, 2),
                    "retrieval": round(retrieval_ms, 2),
                    "cross_check": round(cross_check_ms, 2),
                    "missing_tests": round(missing_tests_ms, 2),
                    "explanation": round(explanation_ms, 2),
                },
                "api_success": cold_response.status_code == 200,
                "pipeline_result_has_no_missing_lisinopril_tests": (
                    cold_response.json().get("missing_tests") == []
                    and missing.get("missing_tests") == []
                ),
            }, indent=2))

            api.app.dependency_overrides.clear()
            engine.dispose()
            api = None
            engine = None
    finally:
        if api is not None:
            api.app.dependency_overrides.clear()
        if engine is not None:
            engine.dispose()
        if original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_database_url


if __name__ == "__main__":
    main()
