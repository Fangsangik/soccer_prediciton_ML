from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import duckdb

from backend.deps import get_database
from backend.services.betting_service import calculate_ev, scan_value_bets

router = APIRouter(prefix="/betting", tags=["betting"])


class BettingLine(BaseModel):
    market: str
    selection: str
    odds: float
    bookmaker: str = ""


class EVRequest(BaseModel):
    match_id: int
    lines: list[BettingLine]


@router.post("/ev")
async def calculate_expected_value(
    request: EVRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        from backend.services.prediction_service import get_prediction

        pred = get_prediction(request.match_id, conn)
        probs = pred.get("probabilities", {})

        selection_prob_map = {
            "home_win": probs.get("home_win", 0.33),
            "draw": probs.get("draw", 0.33),
            "away_win": probs.get("away_win", 0.33),
            "over_2.5": 0.55,
            "under_2.5": 0.45,
            "btts_yes": 0.50,
            "btts_no": 0.50,
        }

        results = []
        for line in request.lines:
            model_prob = selection_prob_map.get(line.selection, 0.33)
            ev_result = calculate_ev(model_prob, line.odds)
            ev_result["market"] = line.market
            ev_result["selection"] = line.selection
            ev_result["odds"] = line.odds
            ev_result["bookmaker"] = line.bookmaker
            results.append(ev_result)

        return {"match_id": request.match_id, "results": results}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/value-bets")
async def get_value_bets(
    league: str | None = Query(None, description="League code filter e.g. PL"),
    min_ev: float = Query(0.03, ge=0, description="Minimum EV threshold"),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        bets = scan_value_bets(league, min_ev, conn)
        return {"value_bets": bets, "count": len(bets)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
