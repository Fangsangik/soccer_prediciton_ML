from backend.db import get_db
import duckdb

from fastapi import Depends, HTTPException, Header
from backend.auth import verify_token


async def get_database() -> duckdb.DuckDBPyConnection:
    """FastAPI dependency for DuckDB connection."""
    return get_db()


async def get_current_user(authorization: str = Header(None)) -> dict:
    """Require a valid Bearer token. Returns decoded user payload."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {
        "user_id": int(payload["sub"]),
        "username": payload["username"],
        "is_admin": payload.get("is_admin", False),
    }


async def get_optional_user(authorization: str = Header(None)) -> dict | None:
    """Returns user info dict or None if not authenticated."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    payload = verify_token(token)
    if not payload:
        return None
    return {
        "user_id": int(payload["sub"]),
        "username": payload["username"],
        "is_admin": payload.get("is_admin", False),
    }
