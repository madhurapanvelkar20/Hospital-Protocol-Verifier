# Technology Stack and Architecture Audit

**Audit scope:** the `hpv-fullstack-v6` workspace, source/configuration files, the local SQLite and Chroma artifacts, the frontend lockfile and installed frontend packages, and the configured Python 3.13.5 environment. This describes the code as found, not an assumption that every optional path is deployed.

## Executive assessment

This is a single-deployment clinical-protocol verification prototype: a React SPA calls a FastAPI API, which stores accounts and per-user verification history in SQLite and runs a deterministic LangGraph pipeline. The pipeline combines a small rule-based interaction/monitoring knowledge base with protocol retrieval. Its configured default retrieval path is BGE-large dense search in persistent Chroma plus in-memory BM25; TF-IDF is an offline alternative.

The overall choices are proportionate for a demo. **Do not add a second database or split this into services now.** Keep SQLAlchemy, SQLite for local/demo use, Chroma for the present small persisted dense index, BM25, the local curated knowledge files, and React/FastAPI. Improve index freshness, evaluation, configuration, and deployment safeguards before considering a datastore migration.

This is not ready for real patient data or clinical use. The bundled benchmark is synthetic and derived from the same rules it tests; its reported 1.0 full-pipeline score is a regression result, not evidence of clinical accuracy. The previously observed defects where unknown drug names were silently dropped and one component satisfied combined monitoring have been fixed and covered by regressions. The required backend dependencies and pytest are now installed in the existing CPython 3.13.5 virtual environment, and the complete backend suite passes. PostgreSQL remains unconfigured and untested.

## 1. Verified technology inventory

### Languages and application frameworks

| Technology | Version / evidence | Role and actual status |
|---|---|---|
| Python | Runtime is CPython 3.13.5. Backend source is Python. | Active API, pipeline, data access, retrieval, OCR, and scripts. |
| JavaScript / JSX | Frontend uses `.js` and `.jsx`; no TypeScript source or TypeScript build is present. | Active browser client. |
| FastAPI / Starlette | Installed FastAPI 0.143.1 / Starlette 1.8.0; `backend/requirements.txt` declares FastAPI `>=0.110.0`. | Active REST API in `backend/main.py`; application module import passed and a SQLite-backed API smoke test is reported below. |
| Pydantic | Installed 2.14.1; used in `backend/main.py` for request schemas and `EmailStr`. | Active request validation. |
| LangGraph | Installed 1.2.15; `backend/src/graph.py` imports and uses `StateGraph`. | Active for parse → retrieve → cross-check → missing-tests → explain orchestration; full pipeline tests passed. |
| React / React DOM | package lock and installed frontend: React 19.3.0, React DOM 19.3.0. | Active SPA, contexts, pages, and components. |
| React Router | `react-router-dom` 7.18.4. | Active client-side routes and protected pages. |
| Vite / React plugin | Installed Vite 8.3.1 and `@vitejs/plugin-react` 6.1.1. | Active development server and production build. |
| Node.js / npm | Installed Node.js 24.13.0 and npm 11.6.2. | Frontend toolchain runtime; the production build completed successfully on this pair. |
| CSS | `frontend/src/App.css` and `tokens.css`; plain CSS, custom properties. | Active styling. No Tailwind, component framework, CSS-in-JS, or other styling library is evident. |
| HTTP client | Browser `fetch`; Python `requests` (installed version 2.32.4). | Active frontend API calls; active backend external data clients. No Axios dependency. |

### Persistence, data, AI, and retrieval

| Technology | Version / evidence | Role and actual status |
|---|---|---|
| SQLite | Actual file `backend/hpv.db` (32 KiB); tables `users` and `verification_history`, two rows in each at prior audit time. Python SQLite runtime is 3.49.1. | Active local relational store for accounts and verification history. API smoke tests used a disposable SQLite file. An earlier application-module import invoked the existing `init_db()`/`create_all()` against the default path; no test account/history rows were written there, but byte-for-byte file preservation was not asserted. No migration or copy was performed. |
| SQLAlchemy | `sqlalchemy>=2.0.0`; installed version 2.1.4. | Active ORM: declarative models, relationships, query construction, and request-scoped sessions. No SQLAlchemy Core query layer is used for application CRUD. |
| PostgreSQL | Opt-in `DATABASE_URL` or `DB_DIALECT`/`DB_*` configuration in `backend/src/db.py`; `psycopg[binary]` is optional. | PostgreSQL engine/session path is implemented, but no PostgreSQL server or driver was available for live validation. |
| Alembic | Optional `alembic>=1.13.0` requirement in `backend/requirements.txt`; migration environment and two versioned revisions under `backend/migrations/`. | Intended for explicit PostgreSQL schema management; not installed or run in this phase. |
| ChromaDB | Installed 1.5.9; `backend/chroma_store/` contains persisted dense collections. | Active in the default BGE path; real collection/query operations were exercised by the pipeline tests and ranking comparison. |
| Sentence Transformers / BGE | Installed Sentence Transformers 6.1.0; code selects `BAAI/bge-large-en-v1.5`. | Actual dense embedding model in the default hybrid retrieval path; real model initialization and query embeddings were measured, not mocked. |
| PyTorch / Transformers | Installed PyTorch 2.14.1 / Transformers 5.19.0, transitive through Sentence Transformers. | Active model runtime for BGE. Python 3.13.5 installation and execution succeeded in this environment. |
| BM25 | Installed `rank_bm25` 0.2.2; declared `>=0.2.2`. | Active in the default hybrid retrieval code path. |
| TF-IDF | Installed scikit-learn 1.9.1; declared `>=1.4.0`. | Active when `EMBEDDING_BACKEND=tfidf`; used for offline and same-query comparison. |
| YAML | Installed PyYAML 6.0.3; declared `>=6.0`. | Active parser for Markdown guideline frontmatter in `backend/src/vector_store.py`. |
| Guideline corpus | Markdown under `backend/data/protocols/`. | Active local protocol source; sections become retrieval chunks with title/source/version/specialty metadata. |
| Structured clinical rules | `backend/data/interactions.json` and `monitoring_requirements.json`. | Active local rule sources for interaction/contraindication and missing-test checks. `interactions_ddinter.json` is optional and was not present in the inspected file inventory. |
| DDInter ingestion | `backend/scripts/ingest_ddinter.py`; no ingested output present. | Implemented optional CSV ingestion path; not an active data source in this workspace. The code’s supported column mapping and license/data provenance still need validation against an actual download. |
| openFDA | `backend/src/live_data.py`; config defaults `LIVE_FDA_RETRIEVAL_ENABLED=false`. | Optional live label retrieval remains disabled by default. The response now distinguishes no-match from unavailable lookup and exposes separate warnings; tests use mocked HTTP only. |
| PubMed / NCBI E-utilities | Search helper in `backend/src/live_data.py`; no caller found in the pipeline. | Implemented but unused/backend-only supporting literature lookup; it is not a guideline citation source. |
| LLM provider | Optional Anthropic client calls hardcode `claude-sonnet-4-5`; `anthropic` remains commented optional and uninstalled. | Optional parser only when `PARSER_BACKEND=llm`; optional explanation when `ANTHROPIC_API_KEY` exists. LLM parser fallback now produces an explicit warning, but Anthropic calls were not tested. |
| OCR | Pillow 12.3.0, pytesseract 0.3.13, and the existing system Tesseract 5.5.3.20260724. | Implementation uses Pillow + `pytesseract` to invoke Tesseract. The real Tesseract-backed OCR tests passed; no alternate OCR engine was installed. |

### Authentication, operations, and quality tooling

| Technology | Version / evidence | Role and actual status |
|---|---|---|
| bcrypt | `bcrypt>=4.0.0`; installed version 5.0.0. | Active password hashing and verification. |
| JWT | Installed python-jose 3.5.0; declared `python-jose[cryptography]>=3.3.0`. | Active for HS256 bearer access tokens with seven-day expiry. The signing secret still has an insecure built-in development fallback. |
| Email validation / upload support | Installed email-validator 2.3.0 and python-multipart 0.0.32. | Active for FastAPI request validation and multipart upload. |
| Caching / background work | No Redis, cache framework, task queue, or background worker found. | Retriever, graph, and model use module-level lazy singletons; these are per-process in-memory reuse, not a distributed cache or task system. |
| Python tests | pytest 9.1.1 installed as a test-only dependency; `httpx` 0.28.1 is present. The source tree has no pytest configuration file. | `python -m pytest -q` runs the backend suite; 1 PostgreSQL integration module is intentionally skipped without `TEST_DATABASE_URL`. |
| Frontend lint/build | Oxlint 1.85.0, npm scripts in `frontend/package.json`; frontend dependencies are locked in `package-lock.json`. | Active lint and production build. Build succeeded; lint completed with two warnings in `AuthContext.jsx`. |
| Type checking | No `tsconfig`, TypeScript source, mypy, or Pyright project configuration found. | Not configured. |
| Containers / CI / migrations | No Docker/compose, CI workflow, or deployment manifest found. Alembic config and two revisions exist but Alembic is optional and not installed. | PostgreSQL migration setup is documented, but was not applied; deployment remains manual. |

