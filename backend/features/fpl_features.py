"""FPL-specific feature extraction and projection functions."""
from __future__ import annotations

from typing import Any

import duckdb


def get_fixture_difficulty(
    conn: duckdb.DuckDBPyConnection,
    team_code: int,
    n_ahead: int = 5,
) -> list[dict[str, Any]]:
    """Return upcoming fixture difficulty ratings (FDR) for a team.

    Only unfinished fixtures are returned, ordered by gameweek ascending.

    Args:
        conn: Active DuckDB connection.
        team_code: FPL team code (matches ``fpl_fixtures.home_team_code`` /
                   ``away_team_code``).
        n_ahead: Maximum number of upcoming gameweeks to return.

    Returns:
        List of dicts, each with keys:
        ``fixture_id``, ``gameweek``, ``kickoff``,
        ``opponent_code``, ``is_home``, ``difficulty``.
    """
    rows = conn.execute(
        """
        SELECT
            fixture_id, gameweek, kickoff,
            home_team_code, away_team_code,
            home_difficulty, away_difficulty
        FROM fpl_fixtures
        WHERE finished = false
          AND (home_team_code = ? OR away_team_code = ?)
        ORDER BY gameweek ASC
        LIMIT ?
        """,
        [team_code, team_code, n_ahead],
    ).fetchall()

    result: list[dict[str, Any]] = []
    for fixture_id, gw, kickoff, htc, atc, h_diff, a_diff in rows:
        is_home = htc == team_code
        opponent_code = atc if is_home else htc
        difficulty = h_diff if is_home else a_diff
        result.append(
            {
                "fixture_id": fixture_id,
                "gameweek": gw,
                "kickoff": kickoff,
                "opponent_code": opponent_code,
                "is_home": is_home,
                "difficulty": difficulty,
            }
        )
    return result


def project_points(
    conn: duckdb.DuckDBPyConnection,
    fpl_id: int,
    horizon: int = 5,
) -> dict[str, Any]:
    """Project expected FPL points over the next *horizon* gameweeks.

    Uses a form-weighted average of recent gameweek history.  Points are
    scaled down by fixture difficulty (FDR 1 = +10 %, FDR 5 = -20 %).

    Args:
        conn: Active DuckDB connection.
        fpl_id: FPL player ID.
        horizon: Number of upcoming gameweeks to project.

    Returns:
        Dict with keys:
        ``fpl_id``, ``horizon``, ``projected_total``,
        ``projected_per_gw`` (list of per-GW floats),
        ``base_form_pts`` (form-weighted baseline per GW).
    """
    # Fetch recent GW history (last 5 GWs) for form baseline
    history = conn.execute(
        """
        SELECT gameweek, points, minutes
        FROM fpl_gameweek_history
        WHERE fpl_id = ?
        ORDER BY gameweek DESC
        LIMIT 5
        """,
        [fpl_id],
    ).fetchall()

    if not history:
        return {
            "fpl_id": fpl_id,
            "horizon": horizon,
            "projected_total": 0.0,
            "projected_per_gw": [],
            "base_form_pts": 0.0,
        }

    # Exponentially weighted form (most recent = highest weight)
    weights = [2 ** i for i in range(len(history))]
    total_weight = sum(weights)
    base_pts = sum(
        row[1] * w for row, w in zip(history, weights)
    ) / total_weight

    # Fetch player's team code
    team_row = conn.execute(
        "SELECT team_code FROM fpl_players WHERE fpl_id = ?", [fpl_id]
    ).fetchone()
    team_code = team_row[0] if team_row else None

    # Fetch upcoming fixtures
    fixtures = (
        get_fixture_difficulty(conn, team_code, n_ahead=horizon)
        if team_code is not None
        else []
    )

    # FDR multipliers: 1 → 1.10, 2 → 1.05, 3 → 1.00, 4 → 0.90, 5 → 0.80
    fdr_mult = {1: 1.10, 2: 1.05, 3: 1.00, 4: 0.90, 5: 0.80}

    per_gw: list[float] = []
    for i in range(horizon):
        if i < len(fixtures):
            fdr = fixtures[i]["difficulty"]
            mult = fdr_mult.get(fdr, 1.0)
        else:
            mult = 1.0  # no fixture data → neutral
        per_gw.append(round(base_pts * mult, 2))

    return {
        "fpl_id": fpl_id,
        "horizon": horizon,
        "projected_total": round(sum(per_gw), 2),
        "projected_per_gw": per_gw,
        "base_form_pts": round(base_pts, 2),
    }


def get_value_score(
    conn: duckdb.DuckDBPyConnection,
    fpl_id: int,
    horizon: int = 5,
) -> dict[str, Any]:
    """Compute a value score = projected_points / price for *fpl_id*.

    Higher values indicate better value-for-money picks.

    Args:
        conn: Active DuckDB connection.
        fpl_id: FPL player ID.
        horizon: Projection horizon passed to :func:`project_points`.

    Returns:
        Dict with keys:
        ``fpl_id``, ``price``, ``projected_total``, ``value_score``.
        ``value_score`` is ``None`` if price is zero or unknown.
    """
    price_row = conn.execute(
        "SELECT price FROM fpl_players WHERE fpl_id = ?", [fpl_id]
    ).fetchone()

    price = price_row[0] if price_row else None

    projection = project_points(conn, fpl_id, horizon=horizon)
    proj_total = projection["projected_total"]

    if price and price > 0:
        value_score = round(proj_total / price, 4)
    else:
        value_score = None

    return {
        "fpl_id": fpl_id,
        "price": price,
        "projected_total": proj_total,
        "value_score": value_score,
    }
