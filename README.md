# Hospital Treatment Protocol Verifier — React + FastAPI (v6)

Fixes a real limitation found while testing with an actual prescription
photo: the system could only handle **one** diagnosis, and OCR'd photos
required manually retyping the diagnosis and tests even when the
prescription stated them clearly. Also added 2 drugs (Telmisartan,
Atorvastatin) that a real test prescription used but weren't in the
vocabulary yet.

## Multiple diagnoses, in one pipeline run (not N separate runs)

Previously `parsed_diagnosis` was a single string — a prescription
treating two conditions at once (e.g. hypertension **and** type 2
diabetes, extremely common) could only be checked against one of them,
silently ignoring contraindications against the other.

Fixed properly, not just patched at the UI layer: `VerifierState` now
carries `parsed_diagnoses` (a list), and `cross_check_agent.py` checks
**every parsed drug against every parsed diagnosis** in a single pass —
this was the "run the pipeline for each diagnosis" idea from the
request, done more efficiently as one combined check rather than
duplicating retrieval and citation work per diagnosis. The Diagnosis
field now accepts a comma-separated list (`hypertension, type 2
diabetes`), and both the regex parser and the LLM parser were updated to
match. Both `parser_agent.py` and `llm_parser_agent.py` also dedupe
overlapping matches now (e.g. a hint of "type 2 diabetes mellitus" no
longer also lists "type 2 diabetes" as a separate entry).

**Verified with your actual prescription's content** (recreated as a
test image, since I can't access your uploaded file directly): all 4
drugs parsed correctly, both diagnoses captured in one pipeline run,
and all 3 missing-test violations correctly flagged.

## OCR auto-fill for diagnosis + tests ordered (not just drug text)

Previously, uploading a photo only filled the free-text prescription
box — diagnosis and tests still had to be typed by hand even when the
prescription had clear "DIAGNOSIS" and "TESTS ORDERED" sections (like
your Sunrise Medical Centre example).

New: `src/prescription_extract.py` looks for those section headers in
the OCR'd text and extracts every line listed under them — handling
numbered lists, bullets, and dashes, and correctly stopping at the next
section even with no blank line separating them. If no explicit section
is found, diagnosis extraction falls back to the same keyword-matching
approach the regex parser already uses; there's no fallback for tests,
since there's no fixed vocabulary of lab test names to guess from — it's
left blank for you to fill in rather than guessed.

`/api/ocr` now returns `diagnoses` and `ordered_tests` alongside the
extracted text, and the frontend auto-fills the Diagnosis and Tests
Already Ordered fields from them — **all of it remains fully editable**
before you click Run verification, same principle as the raw text
itself: OCR/extraction mistakes are exactly what this project exists to
catch, not introduce silently.

6 new tests in `backend/tests/test_prescription_extract.py`, all passing,
including a regression case for sections with no blank line between them
(caught this exact bug while building it).

## Two drugs added: Telmisartan, Atorvastatin

Your real test prescription used both, and neither was in the system's
16-drug vocabulary — silently dropping 2 of 4 drugs would have been a
confusing first impression. Both now have full guideline documents,
monitoring requirements, and an interaction rule each (Telmisartan +
Lisinopril: dual RAS blockade, same pattern as the existing Losartan
rule). Vocabulary is now 18 drugs.

## Setup (unchanged)

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

## Tested before delivery

- **30+ tests across 8 files, all passing** — added `test_prescription_extract.py` (6 tests),
  updated `test_llm_parser.py` and `test_live_retrieval_integration.py` for the plural
  diagnosis field, all others re-verified clean.
- Full real-world scenario test: a recreated version of your actual
  prescription (4 drugs including the 2 new ones, 2 diagnoses, 1 test)
  run through the complete stack — OCR → structured extraction → parse →
  retrieve → cross-check → missing-test → explain → save to history — via
  FastAPI's TestClient (exercises the real HTTP request/response stack,
  not just direct function calls).
- `npm run build` — clean compile, no errors.
- Benchmark re-run clean (48/48 cases, no regression from the diagnosis
  field refactor).

