# SQLite to PostgreSQL migration (opt-in)

This guide is for moving the application's **relational** data only. SQLAlchemy remains the ORM and ChromaDB remains the vector store. SQLite stays supported and remains the default when no PostgreSQL configuration is supplied.

## Current and proposed architecture

| Area | Current | Proposed when explicitly enabled |
|---|---|---|
| Relational engine | SQLite file `backend/hpv.db` | PostgreSQL selected from environment |
| ORM / models | SQLAlchemy ORM (`users`, `verification_history`) | Same models and ORM |
| Schema setup | SQLite `create_all()` compatibility behavior | Explicit, versioned Alembic revisions; the API refuses an unmigrated PostgreSQL schema |
| User identity | Unique email, bcrypt hash, integer ID | Preserved; primary keys and password hashes are copied |
| Verification history | User FK, prescription input, JSON result text | Same fields and IDs; per-user/newest-first index added |
| Protocol vectors | Persistent ChromaDB | Unchanged; PostgreSQL stores no vectors |

This is appropriate if the next deployment needs a server database, multiple API instances, centralized backup/monitoring, or more concurrent writes. The current SQLite database is only 32 KiB with two users and two history rows at audit time, so no existing scale measurement alone requires the migration.

## Environment configuration

Use a secret store or process-level secret injection for credentials. Do not place a database password in source control, this document, shell history, or a checked-in `.env` file.

Either provide the SQLAlchemy URL directly:

```text
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>
```

or provide separate environment variables (the code composes/escapes the URL using SQLAlchemy):

```text
DB_DIALECT=postgresql
DB_HOST=<host>
DB_PORT=5432
DB_NAME=<database>
DB_USER=<user>
DB_PASSWORD=<secret-injected-value>
```

`DATABASE_URL` takes precedence. If neither PostgreSQL configuration is supplied, the existing `DATABASE_PATH`/`hpv.db` SQLite behavior remains active. SQLite uses `check_same_thread=False`; PostgreSQL uses connection-pool pre-ping. Per-request SQLAlchemy sessions are closed after each request and rolled back on an uncaught request exception.
The application normalizes `postgres://` and `postgresql://` URLs to the Psycopg 3 SQLAlchemy driver. If supplying `DATABASE_URL` directly, percent-encode reserved characters in credentials; the split `DB_*` configuration uses SQLAlchemy URL construction and safely handles them.

The existing schema uses timezone-naive `created_at` columns. The application now stores these values as naive UTC (converting from UTC explicitly) so PostgreSQL does not interpret an aware timestamp according to the server/session timezone. This preserves the existing SQLite column behavior and requires no schema migration.

### Local Windows test setup

