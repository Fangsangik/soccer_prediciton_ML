"""Title Race & Champions League winner prediction endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import duckdb

from backend.deps import get_database

router = APIRouter(prefix="/title-race", tags=["title-race"])


@router.get("/league")
async def league_title_race(
    league: str = Query("PL"),
    season: str = Query("2025-26"),
    simulations: int = Query(5000, ge=100, le=20000),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Monte Carlo simulation for league title/relegation probabilities."""
    try:
        from backend.models.season_simulator import simulate_league
        result = simulate_league(conn, league, season, n_simulations=simulations)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Simulation failed: {str(exc)}"
        ) from exc


@router.get("/champions-league")
async def champions_league_prediction(
    season: str = Query("2025-26"),
    simulations: int = Query(5000, ge=100, le=20000),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Monte Carlo simulation for Champions League winner."""
    try:
        from backend.models.season_simulator import simulate_champions_league
        result = simulate_champions_league(conn, season, n_simulations=simulations)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"CL simulation failed: {str(exc)}"
        ) from exc