---

Addresses four things flagged as prototype-only, with a path toward a
real system: a configurable production database, a real (not
hand-written) drug interaction data source, an OCR photo-upload feature,
a visible confidence indicator, and an About page rewritten for end
users instead of engineers.

## 1. Database: SQLite → PostgreSQL, configurable

**Migration status:** PostgreSQL requires explicit Alembic schema migrations and has an opt-in SQLite copy script. The earlier setup snippet in this historical section predates that workflow; use [the PostgreSQL migration guide](./docs/POSTGRESQL_MIGRATION.md) for current environment configuration, data preservation, migration, and regression-test instructions. SQLite-only tests do not verify PostgreSQL behavior; run the opt-in integration test against a dedicated disposable database.

**Why not MongoDB** (addressing this directly, since it's a reasonable
question): this data is inherently relational — every verification
belongs to exactly one user via a foreign key, and a real deployment
would add more linked tables (per-hospital corpora, audit logs). A
relational database enforces that relationship at the DB level; a
document store leaves it to application code to get right every time.
MongoDB is the right tool for document-shaped or massive-horizontal-scale
data, neither of which applies here.

**What actually needed fixing**: SQLite is a single file, not a server —
fine for one process (a demo), but it doesn't support concurrent writes
from multiple backend instances, which any real multi-user deployment
needs. The fix is SQLite → **PostgreSQL**, both relational, via one
environment variable:

```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/hpv
python -m pip install "psycopg[binary]>=3.1.18" alembic
```

Leave PostgreSQL configuration unset to keep SQLite as the local/demo
default. Existing SQLite data is never copied automatically. Apply
Alembic migrations explicitly and follow the migration guide before
switching a deployment to PostgreSQL.

## 2. Interaction data: 15 hand-written rules → a real ingestion pipeline

Fifteen manually-authored rules doesn't scale, and hand-writing more
doesn't fix that — it's the same non-scalable approach, just bigger. The
real fix is a **pipeline that ingests a real, curated interaction
database**, not more manual entries.

**Source**: [DDInter 2.0](https://ddinter2.scbdd.com/) — a free,
pharmacist-curated database covering 2,310 drugs and 302,516 interaction
records with severity, mechanism, and management annotations (Tian et
al., 2025, *Nucleic Acids Research*). CC BY-NC-SA 4.0 licensed — fine for
this academic project; a commercial deployment would need a differently
licensed source (e.g. DrugBank or First Databank under a commercial
license).

```bash
# 1. Download from https://ddinter.scbdd.com/download/
# 2. Run:
cd backend
python scripts/ingest_ddinter.py path/to/ddinter_export.csv
# 3. Restart the backend -- cross_check_agent.py merges the result in automatically
```

**Honest limitation**: this build environment has no internet access to
`ddinter2.scbdd.com`, so the real CSV could not be downloaded and
ingested here. What's verified: the mapping/filtering/severity-normalizing
logic, tested against a synthetic CSV shaped like DDInter's documented
columns (`backend/tests/test_ddinter_ingest.py`, 4 tests passing), and
that `cross_check_agent.py` correctly merges an ingested file in when
present and falls back cleanly when it's not (tested with a real
end-to-end pipeline run). **You need to download the real file yourself
and confirm the column names match** — the script prints the headers it
found and refuses to guess if they don't, since a wrong drug-pair mapping
here is a patient-safety bug, not a cosmetic one.

## 3. Other parameters worth improving for a real system (not all implemented — prioritized)

**High priority — accuracy/safety:**
- **Guideline corpus scale**: 16 hand-written documents is a demo, not
  production coverage. A real system needs either a licensed guideline
  database or a document-ingestion pipeline (PDF/HTML parsing) over a
  hospital's actual protocol library.
- **Parsing robustness**: the regex parser only knows 16 drug names; even
  the LLM-based parser hasn't been validated against messy, real-world
  clinical shorthand. A real system would use a clinical NER model
  (e.g. scispaCy, MedCAT) trained/validated on real prescription text.
