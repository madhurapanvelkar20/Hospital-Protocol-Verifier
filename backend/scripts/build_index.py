"""
Pre-builds the retrieval index so the first Streamlit query isn't slow.

For the default "tfidf" backend this just loads and vectorizes the corpus
in-memory (nothing is persisted to disk -- it's fast enough to redo on every
app start). For the "bge" backend this downloads the embedding model and
persists embeddings to ./chroma_store so subsequent runs are fast.

Usage:
    python scripts/build_index.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import EMBEDDING_BACKEND
from src.vector_store import get_retriever, load_protocol_chunks

if __name__ == "__main__":
    chunks = load_protocol_chunks()
    print(f"Loaded {len(chunks)} protocol chunks from data/protocols/")

    retriever = get_retriever()
    print(f"Built '{EMBEDDING_BACKEND}' retriever index.")

    sample = retriever.query("hypertension ACE inhibitor monitoring")
    print("\nSample query result:")
    for r in sample:
        print(f" - [{r['score']:.2f}] {r['source']} (v{r['version']})")
