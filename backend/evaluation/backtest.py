"""Backtesting framework: run predictions on finished matches and evaluate."""
from __future__ import annotations

from typing import Any

import duckdb

from backend.models.match_predictor import predict
from backend.evaluation.calibration import brier_score, accuracy, log_loss


def _outcome_from_scores(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home_win"
    elif home_score == away_score:
        return "draw"
    else:
        return "away_win"


def backtest_season(
    season: str,
    conn: duckdb.DuckDBPyConnection,
    max_matches: int = 200,
) -> dict[str, Any]:
    """Run predictions on all finished matches in a season and compute metrics.

    Args:
        season: Season string e.g. "2024-25".
        conn: Active DuckDB connection.
        max_matches: Cap on number of matches to backtest (for speed).

    Returns:
        Dict with roi, hit_rate, brier, log_loss, profit_curve, n_matches.
    """
    rows = conn.execute(
        """
        SELECT match_id, home_score, away_score
        FROM matches
        WHERE status = 'FINISHED' AND season = ?
        ORDER BY kickoff ASC
        LIMIT ?
        """,
        [season, max_matches],
    ).fetchall()

    if not rows:
        return {
            "season": season,
            "n_matches": 0,
            "hit_rate": 0.0,
            "brier": None,
            "log_loss": None,
            "roi": 0.0,
            "profit_curve": [],
        }

    predictions = []
    actuals = []
    profit_curve: list[float] = []
    cumulative_profit = 0.0
    n_bets = 0

    for match_id, home_score, away_score in rows:
        actual = _outcome_from_scores(home_score or 0, away_score or 0)
        pred = predict(match_id, conn)

        if "error" in pred:
            continue

        predictions.append(pred)
        actuals.append(actual)

        # Simple flat-stake betting simulation: bet on highest-probability outcome
        probs = pred["probabilities"]
        top_outcome = max(probs, key=lambda k: probs[k])
        model_prob = probs[top_outcome]

        # Simulate market odds with 5% margin
        market_odds = round(1 / (model_prob * 1.05), 2)
        market_odds = max(1.01, market_odds)

        stake = 1.0
        if top_outcome == actual:
            profit = stake * (market_odds - 1)
        else:
            profit = -stake

        cumulative_profit += profit
        n_bets += 1
        profit_curve.append(round(cumulative_profit, 4))

    if not predictions:
        return {
            "season": season,
            "n_matches": len(rows),
            "hit_rate": 0.0,
            "brier": None,
            "log_loss": None,
            "roi": 0.0,
            "profit_curve": [],
        }

    hit_rate = accuracy(predictions, actuals)
    bs = brier_score(predictions, actuals)
    ll = log_loss(predictions, actuals)
    roi = round(cumulative_profit / n_bets * 100, 2) if n_bets else 0.0

    return {
        "season": season,
        "n_matches": len(predictions),
        "hit_rate": round(hit_rate * 100, 2),
        "brier": bs,
        "log_loss": ll,
        "roi": roi,
        "profit_curve": profit_curve,
        "cumulative_profit": round(cumulative_profit, 4),
        "n_bets": n_bets,
    }
