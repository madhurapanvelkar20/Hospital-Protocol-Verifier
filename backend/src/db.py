"""
Database layer: SQLite via SQLAlchemy -- no external DB server needed,
appropriate for a student project / exhibition demo. The DB file
(hpv.db) is created automatically on first run in the backend/ folder.

Two tables:
  - users: email, hashed password, display name, created_at
  - verification_history: one row per prescription verification a logged-in
    user has run, storing both the input and the full pipeline result
    (as JSON), so the History page can show past runs without re-running
    the pipeline.
"""

import json
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

DB_PATH = os.environ.get("DATABASE_PATH", "hpv.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="history")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
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
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
