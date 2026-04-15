"""FPL service layer: player queries, lineup optimization, gameweek info."""
from __future__ import annotations

from typing import Any

import pandas as pd
import duckdb

from backend.features.fpl_features import project_points, get_value_score
from backend.models.fpl_optimizer import optimize_squad


def get_players(
    conn: duckdb.DuckDBPyConnection,
    position: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    sort_by: str = "total_points",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return FPL players with optional filters.

    Args:
        conn: Active DuckDB connection.
        position: Position filter (GKP, DEF, MID, FWD).
        min_price: Minimum price filter.
        max_price: Maximum price filter.
        sort_by: Column to sort by (total_points, price, form, points_per_game).
        limit: Maximum rows to return.

    Returns:
        List of player dicts.
    """
    valid_sort = {"total_points", "price", "form", "points_per_game", "ict_index"}
    if sort_by not in valid_sort:
        sort_by = "total_points"

    wheres = []
    params: list[Any] = []

    if position:
        wheres.append("fp.position = ?")
        params.append(position.upper())
    if min_price is not None:
        wheres.append("fp.price >= ?")
        params.append(min_price)
    if max_price is not None:
        wheres.append("fp.price <= ?")
        params.append(max_price)

    where_sql = "WHERE " + " AND ".join(wheres) if wheres else ""

    rows = conn.execute(
        f"""
        SELECT
            fp.fpl_id, fp.web_name, fp.position, fp.team_name,
            fp.price, fp.total_points, fp.form, fp.points_per_game,
            fp.selected_by_pct, fp.minutes, fp.goals_scored, fp.assists,
            fp.clean_sheets, fp.bonus, fp.ict_index,
            fp.injury_status, fp.injury_note
        FROM fpl_players fp
        {where_sql}
        ORDER BY fp.{sort_by} DESC
        LIMIT ?
        """,
        params + [limit],
    ).fetchall()

    cols = [
        "fpl_id", "web_name", "position", "team_name", "price", "total_points",
        "form", "points_per_game", "selected_by_pct", "minutes", "goals_scored",
        "assists", "clean_sheets", "bonus", "ict_index", "injury_status", "injury_note",
    ]
    return [dict(zip(cols, row)) for row in rows]


def optimize_lineup(
    budget: float,
    horizon: int,
    constraints: dict[str, Any],
    conn: duckdb.DuckDBPyConnection,
    position_filter: str | None = None,
    existing_squad: list[int] | None = None,
    free_transfers: int = 1,
    transfer_penalty: int = 4,
) -> dict[str, Any]:
    """Build projected points for all players then run optimizer.

    Args:
        budget: Total budget (e.g. 100.0).
        horizon: Projection horizon in gameweeks.
        constraints: Optimizer constraints dict.
        conn: Active DuckDB connection.
        position_filter: Unused; optimizer always selects full squad.
        existing_squad: Current squad fpl_ids for transfer calc.
        free_transfers: Free transfers available.
        transfer_penalty: Points per extra transfer.

    Returns:
        OptimizeResult dict from fpl_optimizer.
    """
    rows = conn.execute(
        """
        SELECT fpl_id, web_name, position, team_name, price, injury_status
        FROM fpl_players
        """
    ).fetchall()

    records = []
    for fpl_id, web_name, position, team_name, price, injury_status in rows:
        proj = project_points(conn, fpl_id, horizon=horizon)
        records.append(
            {
                "fpl_id": fpl_id,
                "web_name": web_name,
                "position": position,
                "team_name": team_name,
                "price": price or 0.0,
                "projected_points": proj["projected_total"],
                "injury_status": injury_status or "Available",
            }
        )

    players_df = pd.DataFrame(records)

    return optimize_squad(
        players_df=players_df,
        budget=budget,
        horizon=horizon,
        constraints=constraints,
        existing_squad=existing_squad,
        free_transfers=free_transfers,
        transfer_penalty=transfer_penalty,
    )


def get_gameweek_info(gw: int, conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Return summary information for a given gameweek.

    Args:
        gw: Gameweek number.
        conn: Active DuckDB connection.

    Returns:
        Dict with fixtures, top scorers, and aggregate stats.
    """
    fixtures = conn.execute(
        """
        SELECT
            f.fixture_id, f.gameweek, f.kickoff,
            ht.name AS home_team, awt.name AS away_team,
            f.home_difficulty, f.away_difficulty, f.finished
        FROM fpl_fixtures f
        LEFT JOIN teams ht ON ht.team_id = f.home_team_code
        LEFT JOIN teams awt ON awt.team_id = f.away_team_code
        WHERE f.gameweek = ?
        ORDER BY f.kickoff ASC
        """,
        [gw],
    ).fetchall()

    fixture_list = [
        {
            "fixture_id": r[0],
            "gameweek": r[1],
            "kickoff": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
            "home_team": r[3],
            "away_team": r[4],
            "home_difficulty": r[5],
            "away_difficulty": r[6],
            "finished": r[7],
        }
        for r in fixtures
    ]

    # Top scorers this GW from history
    top_scorers = conn.execute(
        """
        SELECT fp.web_name, fp.position, fp.team_name, gh.points, gh.goals, gh.assists
        FROM fpl_gameweek_history gh
        JOIN fpl_players fp ON fp.fpl_id = gh.fpl_id
        WHERE gh.gameweek = ?
        ORDER BY gh.points DESC
        LIMIT 10
        """,
        [gw],
    ).fetchall()

    scorers_list = [
        {
            "web_name": r[0],
            "position": r[1],
            "team_name": r[2],
            "points": r[3],
            "goals": r[4],
            "assists": r[5],
        }
        for r in top_scorers
    ]

    avg_row = conn.execute(
        "SELECT AVG(points), MAX(points) FROM fpl_gameweek_history WHERE gameweek = ?",
        [gw],
    ).fetchone()

    return {
        "gameweek": gw,
        "fixtures": fixture_list,
        "top_scorers": scorers_list,
        "average_points": round(avg_row[0] or 0, 2) if avg_row else 0,
        "highest_score": int(avg_row[1] or 0) if avg_row else 0,
    }