## 2. Architecture and data flow

1. The browser SPA in `frontend/src` calls `/api` routes using `fetch`, a bearer token, and a default API origin of `http://localhost:8000/api`.
2. FastAPI in `backend/main.py` handles signup/login, OCR, verification, history, metadata, and health. `HTTPBearer` protects user-specific endpoints. SQLAlchemy sessions are provided by a FastAPI dependency.
3. `/api/verify` synchronously invokes `run_pipeline`; LangGraph composes five state nodes:
   - regex parser by default, optional Claude parser;
   - local protocol retrieval, optional openFDA lookup;
   - deterministic interaction and contraindication rule matching;
   - deterministic monitoring-test requirements matching;
   - template explanation by default, optional Claude phrasing.
   - parser, external-data, and unsupported-drug warnings are returned in the verification result; warnings are also retained inside saved history results and shown in both the Verifier and History UI.
4. Retrieval reads Markdown protocol sections. The default BGE path embeds chunks and persists dense vectors in Chroma; BM25 is built in memory. The TF-IDF fallback fits an in-memory matrix. The cross-check rules and monitoring requirements are JSON data, not embeddings or SQL tables.
5. Verification inputs and the full result JSON are saved in `verification_history`. Password hashes and user records are stored in `users`. The history page reads the saved result and does not rerun the pipeline.
6. OCR uses Pillow preprocessing and `pytesseract`/Tesseract locally, then returns recognized text and best-effort extracted diagnosis/tests for user review. OCR output is not silently verified.

The architecture has useful boundaries between API, graph, agents, data, and UI. Business rules are not delegated to an LLM. However, the checked rules are small, local, and not independently validated clinical truth. The five LangGraph nodes currently execute sequentially; LangGraph provides state/orchestration, not parallel computation here.

## 3. Database and data-storage assessment

### Current data placement

| Data | Actual storage |
|---|---|
| Users, email, display name, bcrypt hash, creation time | `users` SQLite table via SQLAlchemy ORM. |
| Verification input, diagnosis hint, result JSON, violation count/severity, creation time | `verification_history` SQLite table via SQLAlchemy ORM. The complete result is JSON text in a relational column. |
| Drug interaction and drug/diagnosis rules | JSON files; optionally merged at process import from DDInter JSON if present. |
| Monitoring rules and sample prescriptions | JSON files. |
| Protocol documents | Markdown files; section chunks are derived in memory and Chroma. |
| Embeddings and Chroma metadata | Chroma persistent local SQLite/segment files; derived from protocol documents. |
| PubMed results | Returned from an unused helper; no persistence found. |

Monitoring requirements now carry explicit conjunctive `required_components` groups and configured alias lists; the matcher normalizes ordered names, recognizes exact aliases and explicitly delimited panel members, then computes missing canonical components as a set difference. It does not use arbitrary substring matches (for example, “Creatinine Clearance” does not satisfy the “creatinine” alias). These mappings are implementation rules, not clinician-validated equivalences. The ambiguous abbreviation `KFT` is deliberately not accepted because the project’s source data does not define its component panel. A site-specific lab catalog should define it before it is used to satisfy renal or electrolyte requirements.

When `interactions_ddinter.json` is introduced, `_load_interactions` concatenates its entries with the curated JSON without deduplication. An overlapping pair can therefore produce duplicate findings. No DDInter data file is present now, so this is a conditional issue; compare normalized pairs and preserve provenance before enabling an ingested dataset.

### ORM versus database versus vector store

SQLAlchemy is the **data-access/ORM layer**: it maps Python model classes to relational tables and builds queries. SQLite is the **relational database engine** that stores user/history rows in the current deployment. Chroma is a **vector store** used for similarity search over embedding vectors and chunk metadata. These components solve different problems. Replacing SQLAlchemy would not itself change the SQLite engine, and replacing SQLite would not require replacing SQLAlchemy.

SQLAlchemy ORM usage is appropriate for the two small relational entities and relationship. No evidence justifies removing it. SQLite is appropriate for local demos and a single process. The current history query filters by user, orders by creation time, and limits to 50, but the SQLite table has no composite `(user_id, created_at)` index. The PostgreSQL-only schema revision adds that index without changing the existing SQLite schema automatically. The inspected SQLite database also has redundant explicit indexes on the `id` primary-key columns because the models set `index=True` on those columns. These are small-scale optimization opportunities, not observed bottlenecks. SQLite schema initialization still uses `Base.metadata.create_all()` at import; PostgreSQL now requires explicit Alembic migrations. SQLite `check_same_thread=False` allows the driver connection to be used from FastAPI’s worker threads; it does not make SQLite a multi-writer server or make one SQLAlchemy `Session` safe for concurrent use. Sessions are request-scoped and closed in `get_db`.

The model declares `user_id` as a foreign key, but SQLite foreign-key enforcement is not enabled explicitly in the engine connection setup. Verify and enable it before relying on the constraint. For a multi-worker or multi-instance deployment, PostgreSQL is a credible relational upgrade because it handles concurrent writers and server-based access. An opt-in PostgreSQL configuration, Alembic migration path, and explicit SQLite copy utility are now present, but no PostgreSQL server/driver was available for live validation. The copy is not run automatically and refuses a non-empty target.

The local SQLite file contains account and verification-history rows. Treat it as sensitive user data: do not publish or copy it into an untrusted environment. No encryption-at-rest configuration is visible. Do not use real patient data until privacy, retention, access, key management, audit, and regulatory reviews are complete.

### Alternatives compared

- **SQLite:** keep for local/demo use. It has no server operations and is sufficient for the current small footprint, but single-writer behavior and single-file deployment make multi-instance concurrency and recovery a concern.
- **PostgreSQL + SQLAlchemy:** consider only when real multi-worker/multi-instance deployment or stronger operational needs are demonstrated. ORM can remain; add a supported driver, explicit migration tooling, backups, monitoring, and migration/rollback procedures first.
- **PostgreSQL + pgvector:** not justified yet. It would consolidate relational and vector operations, but introduces extension/deployment complexity without evidence that the 64-chunk local index or Chroma operations are a bottleneck.
- **ChromaDB:** currently proportionate to a small local persistent vector index and metadata-bearing chunks. It is not inherently more accurate than other stores; stale-index behavior must be handled, now improved by corpus/model-specific collection snapshots.
- **FAISS:** would offer efficient local nearest-neighbor search, but would require separate persistence/metadata mapping and synchronization work. There is no measured latency or index-size problem that makes it a better fit.

## 4. RAG, embedding, and retrieval assessment

The code has two retrieval modes. Default `bge` loads `BAAI/bge-large-en-v1.5`, queries Chroma dense neighbors, builds an in-memory BM25 index once per process, normalizes each candidate list independently to `[0,1]`, and combines the two scores with equal default weights. Dense candidates and BM25 candidates are each capped at 10 before fusion; final results default to three chunks. `tfidf` uses scikit-learn TF-IDF and cosine similarity, entirely in memory. Both paths use local Markdown sections and metadata for citation display.

The checked-in Chroma SQLite artifact contains one 1024-dimensional collection with 64 embeddings. This is a small enough dataset that local Chroma or even in-memory TF-IDF can be reasonable; there is no measured need for a managed vector database. `rank_bm25` is actively used, not dead weight. Metadata is preserved and returned for citation, but no metadata filter is used in retrieval. BM25 tokenization is simple lowercase whitespace splitting; no clinical synonym normalization is implemented. Score min-max normalization on a small top-N pool can magnify a weak candidate and does not make the scores calibrated probabilities. The reported “retrieval confidence” is the top fused score (or forced to `1.0` if any FDA live chunk exists), not a validated confidence estimate.

The persisted local Chroma client is a process-local singleton; multi-process access to the same persistence directory has not been tested and should not be assumed safe for multiple workers.

