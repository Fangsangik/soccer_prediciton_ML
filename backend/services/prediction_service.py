"""Orchestrates feature loading, model execution, and response formatting."""
from __future__ import annotations

from typing import Any

import duckdb

from backend.models.match_predictor import predict, MODEL_VERSION


def get_prediction(match_id: int, conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Load features, run prediction model, and return formatted response.

    Args:
        match_id: Target match.
        conn: Active DuckDB connection.

    Returns:
        Full prediction response dict.
    """
    result = predict(match_id, conn)

    if "error" in result:
        return result

    # Persist to match_predictions table (upsert)
    try:
        import json
        conn.execute(
            """
            INSERT INTO match_predictions
                (match_id, model_version, prob_home_win, prob_draw, prob_away_win,
                 pred_home_goals, pred_away_goals, confidence, key_factors, score_dist)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (match_id, model_version) DO UPDATE SET
                prob_home_win = excluded.prob_home_win,
                prob_draw = excluded.prob_draw,
                prob_away_win = excluded.prob_away_win,
                pred_home_goals = excluded.pred_home_goals,
                pred_away_goals = excluded.pred_away_goals,
                confidence = excluded.confidence,
                key_factors = excluded.key_factors,
                score_dist = excluded.score_dist,
                predicted_at = current_timestamp
            """,
            [
                match_id,
                MODEL_VERSION,
                result["probabilities"]["home_win"],
                result["probabilities"]["draw"],
                result["probabilities"]["away_win"],
                result["predicted_score"]["home"],
                result["predicted_score"]["away"],
                result["confidence"],
                json.dumps(result.get("key_factors", [])),
                json.dumps(result.get("score_distribution", {})),
            ],
        )
    except Exception:
        pass  # persist failure should not block response

    return result


def get_batch_predictions(
    match_ids: list[int], conn: duckdb.DuckDBPyConnection
) -> list[dict[str, Any]]:
    """Run predictions for multiple matches.

    Args:
        match_ids: List of match IDs.
        conn: Active DuckDB connection.

    Returns:
        List of prediction dicts (one per match_id).
    """
    return [get_prediction(mid, conn) for mid in match_ids]
