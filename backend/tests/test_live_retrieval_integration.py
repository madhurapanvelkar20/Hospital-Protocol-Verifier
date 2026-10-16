"""
Integration check: with LIVE_FDA_RETRIEVAL_ENABLED on and live_data mocked,
confirms retrieve_protocol() actually merges live chunks into the result
-- i.e. that the wiring in retriever_agent.py works, not just live_data.py
in isolation.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.agents.retriever_agent as retriever_agent

FAKE_LIVE_CHUNK = [{
    "text": "Lactic acidosis is a rare but serious complication of metformin therapy...",
    "title": "Glucophage — Warnings (FDA Label)",
    "source": "FDA Structured Product Label (live, via openFDA)",
    "version": "2023-04-15",
    "specialty": "FDA Regulatory Labeling",
    "score": 1.0,
}]

state = {
    "raw_text": "Prescribe Metformin 500mg oral twice daily for type 2 diabetes.",
    "parsed_drugs": [{"name": "metformin", "dose": "500mg", "route": "oral", "frequency": "twice daily"}],
    "parsed_diagnoses": ["type 2 diabetes"],
}

def test_live_fda_chunks_merge_ahead_of_local_results(monkeypatch):
    monkeypatch.setattr(retriever_agent, "LIVE_FDA_RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(
        retriever_agent,
        "fetch_fda_label_chunks_with_status",
        lambda _: (FAKE_LIVE_CHUNK, None),
    )

    result = retriever_agent.retrieve_protocol(state)

    assert result["retrieved_chunks"][0]["source"] == "FDA Structured Product Label (live, via openFDA)"
    assert result["retrieval_confidence"] == 1.0
    assert len(result["retrieved_chunks"]) > 1
