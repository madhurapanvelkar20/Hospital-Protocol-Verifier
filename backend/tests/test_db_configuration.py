"""Unit tests for environment-driven SQLAlchemy database selection."""

import pytest


def _database_url(environ):
    from src.db import _database_url as build_database_url

    return build_database_url(environ)


def test_sqlite_remains_the_default():
    assert _database_url({}) == "sqlite:///hpv.db"
    assert _database_url({"DATABASE_PATH": "local-copy.db"}) == "sqlite:///local-copy.db"


def test_postgres_environment_settings_build_psycopg_url_safely():
    from sqlalchemy.engine import URL

    url = _database_url(
        {
            "DB_DIALECT": "postgresql",
            "DB_HOST": "localhost",
            "DB_NAME": "hpv_test",
            "DB_USER": "hpv_test_user",
            "DB_PASSWORD": "p@ss:/word",
        }
    )

    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg"
    assert url.host == "localhost"
    assert url.port == 5432
    assert url.database == "hpv_test"
    assert url.username == "hpv_test_user"
    assert url.password == "p@ss:/word"


@pytest.mark.parametrize(
    "configured_url",
    [
        "postgres://user:encoded%40password@localhost:5432/hpv_test",
        "postgresql://user:encoded%40password@localhost:5432/hpv_test",
    ],
)
def test_postgres_url_aliases_use_psycopg(configured_url):
    from sqlalchemy.engine import make_url

    url = make_url(_database_url({"DATABASE_URL": configured_url}))

    assert url.drivername == "postgresql+psycopg"
    assert url.password == "encoded@password"


def test_database_url_takes_precedence_over_split_settings():
    url = _database_url(
        {
            "DATABASE_URL": "postgresql+psycopg://user@localhost/hpv_test",
            "DB_DIALECT": "unsupported",
        }
    )

    assert url == "postgresql+psycopg://user@localhost/hpv_test"


def test_incomplete_postgres_environment_names_missing_settings():
    with pytest.raises(RuntimeError, match="DB_HOST, DB_NAME, DB_USER, DB_PASSWORD"):
        _database_url({"DB_DIALECT": "postgresql"})


def test_invalid_postgres_port_has_actionable_error():
    with pytest.raises(RuntimeError, match="DB_PORT must be a valid integer"):
        _database_url(
            {
                "DB_DIALECT": "postgresql",
                "DB_HOST": "localhost",
                "DB_NAME": "hpv_test",
                "DB_USER": "hpv_test_user",
                "DB_PASSWORD": "test-only",
                "DB_PORT": "not-a-port",
            }
        )


def test_creation_timestamps_are_naive_utc_to_match_existing_schema():
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from src.db import Base, User, VerificationHistory, _utcnow_naive

    assert _utcnow_naive().tzinfo is None
    test_engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(bind=test_engine)
        with Session(test_engine) as session:
            user = User(
                email="postgres-compatibility@example.invalid",
                display_name="Database compatibility test",
                hashed_password="test-only",
            )
            session.add(user)
            session.flush()
            history = VerificationHistory(
                user_id=user.id,
                raw_text="synthetic test input",
                result_json="{}",
            )
            session.add(history)
            session.commit()

            user_created_at = session.execute(
                select(User.created_at).where(User.id == user.id)
            ).scalar_one()
            history_created_at = session.execute(
                select(VerificationHistory.created_at).where(
                    VerificationHistory.id == history.id
                )
            ).scalar_one()

        assert user_created_at.tzinfo is None
        assert history_created_at.tzinfo is None
    finally:
        test_engine.dispose()
