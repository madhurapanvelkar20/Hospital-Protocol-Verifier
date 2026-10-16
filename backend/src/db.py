"""
Database layer: SQLAlchemy over SQLite (default) or explicitly configured
PostgreSQL. PostgreSQL schema setup uses Alembic and existing SQLite data
must be copied with the explicit migration script; see docs/POSTGRESQL_MIGRATION.md.

Two tables:
  - users: email, hashed password, display name, created_at
  - verification_history: one row per prescription verification a logged-in
    user has run, storing both the input and the full pipeline result
    (as JSON), so the History page can show past runs without re-running
    the pipeline.

---- Choosing a database: why not MongoDB? ----
This data is inherently relational: every verification_history row
belongs to exactly one user (a foreign key), and a real deployment would
add more linked tables (e.g. per-hospital protocol corpora, audit logs
referencing both users and verifications). MongoDB is the right tool when
data is document-shaped and doesn't fit a fixed schema well, or when you
need to shard across many servers for very large scale -- neither applies
here. A relational database enforces the user_id relationship at the
database level (a verification row literally cannot exist without a valid
user), which a schemaless document store would leave to application code
to get right every time. So the real upgrade for production isn't "move
off SQL" -- it's "move from SQLite to a server-based SQL database":

---- Choosing a database: why PostgreSQL over SQLite for production ----
SQLite is a single FILE, not a server -- fine for one process (this demo),
but it doesn't handle concurrent writes well (only one writer at a time,
enforced with file locks) and can't be accessed by more than one backend
instance at once. That's a real problem the moment this needs to run as
more than one process (e.g. multiple uvicorn workers, or a load-balanced
deployment) -- exactly what a real hospital system would need. PostgreSQL
is a proper client-server database: many backend processes can read and
write concurrently, it enforces the schema and foreign keys strictly, and
it's the standard choice for this kind of relational, multi-user
application in production.

To switch: set the DATABASE_URL environment variable, e.g.:
    export DATABASE_URL=postgresql://user:password@localhost:5432/hpv
and install the optional psycopg 3 driver. PostgreSQL schema changes must
be applied with Alembic, and existing SQLite data must be copied using
the explicit migration script. Nothing migrates automatically. Leave
DATABASE_URL unset to keep using SQLite (the default, for local dev/demo).
"""

import json
import os
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    URL,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session


def _normalize_database_url(configured_url):
    if configured_url.startswith("postgres://"):
        return "postgresql+psycopg://" + configured_url[len("postgres://") :]
    if configured_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + configured_url[len("postgresql://") :]
    return configured_url


def _database_url(environ=None):
    settings = os.environ if environ is None else environ
    configured_url = settings.get("DATABASE_URL")
    if configured_url:
        return _normalize_database_url(configured_url)

    dialect = settings.get("DB_DIALECT", "").strip().lower()
    if dialect == "postgresql":
        required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
        missing = [name for name in required if not settings.get(name)]
        if missing:
            raise RuntimeError(
                "PostgreSQL configuration is incomplete; set " + ", ".join(missing)
            )
        try:
            port = int(settings.get("DB_PORT", "5432"))
        except ValueError as error:
            raise RuntimeError("DB_PORT must be a valid integer") from error
        return URL.create(
            "postgresql+psycopg",
            username=settings["DB_USER"],
            password=settings["DB_PASSWORD"],
            host=settings["DB_HOST"],
            port=port,
            database=settings["DB_NAME"],
        )
    if dialect and dialect != "sqlite":
        raise RuntimeError(f"Unsupported DB_DIALECT: {dialect}")

    db_path = settings.get("DATABASE_PATH", "hpv.db")
    return f"sqlite:///{db_path}"


def _utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


DATABASE_URL = _database_url()
_IS_SQLITE = (
    DATABASE_URL.startswith("sqlite:")
    if isinstance(DATABASE_URL, str)
    else DATABASE_URL.get_backend_name() == "sqlite"
)

# SQLite needs this flag for use with FastAPI's per-request sessions;
# PostgreSQL (and other server-based DBs) don't use or accept it.
connect_args = {"check_same_thread": False} if _IS_SQLITE else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=not _IS_SQLITE,
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)
Base = declarative_base()

