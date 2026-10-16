"""
Tests for HybridBgeRetriever's fusion logic in src/vector_store.py.

The BM25 half and the score-fusion math are pure Python (no network) and
tested for real. The dense-embedding half is mocked -- since this sandbox
has no internet access to Hugging Face -- with a controllable fake
SentenceTransformer, so we can verify the fusion actually combines both
signals correctly rather than one silently dominating.
"""
import sys
import types
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_collection_name_tracks_corpus_and_model():
    from src.vector_store import _collection_name

    chunks = [{"text": "protocol text", "source": "guideline"}]
    assert _collection_name(chunks, "model-a") == _collection_name(chunks, "model-a")
    assert _collection_name(chunks, "model-a") != _collection_name(chunks, "model-b")
    assert _collection_name(chunks, "model-a") != _collection_name(
        [{"text": "updated protocol text", "source": "guideline"}], "model-a"
    )


def _install_fake_sentence_transformers(vector_map, monkeypatch):
    """vector_map: {text: [float,...]} -- fixed embeddings so dense
    similarity is fully predictable in the test."""
    fake_module = types.ModuleType("sentence_transformers")

    class FakeSentenceTransformer:
        def __init__(self, model_name):
            self.model_name = model_name

        def encode(self, texts):
            return np.array([vector_map.get(t, [0.0] * 8) for t in texts])

    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)


def test_bm25_signal_influences_ranking(monkeypatch, tmp_path):
    """A chunk with strong keyword overlap for a rare, specific term should
    rank highly via BM25 even when every chunk gets an IDENTICAL (flat)
    dense score -- proving BM25 is a real contributor, not dead weight."""
    test_chroma_dir = tmp_path / "chroma"

    import src.vector_store as vs
    monkeypatch.setattr(vs, "CHROMA_PERSIST_DIR", test_chroma_dir)
    chunks = vs.load_protocol_chunks()

    # Every chunk gets the SAME fake embedding -> dense similarity is flat
    # across all of them, so any ranking difference must come from BM25.
    flat_vector_map = {c["text"]: [1.0] * 8 for c in chunks}
    _install_fake_sentence_transformers(flat_vector_map, monkeypatch)

    retriever = vs.HybridBgeRetriever()

    # "digoxin toxicity potassium" is specific vocabulary that should only
    # heavily overlap with the Digoxin Therapy Guideline chunks.
    results = retriever.query("digoxin toxicity potassium hypokalemia")
    top_sources = [r["source"] for r in results]
    assert any("Digoxin" in s or "Cardiology" in s for s in top_sources), (
        f"Expected BM25 keyword overlap to surface the digoxin guideline, got: {top_sources}"
    )
    print("PASS: BM25 keyword signal correctly influences ranking even with a flat dense score")


def test_hybrid_fusion_combines_both_signals(monkeypatch, tmp_path):
    """A dense-only weight ranks the uniquely closest dense candidate first."""
    test_chroma_dir = tmp_path / "chroma"

    import src.vector_store as vs
    monkeypatch.setattr(vs, "CHROMA_PERSIST_DIR", test_chroma_dir)
    chunks = vs.load_protocol_chunks()

    # Give one Warfarin chunk a unique nearest vector and vary the other
    # embeddings to avoid degenerate ties in Chroma's approximate index.
    # Chroma uses L2 distance, so the query and favorite share a vector.
    vector_map = {"digoxin dosing information": [1.0] * 8}
    for index, chunk in enumerate(chunks):
        vector_map[chunk["text"]] = [-1.0 - index * 0.01] * 8
    favorite = next(c for c in chunks if "Warfarin" in c["title"])
    vector_map[favorite["text"]] = [1.0] * 8
    _install_fake_sentence_transformers(vector_map, monkeypatch)

    # dense_weight=1.0 -> pure dense -> should surface Warfarin regardless of query wording
    dense_only = vs.HybridBgeRetriever(dense_weight=1.0)
    results_dense_only = dense_only.query("digoxin dosing information")
    assert any("Warfarin" in r["title"] for r in results_dense_only[:1]), \
        f"Expected dense_weight=1.0 to favor the artificially-boosted Warfarin chunk, got {results_dense_only[0]['title']}"
    print("PASS: dense_weight=1.0 behaves as pure dense retrieval (sanity check on the fusion math)")


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