- **Multi-drug interaction checking**: currently pairwise only. A patient
  on 4+ drugs has combinatorial risk the current Cross-Check Agent
  doesn't fully capture.
- **Real evaluation baselines**: the benchmark still only compares
  against `no_agent` and `retrieval_only` floors, not the plain-LLM /
  plain-RAG baselines the project synopsis calls for.

**High priority — security & compliance** (genuinely required before any
real deployment, not just nice-to-have):
- `JWT_SECRET_KEY` currently defaults to a placeholder — must be set to a
  real secret, ideally via a secrets manager, not an env var in plaintext.
- No rate limiting on `/api/auth/login` — currently vulnerable to
  brute-force password guessing.
- No email verification or password-reset flow.
- No audit logging (who viewed what, when) — a real clinical system
  needs this for compliance, separate from the verification history
  feature (which is for the user, not for compliance audit trails).
- No encryption-at-rest configuration for the database.
- HIPAA (or equivalent local regulatory) compliance review — this
  project currently makes no claims about handling real patient data
  safely, and shouldn't be used with real patient information as-is.

**Medium priority — scale & reliability:**
- Caching for repeated retrieval queries (currently re-embeds/re-queries
  every time).
- Async/background processing for OCR and LLM-parser calls, so a slow
  external call doesn't block the request thread.
- Structured logging and error monitoring (nothing currently captures
  failures beyond what prints to the terminal).
- Containerization (Docker) and a documented deployment process — right
  now this only runs via two manually-started dev servers.

**Lower priority — polish:**
- Held-out benchmark cases independent of the interaction data source,
  for a genuinely generalizable accuracy number.
- PubMed results surfaced in the frontend (currently backend-only).

## 4. OCR photo upload

Upload a photo of a prescription — Tesseract extracts the text, which
you **review and edit before running verification** (never auto-submitted,
since a misread drug name is exactly the kind of error this project
exists to catch, not introduce).

**Requires the Tesseract OCR engine installed separately** from the
Python `pytesseract` package (which just wraps the `tesseract` binary):

- **Windows**: download the installer from
  https://github.com/UB-Mannheim/tesseract/wiki and add it to your PATH
- **macOS**: `brew install tesseract`
- **Linux**: `sudo apt install tesseract-ocr`

Tested end-to-end: OCR extraction on a synthetic prescription image →
correct text → correct parsed drugs → correct violation flagged, all the
way through the real HTTP API (`/api/ocr`), including auth-required (401
without a token), non-image-file rejection (400), and a full
signup → OCR → verify flow. 4 automated tests in
`backend/tests/test_ocr.py`, all passing.

## 5. Visible confidence indicator

A prominent (not buried) indicator showing how confident the guideline
match is — high/moderate/low, plus a note when the query was
automatically reformulated. This directly addresses **alert fatigue**, a
documented reason clinical decision-support tools get ignored in real
deployments (cited in this project's own literature survey) — showing
how sure the system is, rather than presenting every flag as equally
certain.

## 6. About page rewritten for end users

Previously described the five internal agents and tech stack (LangGraph,
bge-large, BM25, ChromaDB) — accurate, but the wrong audience for a
public-facing page. Rewritten to describe what the system **does**
(catches dangerous combinations, flags missing tests, explains every
result) rather than how it's built internally. The engineering detail
still belongs in your presentation to your teacher and in this README —
just not on the page a general visitor sees.

## Setup (unchanged)

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

## Tested before delivery

- Full regression suite: **27 tests across 7 files, all passing**
  (`test_pipeline`, `test_llm_parser`, `test_live_data`,
  `test_live_retrieval_integration`, `test_hybrid_retriever`, `test_ocr`,
  `test_ddinter_ingest`), plus the 48-case benchmark re-run clean.
- Postgres engine construction verified (driver installed, engine built
  correctly) — a live Postgres connection was not available to test
  against.
- DDInter ingestion logic verified against a synthetic CSV — the real
  dataset could not be downloaded in this environment (see honest
  limitation above).
- `npm run build` — clean compile, no errors.

---

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
