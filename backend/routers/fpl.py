from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import duckdb

from backend.deps import get_database
from backend.services.fpl_service import get_players, optimize_lineup, get_gameweek_info

router = APIRouter(prefix="/fpl", tags=["fpl"])


class OptimizeRequest(BaseModel):
    budget: float = 100.0
    horizon: int = 5
    constraints: dict[str, Any] = {}
    existing_squad: list[int] | None = None
    free_transfers: int = 1
    transfer_penalty: int = 4


@router.get("/players")
async def list_fpl_players(
    position: str | None = Query(None, description="GKP | DEF | MID | FWD"),
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    sort_by: str = Query("total_points"),
    limit: int = Query(100, ge=1, le=500),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        players = get_players(conn, position, min_price, max_price, sort_by, limit)
        return {"players": players, "count": len(players)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/optimize")
async def optimize_squad(
    request: OptimizeRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        result = optimize_lineup(
            budget=request.budget,
            horizon=request.horizon,
            constraints=request.constraints,
            conn=conn,
            existing_squad=request.existing_squad,
            free_transfers=request.free_transfers,
            transfer_penalty=request.transfer_penalty,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/gameweek/{gw}")
async def gameweek_info(
    gw: int,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        if gw < 1 or gw > 38:
            raise HTTPException(status_code=400, detail="Gameweek must be between 1 and 38")
        return get_gameweek_info(gw, conn)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
