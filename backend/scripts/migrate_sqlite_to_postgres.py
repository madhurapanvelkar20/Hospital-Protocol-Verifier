"""Copy application rows from SQLite to an empty, migrated PostgreSQL DB.

The default invocation is a read-only dry run. Copying requires --apply.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import MetaData, Table, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import engine, init_db

TABLE_NAMES = ("users", "verification_history")


def _read_sqlite_rows(database_path: Path):
    uri = database_path.resolve().as_uri() + "?mode=ro"
    source = sqlite3.connect(uri, uri=True, detect_types=sqlite3.PARSE_DECLTYPES)
    source.row_factory = sqlite3.Row
    source.execute("BEGIN")
    names = {
        row["name"]
        for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    missing = set(TABLE_NAMES) - names
    if missing:
        source.close()
        raise RuntimeError(
            "SQLite source is missing expected tables: " + ", ".join(sorted(missing))
        )
    rows = {
        table_name: [
            dict(row)
            for row in source.execute(
                f"SELECT * FROM {table_name} ORDER BY id"
            )
        ]
        for table_name in TABLE_NAMES
    }
    return source, rows


def migrate(database_path: Path, apply: bool) -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Target must be PostgreSQL; SQLite remains the source.")

    init_db()
    source, source_rows = _read_sqlite_rows(database_path)
    metadata = MetaData()
    target_tables = {
        name: Table(name, metadata, autoload_with=engine)
        for name in TABLE_NAMES
    }
    try:
        with engine.connect() as connection:
            target_counts = {
                name: connection.execute(
                    text(f"SELECT count(*) FROM {name}")
                ).scalar_one()
                for name in TABLE_NAMES
            }
        if any(target_counts.values()):
            raise RuntimeError(
                "Refusing to copy into a non-empty PostgreSQL target. "
                "Use a new, empty database; existing target rows are never overwritten."
            )

        source_counts = {name: len(source_rows[name]) for name in TABLE_NAMES}
        print(f"SQLite source rows: {source_counts}")
        print(f"PostgreSQL target rows before copy: {target_counts}")
        if not apply:
            print("Dry run only. Re-run with --apply to copy into the empty target.")
            return

        with engine.begin() as connection:
            connection.execute(
                text(
                    "LOCK TABLE users, verification_history "
                    "IN ACCESS EXCLUSIVE MODE"
                )
            )
            locked_counts = {
                name: connection.execute(
                    text(f"SELECT count(*) FROM {name}")
                ).scalar_one()
                for name in TABLE_NAMES
            }
            if any(locked_counts.values()):
                raise RuntimeError(
                    "Target became non-empty before copy. No rows were written."
                )

            for name in TABLE_NAMES:
                if source_rows[name]:
                    connection.execute(
                        target_tables[name].insert(),
                        source_rows[name],
                    )

            for name in TABLE_NAMES:
                connection.execute(
                    text(
                        f"SELECT setval("
                        f"pg_get_serial_sequence(:table_name, 'id'), "
                        f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) "
                        f"FROM {name}"
                    ),
                    {"table_name": name},
                )

            copied_counts = {
                name: connection.execute(
                    text(f"SELECT count(*) FROM {name}")
                ).scalar_one()
                for name in TABLE_NAMES
            }
            if copied_counts != source_counts:
                raise RuntimeError(
                    f"Row-count verification failed: source={source_counts}, "
                    f"target={copied_counts}"
                )
            for name in TABLE_NAMES:
                copied_rows = [
                    dict(row)
                    for row in connection.execute(
                        target_tables[name].select().order_by(
                            target_tables[name].c.id
                        )
                    ).mappings()
                ]
                if copied_rows != source_rows[name]:
                    raise RuntimeError(
                        f"Content verification failed for table {name}; "
                        "the target transaction will be rolled back."
                    )
        print(f"Copy completed and row counts verified: {source_counts}")
        print("The SQLite source was opened read-only and has not been modified.")
    finally:
        source.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite-path",
        required=True,
        type=Path,
        help="Path to the existing SQLite database; it is opened read-only.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the copy. Without this flag the command only reports counts.",
    )
    args = parser.parse_args()
    if not args.sqlite_path.is_file():
        parser.error(f"SQLite database does not exist: {args.sqlite_path}")
    migrate(args.sqlite_path, apply=args.apply)


if __name__ == "__main__":
    main()
