from backend.db import get_db
import duckdb


async def get_database() -> duckdb.DuckDBPyConnection:
    """FastAPI dependency for DuckDB connection."""
    return get_db()
