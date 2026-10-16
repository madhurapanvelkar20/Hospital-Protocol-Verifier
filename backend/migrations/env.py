import os

from alembic import context

from src.db import Base, DATABASE_URL, engine

config = context.config
target_metadata = Base.metadata


def require_explicit_sqlite_migration_opt_in():
    if engine.dialect.name == "sqlite" and (
        os.environ.get("ALEMBIC_ALLOW_SQLITE", "").lower() != "true"
    ):
        raise RuntimeError(
            "Alembic defaults to PostgreSQL-only. Set ALEMBIC_ALLOW_SQLITE=true "
            "only when deliberately adopting an inspected SQLite database."
        )


def run_migrations_offline():
    require_explicit_sqlite_migration_opt_in()
    url = (
        DATABASE_URL.render_as_string(hide_password=False)
        if hasattr(DATABASE_URL, "render_as_string")
        else DATABASE_URL
    )
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    require_explicit_sqlite_migration_opt_in()
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
