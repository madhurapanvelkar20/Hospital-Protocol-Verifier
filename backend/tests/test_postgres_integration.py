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
TEST_DATABASE_CONFIRMATION = os.environ.get(
    "HPV_TEST_DATABASE_CONFIRMATION"
)
if not TEST_DATABASE_URL and not TEST_DATABASE_CONFIRMATION:
    pytest.skip(
        "PostgreSQL integration is not enabled; set TEST_DATABASE_URL and "
        "HPV_TEST_DATABASE_CONFIRMATION to run it.",
        allow_module_level=True,
    )

if not TEST_DATABASE_URL:
    pytest.fail(
        "PostgreSQL integration was enabled without TEST_DATABASE_URL.",
        pytrace=False,
    )

if TEST_DATABASE_CONFIRMATION != "I_CONFIRM_THIS_IS_A_DISPOSABLE_TEST_DATABASE":
    pytest.fail(
        "PostgreSQL integration requires "
        "HPV_TEST_DATABASE_CONFIRMATION=I_CONFIRM_THIS_IS_A_DISPOSABLE_TEST_DATABASE.",
        pytrace=False,
    )

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

try:
    test_url = make_url(TEST_DATABASE_URL)
except (ArgumentError, TypeError) as error:
    pytest.fail(
        f"PostgreSQL integration TEST_DATABASE_URL is invalid: {error}",
        pytrace=False,
    )

if test_url.get_backend_name() != "postgresql":
    pytest.fail(
        "PostgreSQL integration TEST_DATABASE_URL must use PostgreSQL.",
        pytrace=False,
    )
if not test_url.database or not re.search(
    r"(?:^|[_-])test(?:$|[_-])", test_url.database.lower()
):
    pytest.fail(
        "Use a dedicated PostgreSQL test database with 'test' as a delimited "
        "word in its name, such as hpv_test.",
        pytrace=False,
    )
if find_spec("psycopg") is None:
    pytest.fail(
        'PostgreSQL integration requires Psycopg 3; install it with '
        '`python -m pip install "psycopg[binary]>=3.1.18"`.',
        pytrace=False,
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
    pytest.fail(
        "PostgreSQL integration TEST_DATABASE_URL did not configure a PostgreSQL engine.",
        pytrace=False,
    )

from fastapi.testclient import TestClient

import main


def test_postgres_crud_and_authenticated_history_api(monkeypatch):
    init_db()
    email = f"pg-test-{uuid.uuid4().hex}@example.com"
    api_email = f"pg-api-test-{uuid.uuid4().hex}@example.com"
    other_api_email = f"pg-api-test-{uuid.uuid4().hex}@example.com"
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

        with SessionLocal() as db:
            loaded = db.execute(
                select(VerificationHistory).where(
                    VerificationHistory.id == history_id,
                    VerificationHistory.user_id == user_id,
                )
            ).scalar_one()
            assert loaded.result_json
            assert loaded.user.email == email
            assert loaded.created_at is not None
            assert loaded.created_at.tzinfo is None

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

            other_signup = client.post(
                "/api/auth/signup",
                json={
                    "email": other_api_email,
                    "password": "test-password-123",
                    "display_name": "Other PostgreSQL Integration Test",
                },
            )
            assert other_signup.status_code == 200

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

            other_login = client.post(
                "/api/auth/login",
                json={
                    "email": other_api_email,
                    "password": "test-password-123",
                },
            )
            assert other_login.status_code == 200
            other_headers = {
                "Authorization": f"Bearer {other_login.json()['access_token']}"
            }
            other_history = client.get(
                "/api/history",
                headers=other_headers,
            )
            assert other_history.status_code == 200
            assert all(
                entry["raw_text"] != "integration test"
                for entry in other_history.json()
            )
    finally:
        with SessionLocal() as db:
            users = db.execute(
                select(User).where(
                    User.email.in_([email, api_email, other_api_email])
                )
            ).scalars().all()
            for user in users:
                db.delete(user)
            db.commit()
