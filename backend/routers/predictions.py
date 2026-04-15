from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import duckdb

from backend.deps import get_database
from backend.services.prediction_service import get_prediction, get_batch_predictions

router = APIRouter(prefix="/predictions", tags=["predictions"])


class BatchPredictionRequest(BaseModel):
    match_ids: list[int]


@router.get("/{match_id}")
async def prediction_for_match(
    match_id: int,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        result = get_prediction(match_id, conn)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/batch")
async def batch_predictions(
    request: BatchPredictionRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        results = get_batch_predictions(request.match_ids, conn)
        return {"predictions": results, "count": len(results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
