from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import duckdb

from backend.config import settings

_connection: Optional[duckdb.DuckDBPyConnection] = None

SCHEMA_PATH = Path(__file__).parent / "storage" / "schema.sql"


def get_db() -> duckdb.DuckDBPyConnection:
    """Return the singleton DuckDB connection, initialising it on first call."""
    global _connection
    if _connection is None:
        db_path = settings.DB_PATH
        # Ensure the parent directory exists for file-based DBs.
        if db_path != ":memory:":
            os.makedirs(Path(db_path).parent, exist_ok=True)
        _connection = duckdb.connect(db_path)
        _run_schema(_connection)
    return _connection


def init_db() -> duckdb.DuckDBPyConnection:
    """Explicitly initialise (or re-initialise) the database and return the connection."""
    global _connection
    if _connection is not None:
        try:
            _connection.close()
        except Exception:
            pass
        _connection = None
    return get_db()


def close_db() -> None:
    """Close the singleton connection if it is open."""
    global _connection
    if _connection is not None:
        try:
            _connection.close()
        except Exception:
            pass
        _connection = None


def _run_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Execute the DDL schema file against the given connection."""
    if SCHEMA_PATH.exists():
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executemany("", [])  # no-op warmup
        conn.execute(sql)
    # Migrations: add columns that may not exist in older DBs
    try:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(128)")
    except Exception:
        pass  # Column already exists
    try:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT false")
    except Exception:
        pass  # Column already exists
    # Ensure "Sangik Hwang" is admin
    try:
        conn.execute("UPDATE users SET is_admin = true WHERE username = 'Sangik Hwang'")
    except Exception:
        pass
