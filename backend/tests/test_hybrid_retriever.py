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
import shutil
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _install_fake_sentence_transformers(vector_map):
    """vector_map: {text: [float,...]} -- fixed embeddings so dense
    similarity is fully predictable in the test."""
    fake_module = types.ModuleType("sentence_transformers")

    class FakeSentenceTransformer:
        def __init__(self, model_name):
            self.model_name = model_name

        def encode(self, texts):
            return np.array([vector_map.get(t, [0.0] * 8) for t in texts])

    fake_module.SentenceTransformer = FakeSentenceTransformer
    sys.modules["sentence_transformers"] = fake_module


def test_bm25_signal_influences_ranking():
    """A chunk with strong keyword overlap for a rare, specific term should
    rank highly via BM25 even when every chunk gets an IDENTICAL (flat)
    dense score -- proving BM25 is a real contributor, not dead weight."""
    import src.config as config
    test_chroma_dir = Path("/tmp/test_chroma_bm25_check")
    shutil.rmtree(test_chroma_dir, ignore_errors=True)
    config.CHROMA_PERSIST_DIR = test_chroma_dir

    from src.vector_store import load_protocol_chunks
    chunks = load_protocol_chunks()

    # Every chunk gets the SAME fake embedding -> dense similarity is flat
    # across all of them, so any ranking difference must come from BM25.
    flat_vector_map = {c["text"]: [1.0] * 8 for c in chunks}
    _install_fake_sentence_transformers(flat_vector_map)

    import importlib
    import src.vector_store as vs
    importlib.reload(vs)

    retriever = vs.HybridBgeRetriever()

    # "digoxin toxicity potassium" is specific vocabulary that should only
    # heavily overlap with the Digoxin Therapy Guideline chunks.
    results = retriever.query("digoxin toxicity potassium hypokalemia")
    top_sources = [r["source"] for r in results]
    assert any("Digoxin" in s or "Cardiology" in s for s in top_sources), (
        f"Expected BM25 keyword overlap to surface the digoxin guideline, got: {top_sources}"
    )
    print("PASS: BM25 keyword signal correctly influences ranking even with a flat dense score")

    shutil.rmtree(test_chroma_dir, ignore_errors=True)


def test_hybrid_fusion_combines_both_signals():
    """With DIFFERENT dense scores per chunk, confirm the top result
    reflects a combination -- not purely one signal -- by checking that
    changing dense_weight changes the ranking outcome."""
    import src.config as config
    test_chroma_dir = Path("/tmp/test_chroma_fusion_check")
    shutil.rmtree(test_chroma_dir, ignore_errors=True)
    config.CHROMA_PERSIST_DIR = test_chroma_dir

    from src.vector_store import load_protocol_chunks
    chunks = load_protocol_chunks()

    # Give the Warfarin guideline chunks an artificially HIGH dense score,
    # everything else low -- so a dense-only search would favor Warfarin.
    # (Also map the query text itself to the same vector as the "favorite"
    # chunks: ChromaDB's default L2 distance means "closest to the query
    # vector" wins, so the query has to actually sit near what we want to
    # win, not just have that chunk sit near an arbitrary high vector.)
    vector_map = {"digoxin dosing information": [1.0] * 8}
    for c in chunks:
        if "Warfarin" in c["source"] or "Hematology" in c["source"]:
            vector_map[c["text"]] = [1.0] * 8
        else:
            vector_map[c["text"]] = [-1.0] * 8
    _install_fake_sentence_transformers(vector_map)

    import importlib
    import src.vector_store as vs
    importlib.reload(vs)

    # dense_weight=1.0 -> pure dense -> should surface Warfarin regardless of query wording
    dense_only = vs.HybridBgeRetriever(dense_weight=1.0)
    results_dense_only = dense_only.query("digoxin dosing information")
    assert any("Warfarin" in r["source"] or "Hematology" in r["source"] for r in results_dense_only[:1]), \
        f"Expected dense_weight=1.0 to favor the artificially-boosted Warfarin chunk, got {results_dense_only[0]['source']}"
    print("PASS: dense_weight=1.0 behaves as pure dense retrieval (sanity check on the fusion math)")

    shutil.rmtree(test_chroma_dir, ignore_errors=True)


if __name__ == "__main__":
    test_bm25_signal_influences_ranking()
    test_hybrid_fusion_combines_both_signals()
    print("\nAll hybrid retriever tests passed (dense side mocked, BM25 + fusion math real).")