Before the change in this audit, the collection was always named `protocols` and only populated when empty. Editing or adding guideline chunks could therefore leave a stale dense index while BM25 loaded the new corpus, mixing corpus versions. The retriever now derives an immutable collection name from the serialized corpus and model name, reconciles missing/stale IDs, and retains old collections rather than deleting data. This prevents silent old-corpus reuse and preserves the previous data for rollback. Old snapshots consume disk until deliberately backed up and cleaned; model weights/revision and library version still are not pinned, so this is not full bit-for-bit reproducibility.

The 48-case benchmark in `backend/benchmark/` is a deterministic rule-regression test generated from the same JSON rule files used by the pipeline. Its current in-process result is 1.0 case accuracy, 1.0 violation recall, and 0 false-positive rate for `full_pipeline`; no-agent and retrieval-only baselines score 0.333 case accuracy and 0 recall. The checked-in report was preserved. A separate 15-query retrieval comparison now reports title-based P@5, R@5, MRR@5, nDCG@5, initialization time, and query latency for actual BGE/Chroma/BM25 versus TF-IDF. The labels are protocol-title relevance judgments, not clinician judgments or clinical validation, and are too small to establish clinical retrieval quality.

**Recommendation:** keep the current local hybrid architecture for this scale. Add independently authored/clinician-reviewed held-out retrieval and violation cases, retrieval metrics, and latency measurement before tuning score fusion or migrating the store. Compare BM25, dense-only, hybrid, and TF-IDF on the same judged queries; a vector database migration cannot repair a weak corpus, parser, chunking policy, or evaluation set.

## 5. Dependency and version review

- Python requirements specify lower bounds (`>=`) rather than exact versions; there is no Python lockfile or declared `requires-python` range. A fresh install can resolve materially different versions over time; pin a tested deployment set before production.
- The selected interpreter is CPython 3.13.5. The required runtime stack and tests were installed/executed successfully there: FastAPI 0.143.1, Pydantic 2.14.1, LangGraph 1.2.15, ChromaDB 1.5.9, Sentence Transformers 6.1.0, PyTorch 2.14.1, Transformers 5.19.0, rank-bm25 0.2.2, scikit-learn 1.9.1, SQLAlchemy 2.1.4, pytest 9.1.1, httpx 0.28.1, and pytesseract 0.3.13. `pip check` reported no broken requirements.
- Source syntax includes `str | None`, so the source-level minimum is Python 3.10. There is no declared support matrix. CPython 3.13.5 is the version actually tested; compatibility of other Python versions is unverified. PostgreSQL-only optional packages (`psycopg`, Alembic) and optional Anthropic were not installed because PostgreSQL/LLM paths were not enabled.
- The Tesseract 5.5.3.20260724 executable is present on this Windows host, and the real OCR tests passed using the existing Tesseract engine and pytesseract wrapper. No alternate OCR engine was installed. A live PostgreSQL server and driver were not verified.
- Optional Anthropic dependency is commented out; no `.env` or secrets manager setup is present. Installing it alone would not address key handling or clinical validation.
- Frontend dependencies are locked. Installed versions observed: React/React DOM 19.3.0, React Router 7.18.4, Vite 8.3.1, React plugin 6.1.1, and Oxlint 1.85.0. The JS-only project also lists `@types/react` and `@types/react-dom`; these provide little build value without TypeScript, but are not a runtime risk.
- Successful frontend build output after safety-warning UI changes: Vite produced a 289.12 kB JS bundle (90.01 kB gzip) and 17.45 kB CSS (3.93 kB gzip). Build wall time was under one second in this run; this is not a backend latency benchmark.
- `npm run lint` completes with two existing warnings: `react/only-export-components` and `react/set-state-in-effect` in `frontend/src/context/AuthContext.jsx`. No lint configuration for Python or type-checking is present.

### Dependency installation performed

The existing project-selected Python 3.13.5 virtual environment was used. Missing declared default-path packages (`langgraph>=0.2.0`, `chromadb>=0.5.0`, `sentence-transformers>=3.0.0`) and the minimum test tool (`pytest>=8.0.0`) were installed; the other required manifest dependencies, including `pytesseract`, were already available. `httpx` was already installed. `python -m pip check` passed. PostgreSQL-only (`psycopg`, Alembic) and Anthropic dependencies remain uninstalled because those optional paths were not enabled. No OCR engine was added or replaced.

## 6. Performance, reliability, and maintainability

### Evidence-backed observations

1. **Lazy warm-up:** the graph and retriever are module-level lazy singletons. The first verification in a process may pay model loading and index initialization cost; subsequent requests in that process reuse these objects. There is no startup warm-up/readiness check, and separate worker processes each load their own model and BM25 index.
2. **Index freshness:** fixed as described above. Old collection snapshots are retained to avoid destructive migration.
3. **OCR upload memory:** the endpoint previously read the entire multipart upload before checking its 8 MB maximum. It now reads at most 8 MB + 1 byte, so an over-limit file is rejected without buffering the complete body in application memory. This does not replace reverse-proxy/request-body limits.
4. **Blocking work:** `/api/verify` is a synchronous FastAPI route (FastAPI runs sync routes in its worker pool). `/api/ocr` is declared async, but the Tesseract/Pillow work is synchronous inside it and can block the event loop during OCR. Live HTTP and Claude calls are synchronous; live FDA lookup is sequential per drug and has a six-second timeout per call. These are acceptable prototype choices but warrant moving blocking OCR/HTTP calls to a threadpool and applying total request budgets if observed latency grows.
5. **Repeated retrieval work:** query embeddings are computed for each request; no retrieval-result cache exists. BM25 is constructed once per process, not per request. Caching must be keyed by query plus corpus/model version and invalidated when data changes; current scale does not justify Redis.
6. **Database query path:** history is capped at 50 items, but lacks the likely helpful composite user/date index. The local DB has only two history rows at audit time, so no measurable database bottleneck was observed.
7. **External-source behavior:** the optional FDA path now distinguishes a successful no-match from a failed/unavailable lookup and emits different user-visible warning types. PubMed remains unwired into the request path.
8. **Retrieval latency and relevance:** on the 15 title-labeled queries, BGE/Chroma/BM25 initialized in 17.725 s and averaged 124.27 ms/query (median 126.34 ms, p95 134.05 ms); TF-IDF initialized in 0.066 s and averaged 0.74 ms/query (median 0.62 ms, p95 1.23 ms). Both had P@5 0.213, R@5 1.000, and MRR@5 0.911; nDCG@5 was 0.928 for hybrid and 0.933 for TF-IDF. These are small, corpus-title judgments, not clinical labels, and do not measure API, OCR, cold-start deployment, or end-to-end request latency. They do not justify replacing the current hybrid path without stronger relevance evidence.

### Security and privacy concerns

- `JWT_SECRET_KEY` defaults to the fixed string `dev-only-insecure-secret-change-me`; production must fail closed unless a strong secret is configured.
- Tokens are stored in browser `localStorage`, accessible to injected same-origin JavaScript. An HttpOnly secure cookie is a production alternative, with CSRF protections designed deliberately.
- No login rate limiter, token revocation, refresh flow, account recovery, role-based authorization, or compliance-grade audit trail was found. Password minimum is eight characters.
- CORS currently allows localhost development origins; deployment must set a narrow production origin list and HTTPS.
- OCR accepts an `image/*` content type but content type is client-provided; actual image parsing is the effective format check. The bounded read now avoids unbounded application-level buffering, but image pixel/decompression limits and upstream body-size limits should also be deployed.
- Full prescription text and results are retained in SQLite history. Define retention/deletion/access policy before handling sensitive data; no encryption-at-rest or clinical audit controls are configured.
- The LLM parser still catches broad exceptions to preserve availability, but its regex fallback is now surfaced in a structured user-visible `parser_fallback` warning. The optional LLM explanation can still fall back to its template without a separate diagnostic; no LLM provider was installed or tested.
- No production claims should be made for clinical safety or regulatory compliance based on the synthetic self-derived benchmark.

## 7. Technology comparison and recommendations

