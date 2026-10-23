"""Integration check for merging mocked live FDA chunks into local retrieval."""

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


def test_retriever_merges_live_chunks_ahead_of_local_results(monkeypatch):
    monkeypatch.setattr(retriever_agent, "LIVE_FDA_RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(
        retriever_agent,
        "fetch_fda_label_chunks",
        lambda _drug: FAKE_LIVE_CHUNK,
    )
    state = {
        "raw_text": "Prescribe Metformin 500mg oral twice daily for type 2 diabetes.",
        "parsed_drugs": [{
            "name": "metformin",
            "dose": "500mg",
            "route": "oral",
            "frequency": "twice daily",
        }],
        "parsed_diagnosis": "type 2 diabetes",
    }

    result = retriever_agent.retrieve_protocol(state)

    assert result["retrieved_chunks"][0]["source"] == FAKE_LIVE_CHUNK[0]["source"]
    assert result["retrieval_confidence"] == 1.0
    assert len(result["retrieved_chunks"]) > 1
