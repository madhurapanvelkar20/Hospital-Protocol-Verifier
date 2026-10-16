"""Opt-in tests for a separately provisioned, migrated PostgreSQL test DB.

Set TEST_DATABASE_URL and HPV_TEST_DATABASE_CONFIRMATION for a dedicated
disposable PostgreSQL database before pytest. Tests create uniquely named
rows and delete them; they never create/drop tables or alter the schema.
"""
import os
import re
import uuid
from importlib.util import find_spec

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.skip(
        "Set TEST_DATABASE_URL to run PostgreSQL integration tests.",
        allow_module_level=True,
    )

if os.environ.get("HPV_TEST_DATABASE_CONFIRMATION") != (
    "I_CONFIRM_THIS_IS_A_DISPOSABLE_TEST_DATABASE"
):
    pytest.skip(
        "Set HPV_TEST_DATABASE_CONFIRMATION only for a disposable PostgreSQL test database.",
        allow_module_level=True,
    )

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

try:
    test_url = make_url(TEST_DATABASE_URL)
except ArgumentError:
    pytest.skip("TEST_DATABASE_URL is invalid.", allow_module_level=True)

if test_url.get_backend_name() != "postgresql":
    pytest.skip("TEST_DATABASE_URL must use PostgreSQL.", allow_module_level=True)
if not test_url.database or not re.search(
    r"(?:^|[_-])test(?:$|[_-])", test_url.database.lower()
):
    pytest.skip(
        "Use a dedicated PostgreSQL database with 'test' in a delimited name, such as hpv_test.",
        allow_module_level=True,
    )
if find_spec("psycopg") is None:
    pytest.skip(
        'Install the optional PostgreSQL driver with `python -m pip install "psycopg[binary]>=3.1.18"`.',
        allow_module_level=True,
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from sqlalchemy import select

from src.db import (
    SessionLocal,
    User,
    VerificationHistory,
    engine,
    init_db,
    save_verification,
)

if engine.dialect.name != "postgresql":
    pytest.skip("TEST_DATABASE_URL must use PostgreSQL.", allow_module_level=True)

from fastapi.testclient import TestClient

import main


def test_postgres_crud_and_authenticated_history_api(monkeypatch):
    init_db()
    email = f"pg-test-{uuid.uuid4().hex}@example.com"
    api_email = f"pg-api-test-{uuid.uuid4().hex}@example.com"
    fake_result = {
        "violations": [],
        "retrieved_chunks": [],
        "retrieval_confidence": 0.0,
        "retrieval_attempts": 1,
    }

    try:
        with SessionLocal() as db:
            user = User(
                email=email,
                display_name="PostgreSQL Integration Test",
                hashed_password=main.hash_password("test-password-123"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            user_id = user.id

            history = save_verification(
                db,
                user_id,
                "test prescription",
                None,
                fake_result,
            )
            history_id = history.id
            loaded = db.execute(
                select(VerificationHistory).where(
                    VerificationHistory.id == history_id,
                    VerificationHistory.user_id == user_id,
                )
            ).scalar_one()
            assert loaded.result_json

        monkeypatch.setattr(main, "run_pipeline", lambda *_args: fake_result)
        with TestClient(main.app) as client:
            signup = client.post(
                "/api/auth/signup",
                json={
                    "email": api_email,
                    "password": "test-password-123",
                    "display_name": "PostgreSQL Integration Test",
                },
            )
            assert signup.status_code == 200

            login = client.post(
                "/api/auth/login",
                json={"email": api_email, "password": "test-password-123"},
            )
            assert login.status_code == 200
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            assert client.get("/api/auth/me", headers=headers).status_code == 200

            duplicate_signup = client.post(
                "/api/auth/signup",
                json={
                    "email": api_email,
                    "password": "test-password-123",
                    "display_name": "Duplicate",
                },
            )
            assert duplicate_signup.status_code == 400

            verify = client.post(
                "/api/verify",
                json={
                    "raw_text": "integration test",
                    "diagnosis_hint": None,
                    "ordered_tests": [],
                },
                headers=headers,
            )
            assert verify.status_code == 200

            history_response = client.get("/api/history", headers=headers)
            assert history_response.status_code == 200
            assert any(
                entry["raw_text"] == "integration test"
                for entry in history_response.json()
            )
    finally:
        with SessionLocal() as db:
            users = db.execute(
                select(User).where(User.email.in_([email, api_email]))
            ).scalars().all()
            for user in users:
                db.delete(user)
            db.commit()
