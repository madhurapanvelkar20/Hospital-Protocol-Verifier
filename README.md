# Hospital Treatment Protocol Verifier — React + FastAPI (v4)

Adds authentication, a per-user verification history, and a full
multi-page site (Home, About, Login, Signup, Verifier, History) on top of
v3 (live data sources, hybrid bge-large + BM25 retrieval). The core
5-agent pipeline is untouched — this update is entirely about turning the
single-screen tool into a proper application.

## What's new: authentication + multi-page site

### Backend (`backend/src/auth.py`, `backend/src/db.py`)

- **Password hashing**: `bcrypt`, called directly rather than through
  `passlib` — `passlib`'s bundled bcrypt handler has a known compatibility
  bug with modern `bcrypt` versions (its own internal self-test throws an
  `AttributeError`/`ValueError` on import), confirmed while building this,
  so it's avoided entirely rather than pinned around.
- **Sessions**: JWT access tokens (`python-jose`), 7-day expiry, sent as a
  `Bearer` token and verified on every protected request.
- **Storage**: SQLite via SQLAlchemy (`backend/hpv.db`, created
  automatically on first run) — no external DB server needed, appropriate
  for a student project or exhibition demo.
- **New endpoints**: `POST /api/auth/signup`, `POST /api/auth/login`,
  `GET /api/auth/me`, `GET /api/history`. `POST /api/verify` now requires
  a valid token and automatically saves the run to that user's history.

**Security note for anyone deploying this beyond your own machine**:
`JWT_SECRET_KEY` defaults to a fixed placeholder so the app runs
out of the box. That means every install shares the same token-signing
key. Set a real, random `JWT_SECRET_KEY` environment variable before
deploying this anywhere other than localhost.

### Frontend (`frontend/src/pages/`, `frontend/src/context/AuthContext.jsx`)

Five pages now, wired with `react-router-dom`:

| Page | Route | Auth required? |
|---|---|---|
| Home | `/` | No |
| About | `/about` | No |
| Login | `/login` | No |
| Signup | `/signup` | No |
| Verifier | `/verify` | Yes |
| History | `/history` | Yes |

`ProtectedRoute.jsx` redirects to `/login` if you try to visit `/verify`
or `/history` while logged out. `AuthContext.jsx` holds the current
user/token, persisted to `localStorage` so refreshing the page doesn't
log you out, and re-validates the token against the server on load (so an
expired token gets cleared rather than silently failing later).

The History page reuses the exact same result-display components as the
Verifier page (`ParsedDrugsTable`, `CitationList`, `ReportPanel`,
`ResultBanner`), so a past run looks identical to a fresh one — click any
entry to expand it.

I also added the per-citation confidence score back into the "Matched
guideline" card (`chunk.score`) — it had been dropped during the earlier
UI redesign that removed the pipeline rail.

## Setup

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Visit the site, click **Sign up**, create an account, and you'll land on
the Verifier page. Everything you run there will show up on the History
page.

**New dependencies to be aware of**: `sqlalchemy`, `bcrypt`,
`python-jose[cryptography]`, `email-validator` (backend);
`react-router-dom` (frontend) — all already in `requirements.txt` /
`package.json`, just flagging them since they weren't there before.

## Tested before delivery

- Full auth flow against the real running backend: signup → login →
  protected `/api/verify` (confirmed 401 without a token) → `/api/history`
  showing the saved run → wrong-password rejection (401) →
  duplicate-signup rejection (400).
- `npm run build` — clean compile, no errors.
- Both servers running together, hit over real HTTP (not just imports).

