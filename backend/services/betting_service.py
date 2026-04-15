"""Expected value calculation and value bet scanning."""
from __future__ import annotations

from typing import Any

import duckdb

from backend.services.prediction_service import get_prediction


def calculate_ev(model_prob: float, odds: float) -> dict[str, Any]:
    """Calculate expected value for a given outcome.

    Args:
        model_prob: Model probability for the outcome (0-1).
        odds: Decimal odds offered by bookmaker.

    Returns:
        Dict with ev, edge, kelly fraction, and verdict.
    """
    implied_prob = 1 / odds if odds > 0 else 1.0
    ev = (model_prob * odds) - 1
    edge = model_prob - implied_prob
    kelly = max(0.0, (model_prob * odds - 1) / (odds - 1)) if odds > 1 else 0.0

    if ev > 0.10:
        verdict = "strong_value"
    elif ev > 0.05:
        verdict = "value"
    elif ev > 0:
        verdict = "marginal"
    else:
        verdict = "no_value"

    return {
        "model_prob": round(model_prob, 4),
        "implied_prob": round(implied_prob, 4),
        "ev": round(ev, 4),
        "ev_pct": round(ev * 100, 1),
        "edge": round(edge, 4),
        "kelly_fraction": round(kelly, 4),
        "verdict": verdict,
    }


def scan_value_bets(
    league: str | None,
    min_ev: float,
    conn: duckdb.DuckDBPyConnection,
) -> list[dict[str, Any]]:
    """Scan upcoming matches for value bets using model predictions.

    Uses a simple bookmaker margin model to derive implied odds from
    the model probabilities, then applies a synthetic 5% margin to
    simulate market odds.

    Args:
        league: League code filter (e.g. "PL"), or None for all leagues.
        min_ev: Minimum EV threshold to include a bet.
        conn: Active DuckDB connection.

    Returns:
        List of value bet dicts, sorted by EV descending.
    """
    where = "WHERE m.status = 'SCHEDULED'"
    params: list[Any] = []
    if league:
        where += " AND l.code = ?"
        params.append(league)

    rows = conn.execute(
        f"""
        SELECT m.match_id, m.kickoff,
               ht.name AS home_team, awt.name AS away_team,
               l.code AS league_code
        FROM matches m
        LEFT JOIN leagues l ON l.league_id = m.league_id
        LEFT JOIN teams ht ON ht.team_id = m.home_team_id
        LEFT JOIN teams awt ON awt.team_id = m.away_team_id
        {where}
        ORDER BY m.kickoff ASC
        LIMIT 50
        """,
        params,
    ).fetchall()

    value_bets: list[dict[str, Any]] = []

    for match_id, kickoff, home_team, away_team, league_code in rows:
        pred = get_prediction(match_id, conn)
        if "error" in pred:
            continue

        probs = pred["probabilities"]

        # Simulate market odds with a 5% bookmaker margin
        margin = 0.05
        outcomes = [
            ("home_win", probs["home_win"]),
            ("draw", probs["draw"]),
            ("away_win", probs["away_win"]),
        ]

        for outcome_name, model_prob in outcomes:
            # Market implied prob = model_prob * (1 + margin)
            market_implied = min(0.99, model_prob * (1 + margin))
            market_odds = round(1 / market_implied, 2) if market_implied > 0 else 100.0

            ev_data = calculate_ev(model_prob, market_odds)
            if ev_data["ev"] >= min_ev:
                value_bets.append(
                    {
                        "match_id": match_id,
                        "kickoff": kickoff.isoformat()
                        if hasattr(kickoff, "isoformat")
                        else str(kickoff),
                        "home_team": home_team,
                        "away_team": away_team,
                        "league_code": league_code,
                        "outcome": outcome_name,
                        "market_odds": market_odds,
                        **ev_data,
                    }
                )

    value_bets.sort(key=lambda x: x["ev"], reverse=True)
    return value_bets