| Component | Current technology | Alternative | Benefits | Trade-offs | Migration effort | Recommendation |
|---|---|---|---|---|---|---|
| Relational database | SQLite file, local demo | PostgreSQL | Concurrent multi-process writes, server access, operations/backups suited to multi-instance deployment | Service and operations overhead; driver, migrations, backup/restore, and deployment work | Medium/high; schema is small but data migration must be tested | **Keep** SQLite for demo; **Consider replacing** with PostgreSQL only when multi-instance production is required |
| ORM/data access | SQLAlchemy ORM 2.x | Raw SQL or another ORM | Existing code is small, typed enough for the use case, and DB-dialect portable | ORM adds a dependency, but replacing it does not fix database-engine limits | High for little demonstrated benefit | **Keep** SQLAlchemy |
| Vector storage | Persistent Chroma local collection | FAISS, PostgreSQL/pgvector | FAISS can be lean for local ANN; pgvector may consolidate storage and filtering | FAISS needs separate metadata/persistence; pgvector needs PostgreSQL extension and ops; neither inherently improves relevance | Medium for FAISS; medium/high for pgvector | **Keep** Chroma at current 64-vector scale; reevaluate with measured need |
| Embedding model | BAAI/bge-large-en-v1.5 via Sentence Transformers | Smaller BGE/E5 model or hosted embeddings | Current model supplies local dense semantic retrieval and avoids per-query provider billing | Large local model footprint/startup and CPU/GPU cost; model/revision not pinned; no latency/quality comparison | Medium; change requires full re-embed and relevance evaluation | **Optimize** by pinning model revision, measuring load/query cost, and evaluating smaller models before replacement |
| Retrieval method | Dense top-10 + BM25 top-10, min-max weighted fusion; TF-IDF fallback | Reciprocal-rank fusion, BM25-only, tuned hybrid | Hybrid can combine semantic and exact clinical vocabulary; BM25/TF-IDF work offline | Current score fusion uncalibrated and evaluation has no judged retrieval set | Low/medium to compare; tuning needs labeled queries | **Optimize** evaluation and calibration; keep hybrid until measured otherwise |
| LLM integration | Optional Anthropic Claude parser and explanation | No LLM / other provider / local model | Can parse beyond vocabulary and polish narrative | External PHI exposure, cost, nondeterminism, undeclared optional package, silent fallback; not the factual rule engine | Medium; operational/privacy review needed | **Keep** optional/off by default; **Not needed** for deterministic checks until parsing need and privacy controls justify it |
| OCR | Pillow + pytesseract wrapper + external Tesseract | Cloud OCR or managed document AI | Local processing and human review avoid sending images externally | System binary dependency; OCR quality/handwriting limitations; CPU-bound request work | Low for threadpool/deployment limits; high for provider swap | **Keep** local OCR for demo; **Optimize** resource limits and offload blocking work |
| Cache / jobs | Per-process lazy singletons; no distributed cache/queue | Redis, task queue | Redis/jobs help only with demonstrated cross-worker reuse or long tasks | Infrastructure, invalidation, operational and privacy complexity | Medium/high | **Not needed** at observed scale; use worker offload and measure first |
| Backend/API | FastAPI + LangGraph sequential graph | Flask, async framework, microservices | FastAPI fits typed REST/upload APIs; LangGraph clearly expresses the sequential state flow | Sync model/OCR work; LangGraph overhead for a small fixed pipeline | High to replace; low to improve execution | **Keep**; **Optimize** diagnostics, startup readiness, request budgets, and dependency injection |
| Frontend | React 19 + React Router 7 + Vite 8, plain CSS | Other SPA framework or SSR | Current small client is built successfully, routes/components are separated | No SSR is needed for this authenticated utility; JS-only and types packages are slightly redundant | High for migration, no evidence of need | **Keep** |
| Authentication | bcrypt + HS256 JWT in localStorage | Secure HttpOnly cookie/session system | Simple bearer auth is functional for a local demo | Fixed fallback secret, browser token exposure, no rate limit/revocation or account recovery | Medium/high | **Optimize** before any non-local deployment; production secrets must fail closed |
| Clinical data | JSON rules + Markdown guidelines + optional DDInter CSV ingest | Curated external licensed clinical source / relational rule schema | Transparent, easy-to-edit prototype data; citations preserve source strings | Small/manual source, provenance and updates are not automated; DDInter output is absent; clinical validity unverified | Medium/high for licensed data governance | **Optimize** provenance, review/update process, and independent validation; do not bulk-ingest unverified rules |
| Test/evaluation | pytest-style tests, synthetic self-derived benchmark, Oxlint | Held-out clinician-reviewed dataset and retrieval metrics | Existing tests catch regressions; frontend build/lint are easy to run | Pytest absent from requirements/runtime; benchmark is circular and not a safety metric | Medium/ongoing | **Optimize** test installation and independent evaluation before clinical claims |

## 8. Ranked improvement plan

| Priority | Action | Impact / effort / risk | Recommendation |
|---|---|---|---|
| P0 before real data or deployment | Remove the default JWT signing key; fail startup when unset in production. Add secrets management, HTTPS, narrow CORS, login throttling, patient-data retention/access controls, and a security/privacy review. | Very high impact; medium effort; high risk if deferred. | **Optimize** security and privacy boundaries; keep this prototype local until complete. |
| P1 | Create independent, clinician-reviewed held-out cases; measure extraction correctness, violation precision/recall, false positives, retrieval Recall@k/MRR/nDCG, and latency separately. Compare TF-IDF, BM25, dense, and hybrid. | Very high impact on trust; medium effort; low operational risk. | **Optimize** evaluation before tuning models or stores. |
| P1 | Pin/test backend dependency versions and declare test tooling; test supported Python and OS/Tesseract configurations. Ensure the configured default BGE path is actually installable and add a readiness check/warm-up decision. | High reliability impact; low/medium effort; low risk. | **Optimize** reproducibility and startup. |
| P1 | Preserve and back up the existing Chroma directory before cleanup. Retain the new corpus/model-versioned snapshots; define an explicit safe cleanup policy only after verifying the active index and backup. | High correctness impact; low effort; low risk with snapshots. | **Optimize** index lifecycle. |
| P2 | Enable SQLite foreign keys and add an index on `(user_id, created_at)`; use a migration rather than relying on `create_all()` for deployed schema changes. | Medium impact at current data volume; low/medium effort; low risk if migrated with backup. | **Optimize** SQLite configuration; preserve it for demo. |
| P2 | If measurements show slow OCR or external calls, run blocking work in a threadpool, set total time budgets, and make source unavailability observable without logging prescription contents. | Medium impact; medium effort; low/medium risk. | **Optimize** only when workload or measured latency warrants it. |
| P3, conditional | Migrate SQLite to PostgreSQL for multi-instance concurrency, then consider pgvector only if vector scale/operations justify it. | High impact only for production scale; high effort and migration risk. | **Consider replacing** SQLite only with a documented backup, migration, validation, and rollback plan; pgvector is not currently needed. |

## 9. Changes implemented in this audit

1. **Bounded OCR upload read:** `backend/main.py` now reads no more than `MAX_OCR_IMAGE_BYTES + 1` bytes before rejecting an over-limit image. The endpoint and response contract are unchanged.
2. **Versioned/reconciled Chroma indexes:** `backend/src/vector_store.py` derives a collection name from a stable hash of protocol chunks and the embedding model name. It fills missing IDs, removes unexpected IDs from that new snapshot, and leaves prior collections untouched.
3. **Opt-in PostgreSQL support:** environment-based SQLAlchemy configuration, PostgreSQL migration-head checking, Alembic revisions, transactional rollback behavior, duplicate-email race handling, a read-only-source SQLite copy tool, and opt-in real-PostgreSQL CRUD/API tests. No migration, copy, or PostgreSQL connection was performed.
4. **Prescription safety behavior:** unknown extracted medication names are preserved with an unsupported status and explicit warning; generic/unreadable medication references produce a distinct parsing-failure warning, including when other drugs were recognized. Parser candidates no longer absorb adjacent drugs across conjunctions. Warnings propagate through the API/history and are shown in the UI.
5. **Monitoring matching:** composite lab requirements now require every configured component; ordered tests are normalized and mapped through exact configured aliases/panel terms to canonical components, then compared as sets. Known specimen prefixes are normalized; unrelated compound tests are not accepted by substring. KFT is intentionally not treated as equivalent to a renal panel because its composition is not verified in the source data.
6. **Evaluation:** added a non-writing 15-query BGE/Chroma/BM25 versus TF-IDF runner and title-relevance judgments. The existing 48-case evaluation report was not rewritten.
7. **Hybrid test correction:** the dense-ranking regression now checks the result's guideline `title` metadata instead of the shared, non-specific `source` field.
8. **Typed investigation extraction:** verification extracts explicit lab lists from prescription text and merges them with tests entered in the separate field. The extractor recognizes `Investigations advised:` and treats blank lines within an explicit section as whitespace, retaining separately spaced lab entries until the next section header. Partial composite findings identify the missing components in the response.
9. **Audit documents:** this file records the verified overall stack; `POSTGRESQL_MIGRATION.md` records database-specific setup, copy, test, and rollback instructions.

