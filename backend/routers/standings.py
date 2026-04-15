from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
import duckdb

from backend.deps import get_database

router = APIRouter(prefix="/standings", tags=["standings"])


@router.get("")
async def get_standings(
    league: str = Query("PL"),
    season: str = Query("2024-25"),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Compute league standings from match results."""
    rows = conn.execute(
        """
        SELECT t.team_id, t.name, t.short_name,
               COUNT(*) AS played,
               SUM(CASE WHEN (m.home_team_id = t.team_id AND m.home_score > m.away_score)
                        OR (m.away_team_id = t.team_id AND m.away_score > m.home_score) THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) AS draws,
               SUM(CASE WHEN (m.home_team_id = t.team_id AND m.home_score < m.away_score)
                        OR (m.away_team_id = t.team_id AND m.away_score < m.home_score) THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_score ELSE m.away_score END) AS goals_for,
               SUM(CASE WHEN m.home_team_id = t.team_id THEN m.away_score ELSE m.home_score END) AS goals_against
        FROM matches m
        JOIN teams t ON t.team_id = m.home_team_id OR t.team_id = m.away_team_id
        JOIN leagues l ON l.league_id = m.league_id
        WHERE m.status = 'FINISHED' AND l.code = ? AND m.season = ?
        GROUP BY t.team_id, t.name, t.short_name
        ORDER BY (SUM(CASE WHEN (m.home_team_id = t.team_id AND m.home_score > m.away_score)
                       OR (m.away_team_id = t.team_id AND m.away_score > m.home_score) THEN 3
                       WHEN m.home_score = m.away_score THEN 1 ELSE 0 END)) DESC,
                 (SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_score ELSE m.away_score END) -
                  SUM(CASE WHEN m.home_team_id = t.team_id THEN m.away_score ELSE m.home_score END)) DESC
        """,
        [league, season],
    ).fetchall()

    standings = []
    for i, r in enumerate(rows):
        pts = r[4] * 3 + r[5]
        gd = r[7] - r[8]
        standings.append(
            {
                "position": i + 1,
                "team_id": r[0],
                "name": r[1],
                "short_name": r[2],
                "played": r[3],
                "wins": r[4],
                "draws": r[5],
                "losses": r[6],
                "goals_for": r[7],
                "goals_against": r[8],
                "goal_difference": gd,
                "points": pts,
            }
        )
    return {"league": league, "season": season, "standings": standings}


@router.get("/tournament")
async def get_tournament(
    league: str = Query("CL"),
    season: str = Query("2024-25"),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Get tournament stage view for European competitions (CL, EL, ECL)."""
    # League stage: matchday 1-8 → compute mini standings
    league_stage_rows = conn.execute(
        """
        SELECT t.team_id, t.name, t.short_name,
               COUNT(*) AS played,
               SUM(CASE WHEN (m.home_team_id = t.team_id AND m.home_score > m.away_score)
                        OR (m.away_team_id = t.team_id AND m.away_score > m.home_score) THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) AS draws,
               SUM(CASE WHEN (m.home_team_id = t.team_id AND m.home_score < m.away_score)
                        OR (m.away_team_id = t.team_id AND m.away_score < m.home_score) THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_score ELSE m.away_score END) AS gf,
               SUM(CASE WHEN m.home_team_id = t.team_id THEN m.away_score ELSE m.home_score END) AS ga
        FROM matches m
        JOIN teams t ON t.team_id = m.home_team_id OR t.team_id = m.away_team_id
        JOIN leagues l ON l.league_id = m.league_id
        WHERE m.status = 'FINISHED' AND l.code = ? AND m.season = ? AND m.matchday <= 8
        GROUP BY t.team_id, t.name, t.short_name
        ORDER BY (SUM(CASE WHEN (m.home_team_id = t.team_id AND m.home_score > m.away_score)
                       OR (m.away_team_id = t.team_id AND m.away_score > m.home_score) THEN 3
                       WHEN m.home_score = m.away_score THEN 1 ELSE 0 END)) DESC,
                 (SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_score ELSE m.away_score END) -
                  SUM(CASE WHEN m.home_team_id = t.team_id THEN m.away_score ELSE m.home_score END)) DESC
        """,
        [league, season],
    ).fetchall()

    league_stage = []
    for i, r in enumerate(league_stage_rows):
        pts = r[4] * 3 + r[5]
        gd = r[7] - r[8]
        league_stage.append({
            "position": i + 1, "team_id": r[0], "name": r[1], "short_name": r[2],
            "played": r[3], "wins": r[4], "draws": r[5], "losses": r[6],
            "goals_for": r[7], "goals_against": r[8], "goal_difference": gd, "points": pts,
        })

    # Knockout rounds: matchday > 8 (96=R16, 97=QF, 98=SF, 99=Final)
    knockout_rows = conn.execute(
        """
        SELECT m.matchday, m.match_id, m.status,
               ht.name AS home_team, ht.short_name AS home_short,
               awt.name AS away_team, awt.short_name AS away_short,
               m.home_score, m.away_score, m.kickoff
        FROM matches m
        JOIN leagues l ON l.league_id = m.league_id
        LEFT JOIN teams ht ON ht.team_id = m.home_team_id
        LEFT JOIN teams awt ON awt.team_id = m.away_team_id
        WHERE l.code = ? AND m.season = ? AND m.matchday > 8
        ORDER BY m.matchday ASC, m.kickoff ASC
        """,
        [league, season],
    ).fetchall()

    stage_names = {96: "Round of 16", 97: "Quarter-Finals", 98: "Semi-Finals", 99: "Final"}
    knockout: dict[str, list] = {}
    for r in knockout_rows:
        md = r[0]
        stage = stage_names.get(md, f"Round {md}")
        if stage not in knockout:
            knockout[stage] = []
        knockout[stage].append({
            "match_id": r[1], "status": r[2],
            "home_team": r[3], "home_short": r[4],
            "away_team": r[5], "away_short": r[6],
            "home_score": r[7], "away_score": r[8],
            "kickoff": r[9].isoformat() if hasattr(r[9], "isoformat") else str(r[9]),
        })

    return {
        "league": league, "season": season,
        "league_stage": league_stage,
        "knockout": knockout,
    }
