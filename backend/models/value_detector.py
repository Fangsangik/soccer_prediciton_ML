"""Undervalued player detection using composite performance index."""
from __future__ import annotations

from typing import Any

import duckdb

from backend.features.player_features import get_percentile_ranks


def compute_performance_index(percentiles: dict[str, float], position: str) -> float:
    """Compute a composite performance index from percentile ranks.

    Weights are position-specific to reflect what matters per role.

    Args:
        percentiles: Dict of stat -> percentile (0-100).
        position: Player position (GK, DEF, MID, FWD).

    Returns:
        Composite index as a float (0-100).
    """
    weight_map: dict[str, dict[str, float]] = {
        "GK": {
            "pass_completion_pct": 0.3,
            "aerials_won_per_90": 0.3,
            "progressive_passes_per_90": 0.2,
            "tackles_per_90": 0.1,
            "interceptions_per_90": 0.1,
        },
        "DEF": {
            "tackles_per_90": 0.2,
            "interceptions_per_90": 0.2,
            "aerials_won_per_90": 0.15,
            "pass_completion_pct": 0.15,
            "progressive_passes_per_90": 0.15,
            "xg_per_90": 0.075,
            "xa_per_90": 0.075,
        },
        "MID": {
            "xa_per_90": 0.20,
            "key_passes_per_90": 0.15,
            "progressive_carries_per_90": 0.15,
            "progressive_passes_per_90": 0.15,
            "xg_per_90": 0.10,
            "dribbles_per_90": 0.10,
            "tackles_per_90": 0.075,
            "pass_completion_pct": 0.075,
        },
        "FWD": {
            "xg_per_90": 0.30,
            "shots_per_90": 0.20,
            "dribbles_per_90": 0.15,
            "xa_per_90": 0.10,
            "key_passes_per_90": 0.10,
            "progressive_carries_per_90": 0.15,
        },
    }

    weights = weight_map.get(position, weight_map["MID"])
    score = 0.0
    total_weight = 0.0

    for stat, w in weights.items():
        if stat in percentiles:
            score += percentiles[stat] * w
            total_weight += w

    return round(score / total_weight * 1.0, 2) if total_weight > 0 else 0.0


def get_strengths_weaknesses(
    percentiles: dict[str, float],
) -> tuple[list[str], list[str]]:
    """Identify top strengths and weaknesses from percentile ranks."""
    sorted_stats = sorted(percentiles.items(), key=lambda x: x[1], reverse=True)
    strengths = [s for s, p in sorted_stats if p >= 75][:3]
    weaknesses = [s for s, p in sorted_stats[::-1] if p <= 25][:3]
    return strengths, weaknesses


def get_undervalued_players(
    filters: dict[str, Any],
    conn: duckdb.DuckDBPyConnection,
    season: str = "2024-25",
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """Rank players by value ratio (performance / normalised market value).

    Args:
        filters: Dict with optional position, min_minutes, max_market_value keys.
        conn: Active DuckDB connection.
        season: Season string.
        top_n: Number of undervalued players to return.

    Returns:
        Ranked list of player dicts with value_ratio, performance_index, etc.
    """
    position = filters.get("position")
    min_minutes = filters.get("min_minutes", 900)
    max_market_value = filters.get("max_market_value")

    wheres = ["pss.season = ?", "pss.minutes_played >= ?", "pl.market_value_eur > 0"]
    params: list[Any] = [season, min_minutes]

    if position:
        wheres.append("pl.position = ?")
        params.append(position)
    if max_market_value:
        wheres.append("pl.market_value_eur <= ?")
        params.append(max_market_value)

    rows = conn.execute(
        f"""
        SELECT pl.player_id, pl.name, pl.position, pl.market_value_eur,
               t.name AS team_name
        FROM players pl
        JOIN player_season_stats pss ON pss.player_id = pl.player_id
        LEFT JOIN teams t ON t.team_id = pl.team_id
        WHERE {' AND '.join(wheres)}
        """,
        params,
    ).fetchall()

    if not rows:
        return []

    # Normalise market values to 0-100 range
    market_values = [r[3] for r in rows]
    max_mv = max(market_values) or 1
    min_mv = min(market_values) or 1

    results = []
    for player_id, name, position_code, market_value_eur, team_name in rows:
        percentiles = get_percentile_ranks(conn, player_id, season, position_code)
        if not percentiles:
            continue

        perf_index = compute_performance_index(percentiles, position_code)

        # Normalised market value (0-100, higher = more expensive)
        norm_mv = (
            (market_value_eur - min_mv) / (max_mv - min_mv) * 100
            if max_mv != min_mv
            else 50.0
        )
        norm_mv = max(1.0, norm_mv)  # avoid division by zero

        value_ratio = round(perf_index / norm_mv * 100, 4)

        strengths, weaknesses = get_strengths_weaknesses(percentiles)

        results.append(
            {
                "player_id": player_id,
                "name": name,
                "position": position_code,
                "team_name": team_name,
                "market_value_eur": market_value_eur,
                "performance_index": perf_index,
                "value_ratio": value_ratio,
                "strengths": strengths,
                "weaknesses": weaknesses,
            }
        )

    results.sort(key=lambda x: x["value_ratio"], reverse=True)
    return results[:top_n]