No relational schema or user data was migrated. No model, vector database, database engine, or external infrastructure was added. The old `protocols` Chroma collection remains on disk and can be used by reverting the code; the new collection does not overwrite it.

### Exact files changed across the audit work

- Backend API, retrieval, and persistence: `backend/main.py`, `backend/src/db.py`, `backend/src/vector_store.py`, `backend/src/state.py`, `backend/src/live_data.py`, `backend/src/prescription_extract.py`, `backend/src/agents/parser_agent.py`, `backend/src/agents/llm_parser_agent.py`, `backend/src/agents/retriever_agent.py`, `backend/src/agents/explanation_agent.py`, `backend/src/agents/missing_test_agent.py`.
- PostgreSQL setup and migration path: `backend/requirements.txt`, `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/script.py.mako`, `backend/migrations/versions/0001_relational_baseline.py`, `backend/migrations/versions/0002_history_user_created_at_idx.py`, `backend/scripts/migrate_sqlite_to_postgres.py`.
- Data and tests: `backend/data/monitoring_requirements.json`, `backend/tests/test_hybrid_retriever.py`, `backend/tests/test_live_data.py`, `backend/tests/test_live_retrieval_integration.py`, `backend/tests/test_pipeline.py`, `backend/tests/test_postgres_integration.py`, `backend/tests/test_prescription_extract.py`, `backend/tests/test_retrieval_warnings.py`, `backend/tests/test_safety_regressions.py`, `backend/tests/test_verify_api.py`.
- Retrieval evaluation: `backend/benchmark/README.md`, `backend/benchmark/retrieval_judgments.json`, `backend/benchmark/run_retrieval_evaluation.py`.
- Frontend warning UX: `frontend/src/App.css`, `frontend/src/components/ParsedDrugsTable.jsx`, `frontend/src/components/ResultBanner.jsx`, `frontend/src/pages/History.jsx`, `frontend/src/pages/Verifier.jsx`.
- Documentation: `README.md`, `docs/POSTGRESQL_MIGRATION.md`, `docs/TECH_STACK_AND_ARCHITECTURE_AUDIT.md`.

## 10. Validation and benchmarks

Commands were run from the `backend` or `frontend` directory as appropriate:

```powershell
# Backend
python -m pytest -q
python -m pytest -q tests/test_safety_regressions.py
python -m pip check
python benchmark/run_retrieval_evaluation.py

# Frontend
npm run lint
npm run build
```

The 48-case rule benchmark was evaluated without invoking the report-writing CLI: PowerShell set `$env:EMBEDDING_BACKEND = 'tfidf'`, then Python imported `load_cases`, `evaluate`, and `SYSTEMS` from `benchmark.run_evaluation` and printed their in-process results. The environment override was removed afterwards.

- **Full backend tests:** final `python -m pytest -q` completed with **54 passed, 1 skipped**. The skipped opt-in PostgreSQL integration module requires `TEST_DATABASE_URL`. The suite includes Tesseract-backed OCR tests, Chroma/hybrid retriever tests, and the typed investigation-to-API regression.
- **Investigation/lab regressions:** `python -m pytest -q tests/test_safety_regressions.py tests/test_prescription_extract.py tests/test_verify_api.py` passed **27 tests**. This covers both ordered, potassium-only, creatinine-only, neither, aliases, normalized punctuation/whitespace, unrelated tests, the distinct Creatinine Clearance case, the exact multiline text, and merging explicit field values with text extraction.
- **Exact blank-line-separated reproduction:** focused diagnostics showed the request has the full text in `raw_text` and `ordered_tests: []`. Before matching, extraction returned only `["Serum Creatinine"]` because the extractor stopped at the blank line preceding Serum Potassium. After the fix, both tests are extracted; normalized requirement alias groups remain creatinine/renal-function alternatives AND potassium, normalized detected components are `["serum creatinine", "serum potassium"]`, and final missing components are `[]`. A live request with the same payload to the isolated current-code API returned `missing_tests: []` and `violations: []`.
- **Live process check:** the existing port-8000 API answered health but was running from a Python 3.11 Uvicorn executable (PID 24588). Its module path could not be established from exposed endpoints. The reloader parent exited, but the listener remained attributed to PID 24588 after Windows process inspection and `Stop-Process` could no longer find that process. No further termination was attempted. Instead, the workspace module path was independently confirmed as `backend/main.py`, and a current-code Python 3.13.5 virtualenv server was launched on port 8001 with a disposable SQLite file. Its API passed the exact request. A temporary Vite process on port 5174 was configured for that server; the manual visual browser session against the original port-8000 listener was not completed.
- **Frontend:** `npm run build` passed (289.12 kB JS / 90.01 kB gzip; 17.45 kB CSS / 3.93 kB gzip). No frontend source was changed for this fix.
- **OCR and API smoke:** the installed Tesseract 5.5.3.20260724 + pytesseract path was exercised by backend tests. A separate smoke test against a disposable SQLite file passed signup, unknown-drug verification warning, and persisted history warning; the temporary database and sidecars were removed. The existing `backend/hpv.db` was not used for test rows.
- **Python/dependencies:** CPython 3.13.5, the declared default runtime dependencies plus pytest are installed in the existing virtual environment; `python -m pip check` passed. No alternate OCR engine was installed. Anthropic, Psycopg, and Alembic optional paths were not installed or exercised.
- **PostgreSQL:** no database endpoint was configured; PostgreSQL tests were skipped and no connection, migration, or data copy occurred. SQLite remains the default. The migration path remains unverified against a real PostgreSQL server.
- **48-case regression:** in-process execution with `EMBEDDING_BACKEND=tfidf` yielded full-pipeline accuracy/violation recall 1.0 and false-positive rate 0; no-agent and retrieval-only accuracy 0.333 and recall 0. SHA-256 of the pre-existing `evaluation_report.json` remained `9BA7A698AC4E425514838D37455C1052B8446673F4CD59378894CDA25C8CC010`. This synthetic, self-derived rule regression is not independent quality evidence.
- **15-query retrieval evaluation:** actual BGE-large embeddings, persisted Chroma, and BM25 were compared to TF-IDF using the same queries. Hybrid: P@5 0.213, R@5 1.000, MRR@5 0.911, nDCG@5 0.928; init 17.725 s; mean/median/p95 query latency 124.27/126.34/134.05 ms. TF-IDF: P@5 0.213, R@5 1.000, MRR@5 0.911, nDCG@5 0.933; init 0.066 s; mean/median/p95 0.74/0.62/1.23 ms. These source-title labels are not clinical judgments.
- **Environment/report preservation:** all PostgreSQL connection variables were unset; the existing 48-case report hash was unchanged. The PostgreSQL opt-in test skipped, and no PostgreSQL connection, migration, or copy occurred. The live exact-case request used only the disposable SQLite database. An earlier application-module import invoked the existing `init_db()` which calls `create_all()` on the default SQLite path; no test records were written, but no byte-level file-integrity comparison was captured. This workspace has no Git repository metadata, so a Git status/diff review was unavailable; the changed source, test, and documentation files listed above were reviewed directly. `frontend/dist` contains generated build output and was not included in the source-file list.

## 11. Risks, migration, and rollback

- **Chroma change:** existing persistent files are retained, so rollback is code-only: restore the previous `get_or_create_collection("protocols")` selection. The active code creates a new collection snapshot; do not delete old/new collections until backed up and the currently selected corpus/model is verified. No vector migration or destructive deletion was performed.
- **Database evolution:** before adding the suggested SQLite index or enabling foreign-key enforcement on an existing deployment, back up `hpv.db`, use a versioned migration, test foreign-key violations and history queries on a copy, then deploy. Rollback should restore the backed-up database and prior application version. For PostgreSQL migration, export/import into a new database, validate row counts, relationships, JSON results, timestamps, and user access before cutover; retain the original SQLite file for rollback.
- **Embedding/model changes:** any model replacement or revision change requires a fresh versioned collection and independent relevance evaluation. Keep the old collection until the candidate passes evaluation.
- **Clinical content:** update interaction or monitoring rules only with traceable, licensed, reviewed sources. Keep dated copies and a review/rollback process; do not treat an ingestion script’s successful parse as clinical validation.
- **Verification behavior changed intentionally:** unknown and incompletely parsed medication mentions now generate warnings and are never treated as evidence of safety; composite laboratory requirements require all components and report any missing components. Typed text with an explicit investigations section now contributes ordered tests alongside the separate UI field. Existing result fields are preserved with additive details. Regression coverage passed, but there has been no independent clinician review or clinical validation.

