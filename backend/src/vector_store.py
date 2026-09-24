"""
Loads the protocol corpus, chunks it by section, and provides a retrieval
function over it.

Two backends are supported (see src/config.py -> EMBEDDING_BACKEND):

  - "bge"   (default): TRUE hybrid retrieval -- dense semantic similarity
    via sentence-transformers BAAI/bge-large-en-v1.5 embeddings persisted
    in ChromaDB, fused with BM25 keyword scoring (rank_bm25) over the same
    corpus. This is what the project synopsis commits to ("ChromaDB with
    bge-large embeddings; hybrid dense + BM25 retrieval"). Requires
    internet access on first run to download the embedding model.

  - "tfidf": scikit-learn TF-IDF + cosine similarity only. Fully offline,
    no model download required -- kept as a fallback for environments
    with no internet access (e.g. this sandbox), or for quick testing.

Every chunk carries its source guideline name, version, and specialty as
metadata, so the Retriever Agent can return a proper citation, not just text.
"""

import re
from pathlib import Path
from typing import List, Dict, Any

import yaml  # PyYAML, used only to parse the simple frontmatter block

from src.config import PROTOCOLS_DIR, EMBEDDING_BACKEND, CHROMA_PERSIST_DIR, TOP_K_CHUNKS


def _parse_frontmatter(text: str) -> (Dict[str, Any], str):
    """Split a '---\\nkey: value\\n---\\nbody' markdown file into (metadata, body)."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        return {}, text
    meta = yaml.safe_load(match.group(1)) or {}
    return meta, match.group(2)


def _chunk_body(body: str) -> List[str]:
    """Chunk a protocol document by its '## Section' headers."""
    parts = re.split(r"\n(?=## )", body.strip())
    return [p.strip() for p in parts if p.strip()]


def load_protocol_chunks() -> List[Dict[str, Any]]:
    """Read every .md file in data/protocols and return a flat list of chunks."""
    chunks = []
    for path in sorted(Path(PROTOCOLS_DIR).glob("*.md")):
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        for section in _chunk_body(body):
            chunks.append({
                "text": section,
                "title": meta.get("title", path.stem),
                "source": meta.get("source", path.stem),
                "version": meta.get("version", "unknown"),
                "specialty": meta.get("specialty", "General"),
            })
    return chunks


class TfidfRetriever:
    """Offline fallback retrieval backend: TF-IDF + cosine similarity only."""

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.chunks = load_protocol_chunks()
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform([c["text"] for c in self.chunks])

    def query(self, text: str, top_k: int = TOP_K_CHUNKS) -> List[Dict[str, Any]]:
        from sklearn.metrics.pairwise import cosine_similarity

        if not text.strip():
            return []
        query_vec = self.vectorizer.transform([text])
        scores = cosine_similarity(query_vec, self.matrix)[0]
        ranked = sorted(zip(scores, self.chunks), key=lambda x: x[0], reverse=True)
        results = []
        for score, chunk in ranked[:top_k]:
            results.append({**chunk, "score": float(score)})
        return results


def _minmax_normalize(scores: Dict[int, float]) -> Dict[int, float]:
    """Scales a {chunk_index: raw_score} dict to [0, 1] so dense and BM25
    scores -- which live on totally different numeric scales -- can be
    fused with a simple weighted sum. A flat/empty score set maps to 0.0
    for every entry rather than dividing by zero."""
    if not scores:
        return {}
    values = list(scores.values())
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return {k: 0.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


class HybridBgeRetriever:
    """
    True hybrid retrieval: dense bge-large embeddings (via ChromaDB) fused
    with BM25 keyword scoring (via rank_bm25) over the same local corpus.

    On each query:
      1. Dense candidates come from ChromaDB's nearest-neighbor search
         over bge-large embeddings (semantic similarity).
      2. BM25 candidates come from an in-memory BM25Okapi index built once
         at startup over every chunk (keyword/lexical overlap).
      3. Both candidate sets are min-max normalized to [0, 1] and combined
         as a weighted sum (default: equal weight), then re-ranked --
         this is what makes it "hybrid" rather than dense-only.

    Requires internet access on first run to download the bge-large model
    from Hugging Face; embeddings are then persisted in
    CHROMA_PERSIST_DIR so subsequent runs don't re-embed the corpus.
    """

    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5", dense_weight: float = 0.5,
                 dense_candidates: int = 10):
        import chromadb
        from sentence_transformers import SentenceTransformer
        from rank_bm25 import BM25Okapi

        self.dense_weight = dense_weight
        self.bm25_weight = 1.0 - dense_weight
        self.dense_candidates = dense_candidates

        self.chunks = load_protocol_chunks()

        # --- BM25 keyword index (in-memory, no external service) ---
        tokenized_corpus = [c["text"].lower().split() for c in self.chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)

        # --- dense embeddings, persisted in ChromaDB ---
        self.model = SentenceTransformer(model_name)
        self.client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
        self.collection = self.client.get_or_create_collection("protocols")

        if self.collection.count() == 0:
            embeddings = self.model.encode([c["text"] for c in self.chunks]).tolist()
            self.collection.add(
                ids=[str(i) for i in range(len(self.chunks))],
                embeddings=embeddings,
                documents=[c["text"] for c in self.chunks],
                metadatas=[{k: v for k, v in c.items() if k != "text"} for c in self.chunks],
            )

    def query(self, text: str, top_k: int = TOP_K_CHUNKS) -> List[Dict[str, Any]]:
        if not text.strip():
            return []

        # --- dense candidates: top-N nearest neighbors by bge embedding ---
        query_embedding = self.model.encode([text]).tolist()
        n_results = min(self.dense_candidates, len(self.chunks))
        dense_res = self.collection.query(query_embeddings=query_embedding, n_results=n_results)

        dense_scores: Dict[int, float] = {}
        for doc_id, distance in zip(dense_res["ids"][0], dense_res["distances"][0]):
            dense_scores[int(doc_id)] = 1.0 - float(distance)

        # --- BM25 candidates: keyword overlap score for every chunk ---
        bm25_raw = self.bm25.get_scores(text.lower().split())
        # only keep the same-size top-N pool as the dense side, so a
        # single retrieval doesn't get flooded with near-zero BM25 noise
        bm25_top_idx = sorted(range(len(bm25_raw)), key=lambda i: bm25_raw[i], reverse=True)[:n_results]
        bm25_scores = {i: float(bm25_raw[i]) for i in bm25_top_idx}

        # --- fuse: union of both candidate pools, each side normalized to [0,1] ---
        dense_norm = _minmax_normalize(dense_scores)
        bm25_norm = _minmax_normalize(bm25_scores)

        candidate_ids = set(dense_norm) | set(bm25_norm)
        fused = {
            i: self.dense_weight * dense_norm.get(i, 0.0) + self.bm25_weight * bm25_norm.get(i, 0.0)
            for i in candidate_ids
        }

        ranked_ids = sorted(fused, key=lambda i: fused[i], reverse=True)[:top_k]
        return [{**self.chunks[i], "score": fused[i]} for i in ranked_ids]


_retriever_instance = None


def get_retriever():
    """Lazily construct the configured retriever backend (singleton)."""
    global _retriever_instance
    if _retriever_instance is None:
        if EMBEDDING_BACKEND == "tfidf":
            _retriever_instance = TfidfRetriever()
        else:
            _retriever_instance = HybridBgeRetriever()
    return _retriever_instance