POSTGRES_SCHEMA_REVISION = "0002_history_user_created_at_idx"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow_naive)

    history = relationship("VerificationHistory", back_populates="user", cascade="all, delete-orphan")


class VerificationHistory(Base):
    __tablename__ = "verification_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    raw_text = Column(Text, nullable=False)
    diagnosis_hint = Column(String, nullable=True)
    result_json = Column(Text, nullable=False)  # full pipeline result, JSON-encoded
    violation_count = Column(Integer, default=0)
    highest_severity = Column(String, nullable=True)  # "high" | "medium" | "low" | None
    created_at = Column(DateTime, default=_utcnow_naive)

    user = relationship("User", back_populates="history")


if not _IS_SQLITE:
    Index(
        "ix_verification_history_user_created_at",
        VerificationHistory.user_id,
        VerificationHistory.created_at,
    )


def init_db():
    if _IS_SQLITE:
        Base.metadata.create_all(bind=engine)
        return

    if engine.dialect.name != "postgresql":
        raise RuntimeError(f"Unsupported database dialect: {engine.dialect.name}")

    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            if not inspector.has_table("alembic_version"):
                raise RuntimeError(
                    "PostgreSQL schema is not migrated. Run `alembic upgrade head` "
                    "from the backend directory before starting the API."
                )
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
            if revision != POSTGRES_SCHEMA_REVISION:
                raise RuntimeError(
                    "PostgreSQL schema revision is not supported by this application. "
                    "Run `alembic upgrade head` from the backend directory."
                )

            tables = set(inspector.get_table_names())
            required_columns = {
                "users": {
                    "id",
                    "email",
                    "display_name",
                    "hashed_password",
                    "created_at",
                },
                "verification_history": {
                    "id",
                    "user_id",
                    "raw_text",
                    "diagnosis_hint",
                    "result_json",
                    "violation_count",
                    "highest_severity",
                    "created_at",
                },
            }
            missing_tables = set(required_columns) - tables
            if missing_tables:
                raise RuntimeError(
                    "PostgreSQL schema is missing required table(s): "
                    + ", ".join(sorted(missing_tables))
                    + ". Run `alembic upgrade head` from the backend directory."
                )

            for table, expected_columns in required_columns.items():
                actual_columns = {
                    column["name"] for column in inspector.get_columns(table)
                }
                missing_columns = expected_columns - actual_columns
                if missing_columns:
                    raise RuntimeError(
                        f"PostgreSQL table {table!r} is missing required column(s): "
                        + ", ".join(sorted(missing_columns))
                        + ". Run `alembic upgrade head` from the backend directory."
                    )

            required_indexes = {
                "users": {"ix_users_email"},
                "verification_history": {
                    "ix_verification_history_user_created_at"
                },
            }
            for table, expected_indexes in required_indexes.items():
                actual_indexes = {
                    index["name"] for index in inspector.get_indexes(table)
                }
                missing_indexes = expected_indexes - actual_indexes
                if missing_indexes:
                    raise RuntimeError(
                        f"PostgreSQL table {table!r} is missing required index(es): "
                        + ", ".join(sorted(missing_indexes))
                        + ". Run `alembic upgrade head` from the backend directory."
                    )
    except SQLAlchemyError as error:
        raise RuntimeError(
            "Could not connect to or inspect PostgreSQL to verify the schema. "
            "Check the database connection settings, server availability, "
            "and schema permissions."
        ) from error


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def save_verification(db: Session, user_id: int, raw_text: str, diagnosis_hint: str, result: dict):
    violations = result.get("violations", [])
    severities = [v["severity"] for v in violations]
    highest = None
    for level in ("high", "medium", "low"):
        if level in severities:
            highest = level
            break

    entry = VerificationHistory(
        user_id=user_id,
        raw_text=raw_text,
        diagnosis_hint=diagnosis_hint,
        result_json=json.dumps(result),
        violation_count=len(violations),
        highest_severity=highest,
    )
    try:
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    except SQLAlchemyError:
        db.rollback()
        raise