## 12. Technologies to keep

- **SQLAlchemy:** appropriate ORM for relational users/history; database scale choice is separate.
- **SQLite:** appropriate for local demos and the current tiny relational dataset; PostgreSQL becomes relevant only for a real multi-instance deployment.
- **Chroma + local embeddings + BM25:** appropriate at the observed 64-vector scale, simple to deploy, and compatible with local operation. The correctness issue was stale index lifecycle, not proof that Chroma is too small or slow.
- **React/Vite/FastAPI:** current UI/API stack builds cleanly and fits the application. No evidence supports a framework rewrite.
- **Deterministic structured checks:** retain rules as the source of violation decisions; use LLMs only as explicitly optional parsers or presentation helpers subject to privacy and validation review.
- **No extra infrastructure:** Redis, task queues, microservices, managed vector databases, and pgvector would add operational cost without a measured bottleneck or scale requirement.

## 13. Phase 2 refresh: current correctness, performance, and migration readiness

This section records a fresh review of the current workspace and supersedes older test and timing numbers above where they differ. It does not overwrite the synthetic evaluation report or any database records.

### Current flow and targeted correctness fix

The React `Verifier` submits `raw_text`, `diagnosis_hint`, and `ordered_tests` through `frontend/src/api.js` to the protected synchronous `/api/verify` route in `backend/main.py`. The route extracts tests from the raw text, merges them with the explicit field, runs the lazily compiled LangGraph, and saves the complete result through a request-scoped SQLAlchemy session. The graph parses, retrieves protocol chunks, checks interactions/contraindications, checks required monitoring components, then explains findings. The configured retriever is also a per-process lazy singleton.

A direct run of the real pipeline with `raw_text=""` and with whitespace-only text returned no parsed drugs, no warnings, no violations, and the success-shaped text “The prescription appears consistent...” with unrelated protocol citations. This is unsafe because an empty input is not a verified prescription. The API now rejects whitespace-only prescription text with HTTP 422 before extraction, pipeline execution, or history saving. Missing `raw_text` and non-list `ordered_tests` continue to return FastAPI/Pydantic 422 responses. The frontend already catches API errors and displays the returned `detail` in its `role="alert"` banner; no frontend change was necessary.

Changed files for this phase:

| File | Change |
|---|---|
| `backend/main.py` | Reject blank/whitespace-only prescription text with a clear 422 response. |
| `backend/tests/test_verify_api.py` | Add HTTP-level regressions for blank, missing, and malformed request fields; existing multiline/lab merge regression remains. |
| `backend/tests/test_hybrid_retriever.py` | Isolate Chroma test state and use non-degenerate test vectors so approximate-index ties and module reloads do not contaminate later pipeline tests. |
| `backend/benchmark/run_api_performance.py` | Add a reproducible synthetic cold/warm API benchmark that uses a disposable SQLite database and prints only. |
| `docs/TECH_STACK_AND_ARCHITECTURE_AUDIT.md` | Add this Phase 2 evidence, recommendation, and verification record. |

No other backend or frontend implementation was changed in this phase. The workspace has no `.git` metadata; `git status` and `git diff` therefore cannot be used to distinguish these edits from earlier workspace changes.

### Fresh functional results

| Check | Result |
|---|---|
| Backend baseline before this phase's new blank-input tests | `54 passed, 1 skipped` |
| Focused safety, extraction, and verify-API suite after the fix | `30 passed` |
| Full backend suite after the fix | `57 passed, 1 skipped` |
| Frontend `npm run lint` | Exit 0; two existing `AuthContext.jsx` warnings (`only-export-components` and `set-state-in-effect`). |
| Frontend `npm run build` | Exit 0; Vite production build completed. |
| Frontend unit tests | Not available: `frontend/package.json` has no test script or frontend test files. |
| PostgreSQL integration | Skipped because `TEST_DATABASE_URL` is not configured. No PostgreSQL connection, Alembic migration, or data copy was attempted. |

The full test suite includes the unsupported-medication warnings, combined laboratory components and aliases, exact multiline investigation extraction, API test merging, OCR, SQLite-focused code, and the opt-in PostgreSQL test module. An intermediate full run exposed a brittle hybrid-retriever test fixture: a fake 8-dimensional Chroma collection leaked across module reloads and degenerate vectors made the approximate index return tied candidates unpredictably. The tests now use per-test Chroma directories, monkeypatch module state without reloading it, restore the fake embedding module, and use a unique nearest vector. The production retrieval code was not changed. The related tests pass together with their preceding DDInter tests, and the final complete suite passes. The 48-case synthetic rule benchmark was rerun in memory after the change: full pipeline case accuracy 1.000, violation recall 1.000, false-positive rate 0.000, and 1.000 case accuracy in each of its five categories. `backend/benchmark/evaluation_report.json` was not rewritten; its SHA-256 remained `9ba7a698ac4e425514838d37455c1052b8446673f4cd59378894cda25c8cc010`. This generated dataset is templated and self-derived, not held-out or clinically validated. Natural-language parser/API regressions are present in pytest, but they are not an independently labeled natural-language benchmark.

### Performance baseline and limits

Measurements used the existing Python 3.13.5 virtual environment on Windows and synthetic text only. The default `bge` mode used the actual BGE-large model, persistent Chroma collection, and BM25 hybrid retriever. These are local measurements, not deployment SLOs; CPU/GPU model, concurrent load, and production network conditions were not characterized.

The reproducible API measurement is implemented by `backend/benchmark/run_api_performance.py`. It overrides the database with a disposable temporary SQLite file, creates a synthetic test user, submits one cold request and five warm requests for the same Lisinopril text, then measures individual stages once after warming. Latest run:

| Measurement | Result | Interpretation |
|---|---:|---|
| Cold first `/api/verify` request | 15,553 ms (1 sample) | Includes lazy model/retriever and graph initialization; cold start is much slower than warm requests. |
| Warm API requests | 140.92, 130.35, 132.88, 204.29, 162.16 ms (5 samples) | Mean 154.12 ms; median 140.92 ms; min/max 130.35/204.29 ms. |
| Investigation extraction / parser / retrieval / cross-check / missing-tests / explanation | 0.05 / 0.20 / 175.41 / 0.01 / 0.06 / 0.03 ms (one sample per stage after warm-up) | Retrieval was the largest isolated stage sample, but it exceeded end-to-end warm latency; this demonstrates that a single stage sample is noisy and is not a valid API decomposition. |

The existing 15-query retrieval evaluator was freshly rerun using real BGE embeddings, Chroma, and BM25 against TF-IDF; it prints rather than writes. Hybrid initialization was 20.916 s and query mean/median/p95 were 134.83/132.36/156.15 ms. TF-IDF initialization was 0.103 s and query mean/median/p95 were 0.99/0.84/1.97 ms. Both had P@5 0.213, R@5 1.000, and MRR@5 0.911; nDCG@5 was 0.928 hybrid and 0.933 TF-IDF. These judgments label guideline titles, not clinical relevance.

OCR timing was not measured; OCR is not exercised in the synthetic API benchmark. Frontend rendering/network delay was not measured in a browser. Database query latency was not benchmarked against the existing database or its user data. No before/after performance gain is claimed, because no performance optimization was made. The graph and retriever already cache initialization within a process. Cold startup and dense retrieval are the measurable expensive operations, but the stage sample variability prevents attributing precise shares of end-to-end latency. Whether model warm-up, a smaller model, or an alternate retrieval strategy is worthwhile needs a deployment latency target and repeated representative workload.

### Database and persistence assessment

SQLite remains the active default; SQLAlchemy ORM stores users and verification history, while Chroma remains a separate persisted vector store. PostgreSQL is opt-in via environment configuration, has two Alembic revisions, and is expected to fail startup if the schema is not at the supported revision. The currently observed SQLite database artifact is 110,592 bytes; its row contents were not inspected as part of this phase.

The history endpoint filters by `user_id`, orders newest-first by `created_at`, and limits to 50. A query-plan check against a separate in-memory schema showed a full `verification_history` scan and a temporary B-tree for ordering; the only SQLite history index in that schema was the primary-key index on `id`. The composite `(user_id, created_at)` index exists in the PostgreSQL migration path but is not defined for SQLite. This is a real plan-level scaling issue, but the current SQLite dataset is small and no representative query-time impact was established. No index or schema change was applied; when history volume justifies it, add a versioned SQLite-compatible migration, back up the existing file, and compare query plans and timings on a copy before rollout.