1. Install PostgreSQL with the official Windows installer from
   [postgresql.org/download/windows](https://www.postgresql.org/download/windows/),
   or provision a dedicated disposable PostgreSQL test database. Keep the
   existing application database and production data out of this test setup.
2. In SQL Shell (`psql`), connect as a local PostgreSQL administrator and run:

   ```sql
   CREATE ROLE hpv_test LOGIN;
   \password hpv_test
   CREATE DATABASE hpv_test OWNER hpv_test;
   ```

   `\password` prompts securely; use a unique test-only password. If the role
   or database already exists, inspect it rather than dropping or reusing it.
3. From a PowerShell window, change to `backend` and configure process-scoped
   credentials. These values disappear when the window closes:

   ```powershell
   $env:DB_DIALECT = "postgresql"
   $env:DB_HOST = "localhost"
   $env:DB_PORT = "5432"
   $env:DB_NAME = "hpv_test"
   $env:DB_USER = "hpv_test"
   $env:HPV_TEST_DATABASE_CONFIRMATION = "I_CONFIRM_THIS_IS_A_DISPOSABLE_TEST_DATABASE"
   $secure = Read-Host "PostgreSQL test password" -AsSecureString
   $env:DB_PASSWORD = [System.Net.NetworkCredential]::new("", $secure).Password
   ```

4. Create an isolated Python environment if the project environment is not
   already prepared, activate it, and from `backend` install the application
   and optional PostgreSQL/test dependencies. Do not use `pip` from an
   unrelated global Python installation:

   ```powershell
   python -m pip install -r requirements.txt
   python -m pip install "psycopg[binary]>=3.1.18" "alembic>=1.13.0" "pytest>=8.0.0" "httpx>=0.27.0"
   ```
5. Run `alembic upgrade head` from `backend`. This creates schema in the
   explicitly configured empty `hpv_test` database; it does not copy data.
6. Construct the opt-in integration test URL in the same PowerShell process
   without putting the password in the command text:

   ```powershell
   $env:TEST_DATABASE_URL = & python -c "import os; from sqlalchemy import URL; print(URL.create('postgresql+psycopg', username=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], host=os.environ['DB_HOST'], port=int(os.environ['DB_PORT']), database=os.environ['DB_NAME']).render_as_string(hide_password=False))"
   pytest -q tests/test_postgres_integration.py
   ```

   The integration test also requires the explicit confirmation variable
   above, a database name with `test` as a delimited word (for example
   `hpv_test`), and the Psycopg driver. It rejects non-PostgreSQL URLs. The
   test creates and deletes uniquely named rows but does not create/drop
   tables; use only a disposable database. Clear credentials when finished:

   ```powershell
   Remove-Item Env:DB_DIALECT, Env:DB_HOST, Env:DB_PORT, Env:DB_NAME, Env:DB_USER, Env:DB_PASSWORD, Env:TEST_DATABASE_URL, Env:HPV_TEST_DATABASE_CONFIRMATION -ErrorAction SilentlyContinue
   ```

The PostgreSQL driver is optional and is not installed by SQLite-only users:

```powershell
python -m pip install "psycopg[binary]>=3.1.18" "alembic>=1.13.0"
```

Alembic and the Psycopg 3 driver are optional commented requirements in `backend/requirements.txt`; install them only for PostgreSQL use. Use a supported PostgreSQL server version and provision the database and least-privilege application/migration roles through the deployment platform.

## Schema and migration commands

Run commands from `backend`. Alembic uses the same database environment as the application. It does not run automatically at application startup.

For an empty PostgreSQL database:

```powershell
alembic upgrade head
```

The revisions are:

1. `0001_relational_baseline`: creates the current `users` and `verification_history` tables, unique email index, and existing indexes/foreign key.
2. `0002_history_user_created_at_idx`: adds `(user_id, created_at)` for the history query. It checks for an existing index first to support safe adoption of the current SQLite schema.

The API verifies the PostgreSQL `alembic_version` on startup and refuses to start if migrations have not been applied or are not at the application’s expected revision. The SQLite path retains `create_all()` for compatibility and is not migrated by the API.

Alembic refuses to target SQLite by default, preventing an accidental migration
of the SQLite default. For the existing SQLite database only, if you elect to
manage its schema with Alembic, first stop application writes, make and verify
a separate backup, confirm its schema matches this project’s baseline, then
deliberately opt in:

```powershell
$env:DATABASE_PATH = "<path-to-existing-sqlite-copy>"
$env:ALEMBIC_ALLOW_SQLITE = "true"
alembic stamp 0001_relational_baseline
alembic upgrade head
```

Do not stamp a database whose schema has not been inspected. Stamping records a version; it does not create or validate the baseline tables. This adoption procedure is optional and not needed to keep using SQLite.

## Safe SQLite data copy

The project does not migrate data automatically. Use a **new, empty PostgreSQL database**. The copy script requires an explicit source path, opens SQLite read-only, copies only the two application tables, retains IDs and stored result JSON, resets PostgreSQL sequences, and verifies row counts in one target transaction. A non-empty target is rejected; `--apply` is required to write.

1. Stop the application or otherwise quiesce writes.
2. Make a separate SQLite backup and verify it can be opened. Do not modify or move the original `backend/hpv.db`. For example, use Python's SQLite backup API from a one-off trusted local command, writing to a new path with adequate protected storage.
3. Configure `DATABASE_URL` or `DB_*` for the new PostgreSQL database.
4. Run schema migrations:

   ```powershell
   alembic upgrade head
   ```

5. Dry run against the backup. The output contains counts only, not user data:

   ```powershell
   python scripts/migrate_sqlite_to_postgres.py --sqlite-path "<path-to-sqlite-backup>"
   ```

6. Review the source/target counts and confirm the target is the intended empty database. Only then copy:

   ```powershell
   python scripts/migrate_sqlite_to_postgres.py --sqlite-path "<path-to-sqlite-backup>" --apply
   ```

7. Validate user login, `/api/auth/me`, `/api/verify`, `/api/history`, row counts, ID/sequence behavior, and application logs before cutover. Keep the original and backup SQLite files protected and unchanged until acceptance.

The script never prints email addresses, prescription text, password hashes, or verification results. A copy failure rolls back the PostgreSQL transaction; SQLite remains read-only. The script refuses a target with existing rows, even when those rows have non-conflicting IDs.

The migration preserves stored `result_json` text and integer IDs. The current `DateTime` columns have no timezone flag; values are preserved as the existing naive timestamps, not reinterpreted. Review timestamp semantics before any future conversion to timezone-aware columns.

## Constraints, indexes, transactions, and errors

- `users.email` is unique and non-null; signup retains the friendly duplicate check and also catches a concurrent unique constraint violation, rolls back, and returns the existing duplicate-account response.
- `verification_history.user_id` is non-null and references `users.id`; SQLAlchemy ORM relationship cascade behavior is unchanged. The database FK does not specify `ON DELETE CASCADE`.
- `verification_history` result JSON remains text for API compatibility; no JSON schema/data rewrite is attempted.
- The new `(user_id, created_at)` index supports the filtered newest-first history query. No schema index is claimed to have a measured speedup at the present two-row scale.
- `save_verification` rolls back on SQLAlchemy persistence errors and re-raises them. The request session dependency rolls back uncaught failures and always closes the session.
- `pool_pre_ping` is enabled for PostgreSQL connections to detect stale pooled connections. Pool sizes and timeouts are not tuned without deployment concurrency/latency measurements.
- `Base.metadata.create_all()` is deliberately not used for PostgreSQL. Migration and connectivity errors surface rather than being silently converted into an empty database.

## PostgreSQL integration tests

The opt-in test `backend/tests/test_postgres_integration.py` requires a dedicated, non-production PostgreSQL database at the current migration head and the Python test dependencies. It performs SQLAlchemy user/history CRUD and calls signup, login, `/api/auth/me`, verify (with pipeline execution stubbed), and history endpoints. It deletes only the uniquely named test users it created; it does not create/drop tables or run migrations.

The test runner and FastAPI TestClient dependency (`pytest` and `httpx`) are
listed as test-only requirements in `backend/requirements.txt`. With a dedicated test database
configured by secret injection:

```powershell
$env:TEST_DATABASE_URL = $env:DATABASE_URL
alembic upgrade head
python -m pip install "pytest>=8.0.0" "httpx>=0.27.0"
pytest -q tests/test_postgres_integration.py
```

When `TEST_DATABASE_URL` is absent, this test module is skipped. Never point it at production data. A real PostgreSQL server/driver is required; SQLite tests or mocked engines do not count as PostgreSQL integration validation.

## Cutover, rollback, and data retention

1. Keep the original SQLite file and a verified backup unchanged.
2. Validate a PostgreSQL copy before cutover; do not serve writes from both engines.
3. Cut over by injecting PostgreSQL environment settings and restarting the API. Chroma configuration and persisted vectors remain unchanged.
4. If PostgreSQL fails **before accepting production writes**, stop the API and revert the database environment to the original SQLite path. PostgreSQL remains available for diagnosis.
5. If PostgreSQL has accepted writes, switching back to the old SQLite file would lose those writes. First stop writes, export/reconcile the delta using a separately reviewed reverse-copy process, or restore an explicitly approved backup. No reverse-copy tool is included because conflict and merge policy must be decided before production.
6. Do not use `alembic downgrade base` as a routine rollback: the baseline downgrade drops tables and is destructive. Database backups, not schema downgrade, are the rollback authority for production data.

No data copy, PostgreSQL connection, schema migration, or Alembic command was run as part of this change. PostgreSQL operation remains conditional until exercised against a real disposable PostgreSQL instance.
