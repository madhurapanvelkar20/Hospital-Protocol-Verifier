"""
Central configuration for the Hospital Treatment Protocol Verifier.

EMBEDDING_BACKEND defaults to "bge" -- true hybrid retrieval (bge-large
dense embeddings + BM25 keyword scoring), matching the synopsis's stated
tech stack. This requires internet access on first run to download the
sentence-transformers model. Set EMBEDDING_BACKEND=tfidf to force the
fully-offline TF-IDF-only fallback instead (useful with no internet access,
or for quick iteration without waiting on a model download).
"""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PROTOCOLS_DIR = DATA_DIR / "protocols"
CHROMA_PERSIST_DIR = ROOT_DIR / "chroma_store"

INTERACTIONS_FILE = DATA_DIR / "interactions.json"
MONITORING_FILE = DATA_DIR / "monitoring_requirements.json"
SAMPLE_PRESCRIPTIONS_FILE = DATA_DIR / "sample_prescriptions.json"

# "bge"    (default) -> hybrid retrieval: bge-large dense embeddings (via
#            ChromaDB) fused with BM25 keyword scoring. Needs internet on
#            first run to download the embedding model.
# "tfidf"  -> scikit-learn TF-IDF only, fully offline, no model download.
EMBEDDING_BACKEND = os.environ.get("EMBEDDING_BACKEND", "bge")

# "regex" -> hardcoded-vocabulary regex parser, no API key needed, but only
#            recognizes the drugs/diagnoses listed below.
# "llm"   -> Claude-based parser, handles any drug/diagnosis in free text.
#            Requires ANTHROPIC_API_KEY. Falls back to "regex" automatically
#            if no key is set or the API call fails.
PARSER_BACKEND = os.environ.get("PARSER_BACKEND", "regex")

# If true, the Retriever Agent also queries the live openFDA drug label API
# for each parsed drug and merges any matched label sections into
# retrieved_chunks (see src/live_data.py). Off by default: it makes an
# external network call per request, and should be verified with real
# internet access before relying on it (see backend/tests/test_live_data.py).
LIVE_FDA_RETRIEVAL_ENABLED = os.environ.get("LIVE_FDA_RETRIEVAL_ENABLED", "false").lower() == "true"

# Below this retrieval confidence, the Retriever Agent reformulates the query
# and re-queries once before handing results downstream (self-correction loop).
RETRIEVAL_CONFIDENCE_THRESHOLD = 0.15

TOP_K_CHUNKS = 3

# Known drug vocabulary for the (regex-based) Prescription Parser Agent demo.
# Also used as the fallback vocabulary if the LLM parser is unavailable.
KNOWN_DRUGS = [
    "lisinopril", "metformin", "warfarin", "methotrexate",
    "simvastatin", "furosemide", "ibuprofen", "amoxicillin",
    "digoxin", "levothyroxine", "omeprazole", "clopidogrel",
    "insulin", "losartan", "prednisone", "amlodipine",
]

KNOWN_DIAGNOSES = [
    "hypertension", "type 2 diabetes", "atrial fibrillation",
    "rheumatoid arthritis", "renal impairment", "heart failure",
    "hyperlipidemia", "peptic ulcer disease", "pregnancy",
    "hypothyroidism", "gastroesophageal reflux disease",
    "coronary artery disease", "type 1 diabetes",
]