SQLAlchemy sessions are created per request and closed in the dependency cleanup path. Verification history is committed as one transaction; `save_verification` rolls back on SQLAlchemy errors. PostgreSQL uses `pool_pre_ping`, but pool sizing and concurrent-write behavior remain unmeasured. The app does not silently fall back from PostgreSQL to SQLite when a PostgreSQL URL is selected. These properties are code-reviewed only; real PostgreSQL behavior remains unverified.

### Security and reliability findings

These are code/configuration findings, not claims that an exploit was demonstrated. Fix high-priority deployment issues before handling real patient data.

| Priority | Evidence | Finding and recommended action |
|---|---|---|
| High | `backend/src/auth.py` | `JWT_SECRET_KEY` falls back to a fixed development value. A deployment that omits the variable shares a predictable signing key. Fail startup in production mode when a strong secret is absent; inject it through a secret manager and rotate it. No change was made because production/development mode and deployment configuration are not defined here. |
| High (correctness, fixed) | `backend/main.py`, empty-input runtime reproduction | Empty and whitespace-only text previously produced an unqualified “no violations” result. The API now returns 422; an HTTP regression proves the pipeline is not called for these inputs. |
| Medium | `frontend/src/context/AuthContext.jsx` | Bearer JWT is stored in `localStorage`, where same-origin injected JavaScript could read it. Consider a deliberately designed HttpOnly/Secure cookie migration with CSRF controls before production; no cookie/auth protocol redesign was attempted. |
| Medium | `backend/main.py` `VerifyRequest` | There is no application-level maximum for `raw_text` or the number/length of `ordered_tests`. Apply request/body limits at the reverse proxy and explicit schema limits selected from real document requirements. The OCR route has an 8 MiB application read cap, but this does not bound JSON verification requests. |
| Medium | `backend/main.py` `/api/ocr` | The route is `async` but invokes synchronous image decoding/Tesseract directly. Under concurrent OCR, CPU work can block the event loop. Measure concurrent upload behavior, enforce pixel/decompression and proxy limits, and offload CPU work if deployment tests confirm contention. |
| Medium (scale) | SQLite query-plan check | Per-user history query currently scans and sorts on SQLite as described above. Add an index through a versioned migration only when validated against representative history volume. |
| High before production | `backend/main.py`, database and frontend configuration | CORS is hard-coded to localhost origins, there is no login throttling, and verification history retains prescription text/results without configured retention or encryption-at-rest policy. Establish production origins, HTTPS, throttling, retention/access controls, backups, and privacy review before real data. |

External FDA HTTP requests use configured timeouts and live FDA retrieval is off by default. OCR file bytes are bounded in the application. No real network external-data path, Anthropic path, or concurrency/load behavior was exercised.

### Technology choices and recommendations refreshed

| Component | Current | Alternative | Recommendation |
|---|---|---|---|
| Relational data | SQLite + SQLAlchemy ORM | PostgreSQL + same SQLAlchemy models | **Keep** SQLite for local/single-instance use; **Consider replacing** only for multi-instance/concurrent production, after real PostgreSQL tests and data-copy validation. |
| Vector storage | Persistent Chroma; 64 corpus vectors in the earlier inspected snapshot | pgvector or FAISS | **Keep** Chroma; no size, filtering, or operations evidence justifies replacing it. PostgreSQL is not to replace Chroma. |
| Embeddings/retrieval | BGE-large + Chroma dense search + BM25; TF-IDF offline alternative | Smaller local embedding model, BM25/TF-IDF, or another fusion | **Optimize by evaluation**, not replacement. Latest title judgments show similar ranking metrics but substantially lower TF-IDF latency/startup; they are not clinician relevance judgments. |
| Model lifecycle | Lazy singleton per process | Explicit startup warm-up or smaller model | **Optimize only to a deployment SLO**; first request was ~20.7 s, warm API ~131 ms. No model replacement or startup behavior change in this phase. |
| Backend | FastAPI + LangGraph | Another framework or microservices | **Keep**; current boundaries are adequate, with a targeted blank-input validation fix. |
| Frontend | React + React Router + Vite + CSS | SSR or another SPA framework | **Keep**; build succeeds and the API error detail is already surfaced. No frontend test runner is configured. |
| OCR | Pillow + pytesseract calling system Tesseract | Cloud OCR / another engine | **Keep** local OCR; no evidence supports an engine replacement. Address resource limits and event-loop blocking based on load testing. |
| Cache/jobs | Per-process graph/retriever singletons; no distributed cache or queue | Redis / task queue | **Not needed** on current evidence; avoid patient-result caching and extra infrastructure. |
| Authentication | bcrypt + HS256 JWT in localStorage | HttpOnly secure session/cookie with CSRF design | **Optimize before production**; fixed default key and browser token storage are material risks. |

### PostgreSQL readiness, migration sequence, and rollback

No PostgreSQL server connection, Alembic command, data copy, or application cutover occurred. The integration test was skipped because `TEST_DATABASE_URL` was unset. Runtime inspection confirmed that `psycopg` and Alembic are not installed in the selected Python 3.13.5 environment; they are optional in `backend/requirements.txt`. The actual PostgreSQL path is therefore not validated by the passing SQLite/default suite.

The migration plan remains:

1. Provision a dedicated PostgreSQL test database and inject credentials using `DATABASE_URL` or the `DB_*` environment variables; do not put secrets in source or shell history.
2. Install only the PostgreSQL/migration test extras (`psycopg[binary]`, `alembic`, `pytest`, and `httpx`) in the selected backend virtual environment.
3. Review the current two migration revisions and inspect a backup/copy of the SQLite schema. Run `alembic upgrade head` against an empty, dedicated PostgreSQL database only.
4. Run `tests/test_postgres_integration.py` with `TEST_DATABASE_URL` pointing only to that database. It covers SQLAlchemy CRUD and signup/login/me/verify/history integration, not performance or production concurrency.
5. For data preservation, stop writes, make and verify a separate SQLite backup, dry-run `scripts/migrate_sqlite_to_postgres.py`, compare counts and integrity, then explicitly use its `--apply` option against the new empty PostgreSQL target. Original SQLite remains unchanged.
6. Validate authentication, history ordering, timestamps, foreign-key behavior, transactions, multi-request concurrency, and API tests; verify the runtime dialect is PostgreSQL and its Alembic revision matches the code.
7. Cut over only after approval. Retain the SQLite original/backup. Before PostgreSQL accepts writes, rollback can point back to SQLite. After PostgreSQL writes begin, do not simply switch back; reconcile/export writes or restore an approved backup first.

Full environment setup, commands, safeguards, and rollback details are in [`POSTGRESQL_MIGRATION.md`](./POSTGRESQL_MIGRATION.md). SQLite remains the default and no database architecture was changed in this phase.

### Reproduction commands

From the `backend` directory with the project virtual environment active:

```powershell
python -m pytest -q
python -m pytest -q tests/test_verify_api.py tests/test_safety_regressions.py tests/test_prescription_extract.py
python benchmark/run_api_performance.py
python benchmark/run_retrieval_evaluation.py
```

The 48-case CLI `python benchmark/run_evaluation.py` writes `evaluation_report.json`; use this in-memory command when the existing report must remain untouched:

```powershell
python -c "import os; os.environ['EMBEDDING_BACKEND']='tfidf'; from benchmark.run_evaluation import load_cases, SYSTEMS, evaluate; cases=load_cases(); print({name: evaluate(fn, cases) for name, fn in SYSTEMS.items()})"
```

From the `frontend` directory:

```powershell
npm run lint
npm run build
```

The API performance runner uses TestClient and the installed test dependencies; it will load the configured real retrieval backend, use an automatically deleted temporary SQLite file, and print timing results without writing a report.

## 14. Follow-up performance and PostgreSQL readiness review

This is a separate follow-up to the preceding Phase 2 refresh. It was measured against the current workspace and only makes process-initialization and test-isolation changes; it does not alter the database configuration or clinical verification behavior.

### Repeated loading and initialization

