"""Simple migration runner that applies schema.sql to a DuckDB connection."""
from __future__ import annotations

from pathlib import Path

import duckdb

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def run_migrations(conn: duckdb.DuckDBPyConnection) -> None:
    """Execute the full DDL schema file against *conn*.

    The schema uses ``CREATE TABLE IF NOT EXISTS`` throughout, so running
    migrations multiple times is safe and idempotent.
    """
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")

    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.execute(sql)
    print(f"[migrations] Schema applied from {SCHEMA_PATH}")


def run_migrations_from_path(db_path: str) -> duckdb.DuckDBPyConnection:
    """Open *db_path*, run migrations, and return the connection.

    Useful for standalone CLI usage:
        python -m backend.storage.migrations data/football.duckdb
    """
    import os

    os.makedirs(Path(db_path).parent, exist_ok=True)
    conn = duckdb.connect(db_path)
    run_migrations(conn)
    return conn


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/football.duckdb"
    run_migrations_from_path(path)
    print(f"[migrations] Done — {path}")
