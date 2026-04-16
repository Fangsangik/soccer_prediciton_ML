"""Match-level feature extraction functions for the prediction model."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import duckdb


def get_team_form(
    conn: duckdb.DuckDBPyConnection,
    team_id: int,
    n: int = 5,
    before_date: datetime | None = None,
) -> dict[str, Any]:
    """Return form metrics from the last *n* finished matches for *team_id*.

    Args:
        conn: Active DuckDB connection.
        team_id: The team to analyse.
        n: Number of most-recent finished matches to consider.
        before_date: If set, only include matches kicked off strictly before
            this datetime to avoid data leakage.
    """
    if before_date is not None:
        rows = conn.execute(
            """
            SELECT home_team_id, away_team_id, home_score, away_score, home_xg, away_xg
            FROM matches
            WHERE status = 'FINISHED'
              AND (home_team_id = ? OR away_team_id = ?)
              AND kickoff < ?
            ORDER BY kickoff DESC
            LIMIT ?
            """,
            [team_id, team_id, before_date, n],
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT home_team_id, away_team_id, home_score, away_score, home_xg, away_xg
            FROM matches
            WHERE status = 'FINISHED'
              AND (home_team_id = ? OR away_team_id = ?)
            ORDER BY kickoff DESC
            LIMIT ?
            """,
            [team_id, team_id, n],
        ).fetchall()

    results: list[str] = []
    points = 0
    goals_scored = 0
    goals_conceded = 0
    xg_values: list[float] = []
    xga_values: list[float] = []

    for home_id, away_id, hs, as_, h_xg, a_xg in rows:
        is_home = home_id == team_id
        gf = hs if is_home else as_
        ga = as_ if is_home else hs
        xg = (h_xg or 0.0) if is_home else (a_xg or 0.0)
        xga = (a_xg or 0.0) if is_home else (h_xg or 0.0)

        if gf > ga:
            results.append("W")
            points += 3
        elif gf == ga:
            results.append("D")
            points += 1
        else:
            results.append("L")

        goals_scored += gf or 0
        goals_conceded += ga or 0
        xg_values.append(xg)
        xga_values.append(xga)

    total = len(results)
    return {
        "results": list(reversed(results)),  # chronological order
        "points": points,
        "goals_scored": goals_scored,
        "goals_conceded": goals_conceded,
        "xg_avg": round(sum(xg_values) / total, 3) if total else 0.0,
        "xga_avg": round(sum(xga_values) / total, 3) if total else 0.0,
        "win_rate": round(results.count("W") / total, 3) if total else 0.0,
    }


def get_home_away_splits(
    conn: duckdb.DuckDBPyConnection,
    team_id: int,
    before_date: datetime | None = None,
) -> dict[str, Any]:
    """Return home vs away performance splits for *team_id*.

    Args:
        conn: Active DuckDB connection.
        team_id: The team to analyse.
        before_date: If set, only include matches before this datetime.
    """
    date_filter = " AND kickoff < ?" if before_date is not None else ""
    date_params = [before_date] if before_date is not None else []

    def _split(is_home: bool) -> dict[str, Any]:
        if is_home:
            q = f"""
                SELECT home_score, away_score, home_xg, away_xg
                FROM matches
                WHERE status = 'FINISHED' AND home_team_id = ?{date_filter}
            """
        else:
            q = f"""
                SELECT away_score, home_score, away_xg, home_xg
                FROM matches
                WHERE status = 'FINISHED' AND away_team_id = ?{date_filter}
            """
        rows = conn.execute(q, [team_id] + date_params).fetchall()

        wins = draws = losses = gf_total = ga_total = 0
        xg_sum = xga_sum = 0.0

        for gf, ga, xg, xga in rows:
            gf = gf or 0
            ga = ga or 0
            xg = xg or 0.0
            xga = xga or 0.0
            if gf > ga:
                wins += 1
            elif gf == ga:
                draws += 1
            else:
                losses += 1
            gf_total += gf
            ga_total += ga
            xg_sum += xg
            xga_sum += xga

        total = wins + draws + losses
        return {
            "matches": total,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goals_scored": gf_total,
            "goals_conceded": ga_total,
            "xg_avg": round(xg_sum / total, 3) if total else 0.0,
            "xga_avg": round(xga_sum / total, 3) if total else 0.0,
            "points_per_game": round((wins * 3 + draws) / total, 3) if total else 0.0,
        }

    return {"home": _split(True), "away": _split(False)}


def get_head_to_head(
    conn: duckdb.DuckDBPyConnection,
    team1_id: int,
    team2_id: int,
    n: int = 5,
    before_date: datetime | None = None,
) -> dict[str, Any]:
    """Return head-to-head record between *team1_id* and *team2_id*.

    Args:
        conn: Active DuckDB connection.
        team1_id: Reference team.
        team2_id: Opponent team.
        n: Max recent H2H matches.
        before_date: If set, only include matches before this datetime.
    """
    date_filter = " AND kickoff < ?" if before_date is not None else ""
    date_params = [before_date] if before_date is not None else []

    rows = conn.execute(
        f"""
        SELECT home_team_id, away_team_id, home_score, away_score
        FROM matches
        WHERE status = 'FINISHED'
          AND ((home_team_id = ? AND away_team_id = ?)
               OR (home_team_id = ? AND away_team_id = ?))
          {date_filter}
        ORDER BY kickoff DESC
        LIMIT ?
        """,
        [team1_id, team2_id, team2_id, team1_id] + date_params + [n],
    ).fetchall()

    t1_wins = t2_wins = draws = t1_goals = t2_goals = 0

    for home_id, _away_id, hs, as_ in rows:
        hs = hs or 0
        as_ = as_ or 0
        if home_id == team1_id:
            gf, ga = hs, as_
        else:
            gf, ga = as_, hs

        t1_goals += gf
        t2_goals += ga
        if gf > ga:
            t1_wins += 1
        elif gf < ga:
            t2_wins += 1
        else:
            draws += 1

    total = len(rows)
    return {
        "matches": total,
        "team1_wins": t1_wins,
        "team2_wins": t2_wins,
        "draws": draws,
        "team1_goals": t1_goals,
        "team2_goals": t2_goals,
        "team1_win_rate": round(t1_wins / total, 3) if total else 0.0,
    }


def get_rest_days(
    conn: duckdb.DuckDBPyConnection,
    team_id: int,
    match_date: datetime,
) -> int | None:
    """Return the number of days since *team_id*'s last finished match before *match_date*.

    Args:
        conn: Active DuckDB connection.
        team_id: The team to check.
        match_date: The reference date (usually the upcoming match kickoff).

    Returns:
        Integer days since last match, or ``None`` if no prior match exists.
    """
    row = conn.execute(
        """
        SELECT MAX(kickoff)
        FROM matches
        WHERE status = 'FINISHED'
          AND (home_team_id = ? OR away_team_id = ?)
          AND kickoff < ?
        """,
        [team_id, team_id, match_date],
    ).fetchone()

    if not row or row[0] is None:
        return None

    last_kickoff = row[0]
    if isinstance(last_kickoff, str):
        last_kickoff = datetime.fromisoformat(last_kickoff)

    delta = match_date - last_kickoff
    return max(0, delta.days)
