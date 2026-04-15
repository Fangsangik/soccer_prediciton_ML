from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
import duckdb

from backend.deps import get_database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(conn: duckdb.DuckDBPyConnection = Depends(get_database)) -> dict:
    db_connected = False
    data_freshness = "unknown"

    try:
        row = conn.execute("SELECT MAX(updated_at) FROM matches").fetchone()
        db_connected = True
        if row and row[0]:
            last_update = row[0]
            if isinstance(last_update, str):
                last_update = datetime.fromisoformat(last_update)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            delta = now - last_update.replace(tzinfo=None) if hasattr(last_update, "tzinfo") else now - last_update
            hours = int(delta.total_seconds() / 3600)
            data_freshness = f"{hours}h ago" if hours < 48 else f"{delta.days}d ago"
        else:
            data_freshness = "no data"
    except Exception:
        db_connected = False

    return {
        "status": "ok",
        "db_connected": db_connected,
        "data_freshness": data_freshness,
    }