**Not tested**: the actual browser UI (login form submission, redirect
behavior, the History page's expand/collapse) — this sandbox has no
browser to click through. The backend API and the frontend build are both
verified solid; please click through the pages yourself once before
demoing, the same way you did for the live-data features earlier.

---

## Retrieval upgrade: TF-IDF → real hybrid (bge-large + BM25) is now the default

`backend/src/vector_store.py`'s `HybridBgeRetriever` replaces the earlier
dense-only `BgeChromaRetriever`. It now matches the synopsis's stated tech
stack literally ("ChromaDB with bge-large embeddings; hybrid dense + BM25
retrieval") rather than partially:

- **Dense side**: sentence-transformers `BAAI/bge-large-en-v1.5`
  embeddings, persisted in a local ChromaDB collection.
- **Keyword side**: BM25 (via `rank_bm25`, already a listed dependency
  that was previously unused dead weight — it's now actually doing
  something).
- **Fusion**: both candidate pools are min-max normalized to [0, 1] and
  combined as a weighted sum (default: equal weight), then re-ranked.
  This is what makes it genuinely "hybrid" rather than dense-only with a
  hybrid label slapped on it.

`EMBEDDING_BACKEND` in `backend/src/config.py` now defaults to `"bge"`.
Set it to `"tfidf"` (or `export EMBEDDING_BACKEND=tfidf`) to force the
fully-offline fallback — useful with no internet access, or for fast
iteration without waiting on a model download.

**First run needs internet access** to download the bge-large model
(~1.3GB) from Hugging Face; after that, embeddings are cached in
`backend/chroma_store/` so subsequent runs are fast. **I could not test
this end-to-end myself** — this sandbox can't reach Hugging Face — so
please run it yourself once with real internet access and confirm
retrieval quality looks right before demoing it. What I *did* verify:
the BM25 half and the score-fusion math are tested for real (no
mocking needed, since both are pure Python), and the ChromaDB
add/query wiring was verified with a mocked embedding model in an
earlier round — see `backend/tests/test_hybrid_retriever.py`.

A fast way to sanity-check it once it's running: hit
`http://localhost:8000/api/health` — it reports
`"embedding_backend": "bge"` (or `"tfidf"`) so you can confirm which
backend is actually active, the same way you already used it to debug
the live-FDA flag earlier.

## What's new: live data sources (`backend/src/live_data.py`)

**Why not PubMed as the primary source:** PubMed indexes research paper
abstracts, not clinical treatment protocols. An abstract is evidence, not
a guideline — citing one as if it were hospital protocol would be
misleading. So this update uses two sources, each used for what it's
actually good for:

### 1. openFDA Drug Label API — live guideline-style retrieval

`fetch_fda_label_chunks(drug_name)` queries `api.fda.gov/drug/label.json`
for a drug's real FDA prescribing information (indications, dosing,
warnings, drug interactions, boxed warnings) and returns it in the exact
same chunk shape as the local corpus — so it merges directly into
`retrieved_chunks` with **no frontend changes needed**; the existing
"Matched guideline" citation card just displays it.

Enable with an environment variable:
```bash
export LIVE_FDA_RETRIEVAL_ENABLED=true    # Windows: set LIVE_FDA_RETRIEVAL_ENABLED=true
```

When enabled, the Retriever Agent queries openFDA for every parsed drug
and merges any matched label sections in ahead of the local corpus
results (treated as a direct hit, not ranked against local scores, since
it's an exact drug-name match rather than a similarity guess).

### 2. PubMed (NCBI E-utilities) — supporting literature, not a citation

`search_pubmed_literature(query)` returns a short list of related article
titles/PMIDs/links. This is deliberately **not** wired into
`retrieved_chunks` or treated as a guideline citation — it's exposed as a
separate function you can call for "related literature" context, kept
apart from the pipeline's actual violation-detection logic so a research
abstract never gets treated as clinical authority.

## Honest limitation — please read before demoing this

**I could not test either live API end-to-end from this environment.**
This sandbox's network is restricted to package registries and can't
reach `api.fda.gov` or `eutils.ncbi.nlm.nih.gov`. What I did verify:

- The exact field names and response shape, against openFDA's and NCBI's
  official documentation
- The parsing logic, against mocked responses shaped like those real
  schemas (`backend/tests/test_live_data.py`)
- That `retriever_agent.py` correctly merges live chunks in when the flag
  is on (`backend/tests/test_live_retrieval_integration.py`, also mocked)

**You need to verify the real live call yourself** before relying on it
for a demo:
```bash
cd backend
pip install requests
python tests/test_live_data.py --live
```
This hits the real openFDA and PubMed APIs for a known drug and prints
what comes back, so you can eyeball it before trusting it in front of
your teacher. If openFDA's query syntax has changed, or a drug name
doesn't match their `generic_name` field exactly, this is where you'd
find out and adjust `live_data.py`'s query construction.

## Everything else from v2 is unchanged

- 16-drug corpus, synthetic benchmark, LLM parser — see the earlier
  README sections (still applicable) and `backend/benchmark/README.md`
  for the benchmark's honest limitations.
- Setup commands are unchanged:
  ```bash
  # Terminal 1
  cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000
  # Terminal 2
  cd frontend && npm install && npm run dev
  ```
  Note: the first `uvicorn` run will now download the bge-large model —
  expect it to take longer than before on first start.

## What's still not done

- The benchmark (`backend/benchmark/run_evaluation.py`) still runs
  against whichever `EMBEDDING_BACKEND` is active. If you run it without
  internet access, set `EMBEDDING_BACKEND=tfidf` first or it'll try (and
  fail) to download the bge-large model.
- Live-API results haven't been folded into the synthetic benchmark —
  the benchmark still only exercises the local corpus and knowledge
  base. Extending it to also test live-mode retrieval (with the live
  calls mocked, for reproducibility) would be a good next step.
- PubMed results aren't surfaced in the frontend yet — currently backend-only.
- Real plain-LLM / plain-RAG baselines for the evaluation harness (same
  gap noted in v2).
- Held-out benchmark cases independent of `interactions.json` (same gap
  noted in v2).