- `backend/src/agents/cross_check_agent.py` loads and optionally merges `interactions.json` and `interactions_ddinter.json` once when the module is imported.
- `backend/src/agents/missing_test_agent.py` loads `monitoring_requirements.json` once at module import.
- `backend/src/vector_store.py` reads and parses guideline Markdown when constructing a retriever. It then caches the retriever in a module global. The expensive BGE model is likewise constructed by that retriever, not per query.
- `backend/src/graph.py` caches its compiled LangGraph after first use.
- `Verifier` loads the sample list once on mount, and calls verification once when the user explicitly submits. The API and history calls do not trigger repeated verification by themselves. No patient-specific results are cached.

The `get_retriever()` and `get_graph()` lazy singleton checks were unsynchronized. An 8-thread barrier probe before the fix observed **8 constructor calls and 8 different instances** for each on simultaneous first use (34.30 ms retriever / 32.59 ms graph total probe duration). This could cause concurrent duplicate model loads, guideline parsing, Chroma initialization, and graph compilation. Both getters now use a lock with a second `None` check inside the lock. The same probe after the fix observed **1 constructor call and 1 shared instance** for each resource (32.65 ms retriever / 31.92 ms graph). These synthetic constructor delays are not the benefit metric: the verified result is preventing seven duplicate initializations under the same simultaneous-start condition.

The process-level caches are immutable for that process lifetime. There is no live file watcher or hot reload of JSON/Markdown knowledge data. Development reload or a controlled application restart is the invalidation mechanism; production knowledge updates must restart workers so every process loads the same corpus/rules. This phase did not introduce live reload because mutating rule and retrieval state during concurrent verification could yield mixed-version results.

### Performance measurements after locking

The same runner and synthetic Lisinopril input were used before and after. Results are local to Python 3.13.5 on Windows, with real BGE/Chroma and a disposable SQLite API database. The before figures below are the fresh run recorded in section 13 immediately before this optimization; after figures are a new run after it.

| Measure | Before | After | Conclusion |
|---|---:|---:|---|
| Cold first API request | 15,553 ms | 16,372 ms | Within noisy single-sample variation; locks do not materially change a single-caller cold start. |
| Five warm API calls, mean / median | 154.12 / 140.92 ms | 189.48 / 186.85 ms | No warm latency improvement is demonstrated; later run was slower and variable. Do not attribute a regression to the lock from these small samples. |
| Isolated retrieval sample | 175.41 ms | 150.83 ms | One sample each, noisy; not sufficient to claim improvement. |
| 15-query hybrid init; query mean / median / p95 | 20.916 s; 134.83 / 132.36 / 156.15 ms | 16.118 s; 148.48 / 132.92 / 239.48 ms | Initialization and latency variability are substantial; retrieval metrics are unchanged. |
| Synthetic title-ranking P@5 / R@5 / MRR@5 / nDCG@5 | 0.213 / 1.000 / 0.911 / 0.928 | 0.213 / 1.000 / 0.911 / 0.928 | Same rankings/metrics; this optimization affects initialization concurrency only. |

The retriever comparison’s TF-IDF metrics remained P@5 0.213, R@5 1.000, MRR@5 0.911, and nDCG@5 0.933; its initialization/query mean/median/p95 were 0.049 s and 2.14/1.96/3.59 ms in the after run. Title-based labels are not clinical judgments. Do not replace BGE solely on these results.

### Changes and validation

Files changed in this follow-up:

| File | Change |
|---|---|
| `backend/src/graph.py` | Serialize compiled-graph lazy construction with a lock. |
| `backend/src/vector_store.py` | Serialize retriever/model/Chroma lazy construction with a lock. |
| `backend/tests/test_lazy_initialization.py` | Add an 8-thread regression asserting one construction and a shared instance for each singleton. |
| `backend/tests/test_hybrid_retriever.py` | Isolate temporary Chroma directories, avoid reloading global modules, restore the fake model with monkeypatch, and avoid degenerate vectors that caused test-order contamination. |
| `backend/tests/test_live_retrieval_integration.py` | Convert collection-time assertions into a pytest test and patch the imported feature flag directly, so behavior is independent of whether the retriever module was imported before test collection. |
| `docs/TECH_STACK_AND_ARCHITECTURE_AUDIT.md` | Record the follow-up evidence and migration-readiness status. |

Fresh validation before the optimization: backend `57 passed, 1 skipped`; frontend lint/build passed (lint retained its two existing `AuthContext.jsx` warnings). After the optimization, the focused singleton/retriever/pipeline tests passed `12 passed`; after isolating the hybrid test fixture, the complete backend suite passed `57 passed, 1 skipped`. The frontend has no configured test script. No benchmark report or database contents were changed.

During final validation, the focused tests first exposed a missing `Path` import after simplifying the hybrid test imports; it was restored. The same final suite also exposed a separate order-dependent live-retrieval integration test: it set `src.config.LIVE_FDA_RETRIEVAL_ENABLED` after `retriever_agent` may already have imported the flag by value. The test now patches the actual imported module symbol and runs as a normal pytest test rather than executing assertions at module import. Final run: focused singleton/retriever/pipeline/live-wiring suite `13 passed`; full backend suite `60 passed, 1 skipped`. Final frontend lint/build both exit 0; lint still reports only the two pre-existing warnings in `frontend/src/context/AuthContext.jsx`.

### PostgreSQL readiness — audit only

The current relational data is in SQLAlchemy ORM tables `users` and `verification_history`. Prescription input and full results are stored in `raw_text` and JSON-encoded `result_json` text, not in Chroma. Chroma is a separate persistent local vector store. Clinical interaction and monitoring rules are JSON; protocol documents are Markdown; the optional DDInter ingestion output is a separate JSON file. SQLite is the default; `DATABASE_PATH` can choose its file. `DATABASE_URL` takes precedence, or `DB_DIALECT=postgresql` with `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` composes a Psycopg 3 URL. SQLite receives `check_same_thread=False`; PostgreSQL uses `pool_pre_ping`. SQLAlchemy sessions are request-scoped, closed in `finally`, and rolled back for uncaught dependency exceptions. History writes commit per verification and roll back on SQLAlchemy errors.

The checked-in Alembic chain has:

1. `0001_relational_baseline`: creates users, verification history, unique email, primary keys, and history-to-user foreign key.
2. `0002_history_user_created_at_idx`: adds `(user_id, created_at)` for per-user newest-first history.

The application checks the PostgreSQL schema revision on startup and does not silently fall back to SQLite. Alembic blocks SQLite unless `ALEMBIC_ALLOW_SQLITE=true`. PostgreSQL options remain optional: runtime inspection found `psycopg` and `alembic` absent, and no `TEST_DATABASE_URL` was configured. The PostgreSQL integration test is therefore skipped. No PostgreSQL server was installed or contacted; no migration, connection, data copy, or active database switch was performed.

Readiness gaps and deployment considerations:

- Run migrations against a new disposable PostgreSQL database before application startup; test every migration on the target PostgreSQL major version.
- Install optional Psycopg 3 and Alembic only when preparing that test environment. Inject passwords with a secret manager/process environment; do not check them into `.env`, source, or shell history.
- Review migration parity against the SQLAlchemy models. The baseline migration has nullable timestamps/default semantics that should be explicitly checked for parity; `create_all()` is not used for PostgreSQL.
- The migration path has a safe explicit SQLite-to-PostgreSQL copy utility: quiesce writes, make and verify a separate SQLite backup, migrate an empty PostgreSQL target, dry-run counts, then explicitly apply. Keep the original SQLite file and validate counts, relationships, JSON, timestamps, and authentication/history behavior.
- Exercise the opt-in PostgreSQL CRUD and API integration test with only a dedicated test database, then add concurrency/transaction testing and verify the runtime dialect/revision before cutover.
- History query uses `WHERE user_id = ... ORDER BY created_at DESC LIMIT 50`. A composite history index exists in migration 0002 for PostgreSQL, but the current SQLite metadata path does not create it; SQLite query-plan inspection previously showed scan plus temporary sort. Do not change schema in this task; decide on SQLite index only after representative history volume/query benchmarks.
- `pool_pre_ping` is configured, but pool sizes/timeouts, write concurrency, recovery, and real PostgreSQL performance remain unmeasured.
- Before cutover, snapshot and validate the old SQLite database. Before PostgreSQL accepts writes, rollback can restore the prior SQLite configuration. After PostgreSQL writes begin, switching back risks losing writes; reconcile an approved delta/backup before rollback.

The detailed Windows setup, environment variables, test commands, copy safeguards, and rollback procedure remain in [`POSTGRESQL_MIGRATION.md`](./POSTGRESQL_MIGRATION.md). No database configuration or migration file was changed by this follow-up.
