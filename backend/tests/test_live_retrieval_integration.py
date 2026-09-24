"""
Integration check: with LIVE_FDA_RETRIEVAL_ENABLED on and live_data mocked,
confirms retrieve_protocol() actually merges live chunks into the result
-- i.e. that the wiring in retriever_agent.py works, not just live_data.py
in isolation.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.config as config
config.LIVE_FDA_RETRIEVAL_ENABLED = True

from src.agents.retriever_agent import retrieve_protocol

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
    "parsed_diagnosis": "type 2 diabetes",
}

with patch("src.agents.retriever_agent.fetch_fda_label_chunks", return_value=FAKE_LIVE_CHUNK):
    result = retrieve_protocol(state)

assert result["retrieved_chunks"][0]["source"] == "FDA Structured Product Label (live, via openFDA)", \
    f"Expected the live chunk to be merged in first, got: {result['retrieved_chunks'][0]}"
assert result["retrieval_confidence"] == 1.0
assert len(result["retrieved_chunks"]) > 1, "Expected local corpus chunks still present alongside the live one"

print("PASS: retriever_agent correctly merges live FDA chunks ahead of local corpus results when enabled")
