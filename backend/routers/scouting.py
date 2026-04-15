from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import duckdb

from backend.deps import get_database
from backend.services.scouting_service import get_player_profile, find_similar, get_undervalued, search_players

router = APIRouter(prefix="/scouting", tags=["scouting"])


class SimilarPlayersRequest(BaseModel):
    player_id: int
    filters: dict[str, Any] = {}
    top_n: int = 10
    season: str = "2024-25"


@router.get("/search")
async def search(
    q: str = Query("", description="Player name search"),
    league: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        players = search_players(q, conn, league, limit)
        return {"players": players, "count": len(players)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/players/{player_id}")
async def player_profile(
    player_id: int,
    season: str = Query("2024-25"),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        profile = get_player_profile(player_id, conn, season)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
        return profile
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/similar")
async def similar_players(
    request: SimilarPlayersRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        result = find_similar(
            request.player_id,
            request.filters,
            conn,
            request.season,
            request.top_n,
        )
        if "error" in result and not result.get("similar_players"):
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/undervalued")
async def undervalued_players(
    position: str | None = Query(None, description="GK | DEF | MID | FWD"),
    league: str | None = Query(None, description="PL | PD | BL1 | SA | FL1"),
    min_minutes: int = Query(450, ge=0),
    max_market_value: int | None = Query(None),
    top_n: int = Query(20, ge=1, le=100),
    season: str = Query("2024-25"),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        filters: dict[str, Any] = {"min_minutes": min_minutes}
        if position:
            filters["position"] = position
        if league:
            filters["league"] = league
        if max_market_value:
            filters["max_market_value"] = max_market_value

        players = get_undervalued(filters, conn, season, top_n)
        return {"undervalued_players": players, "count": len(players)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/team-key-players/{team_name}")
async def team_key_players(
    team_name: str,
    season: str = Query("2024-25"),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Get top 2 key players for a team by goals+assists."""
    try:
        rows = conn.execute(
            """SELECT p.name, p.position, s.goals, s.assists, s.xg_per_90, s.xa_per_90, s.minutes_played
               FROM players p
               JOIN player_season_stats s ON s.player_id = p.player_id AND s.season = ?
               JOIN teams t ON t.team_id = p.team_id
               WHERE t.name = ? AND s.minutes_played >= 450
               ORDER BY (COALESCE(s.goals,0) + COALESCE(s.assists,0)) DESC
               LIMIT 2""",
            [season, team_name],
        ).fetchall()

        players = [
            {"name": r[0], "position": r[1], "goals": r[2] or 0, "assists": r[3] or 0,
             "xg_per_90": round(float(r[4] or 0), 2), "xa_per_90": round(float(r[5] or 0), 2)}
            for r in rows
        ]
        return {"team": team_name, "key_players": players}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/rankings")
async def player_rankings(
    league: str = Query("PL"),
    season: str = Query("2024-25"),
    category: str = Query("goals", description="goals|assists|clean_sheets|cards"),
    limit: int = Query(20),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Get player rankings by category."""
    try:
        european_comps = {"CL", "EL", "ECL"}

        # For European competitions, find the teams in that comp then query their
        # domestic stats (since player_season_stats is keyed to domestic leagues).
        if league in european_comps:
            team_names = conn.execute(
                "SELECT DISTINCT t.name FROM teams t JOIN leagues l ON l.league_id = t.league_id WHERE l.code = ?",
                [league],
            ).fetchall()
            if not team_names:
                return {"category": category, "players": [], "count": 0}
            placeholders = ",".join(["?" for _ in team_names])
            team_name_list = [tn[0] for tn in team_names]

            if category == "goals":
                rows = conn.execute(
                    f"""SELECT p.name, t.name AS team, p.position,
                              s.goals AS stat_value, s.minutes_played
                       FROM players p
                       JOIN player_season_stats s ON s.player_id = p.player_id AND s.season = ?
                       LEFT JOIN teams t ON t.team_id = p.team_id
                       WHERE t.name IN ({placeholders}) AND s.minutes_played >= 450
                       ORDER BY s.goals DESC
                       LIMIT ?""",
                    [season] + team_name_list + [limit],
                ).fetchall()
            elif category == "assists":
                rows = conn.execute(
                    f"""SELECT p.name, t.name AS team, p.position,
                              s.assists AS stat_value, s.minutes_played
                       FROM players p
                       JOIN player_season_stats s ON s.player_id = p.player_id AND s.season = ?
                       LEFT JOIN teams t ON t.team_id = p.team_id
                       WHERE t.name IN ({placeholders}) AND s.minutes_played >= 450
                       ORDER BY s.assists DESC
                       LIMIT ?""",
                    [season] + team_name_list + [limit],
                ).fetchall()
            elif category == "clean_sheets":
                rows = conn.execute(
                    f"""SELECT p.name, t.name AS team, p.position,
                              s.clean_sheets AS stat_value, s.minutes_played
                       FROM players p
                       JOIN player_season_stats s ON s.player_id = p.player_id AND s.season = ?
                       LEFT JOIN teams t ON t.team_id = p.team_id
                       WHERE t.name IN ({placeholders}) AND p.position = 'GK'
                         AND s.minutes_played >= 450
                       ORDER BY s.clean_sheets DESC NULLS LAST
                       LIMIT ?""",
                    [season] + team_name_list + [limit],
                ).fetchall()
            else:
                rows = []
        elif category == "goals":
            rows = conn.execute(
                """SELECT p.name, t.name AS team, p.position,
                          s.goals AS stat_value, s.minutes_played
                   FROM players p
                   JOIN player_season_stats s ON s.player_id = p.player_id AND s.season = ?
                   LEFT JOIN teams t ON t.team_id = p.team_id
                   LEFT JOIN leagues l ON l.league_id = t.league_id
                   WHERE l.code = ? AND s.minutes_played >= 450
                   ORDER BY s.goals DESC
                   LIMIT ?""",
                [season, league, limit],
            ).fetchall()
        elif category == "assists":
            rows = conn.execute(
                """SELECT p.name, t.name AS team, p.position,
                          s.assists AS stat_value, s.minutes_played
                   FROM players p
                   JOIN player_season_stats s ON s.player_id = p.player_id AND s.season = ?
                   LEFT JOIN teams t ON t.team_id = p.team_id
                   LEFT JOIN leagues l ON l.league_id = t.league_id
                   WHERE l.code = ? AND s.minutes_played >= 450
                   ORDER BY s.assists DESC
                   LIMIT ?""",
                [season, league, limit],
            ).fetchall()
        elif category == "clean_sheets":
            # Compute clean sheets from matches: count games where team conceded 0
            rows = conn.execute(
                """SELECT t.name AS team_name, t.short_name,
                          COUNT(*) AS clean_sheets,
                          SUM(CASE WHEN m.home_team_id = t.team_id THEN 1 ELSE 0 END) +
                          SUM(CASE WHEN m.away_team_id = t.team_id THEN 1 ELSE 0 END) AS games
                   FROM matches m
                   JOIN teams t ON (t.team_id = m.home_team_id AND m.away_score = 0)
                                OR (t.team_id = m.away_team_id AND m.home_score = 0)
                   JOIN leagues l ON l.league_id = m.league_id
                   WHERE m.status = 'FINISHED' AND l.code = ? AND m.season = ?
                   GROUP BY t.name, t.short_name
                   ORDER BY COUNT(*) DESC
                   LIMIT ?""",
                [league, season, limit],
            ).fetchall()
            # Reformat to match expected shape: name, team, position, stat_value, minutes
            rows = [(r[0], r[0], 'Team', r[2], r[3]) for r in rows]
        else:
            rows = []

        players = [
            {
                "name": r[0] or "",
                "team": r[1] or "",
                "position": r[2] or "",
                "stat_value": int(r[3] or 0),
                "minutes": int(r[4] or 0),
            }
            for r in rows
        ]
        return {"category": category, "players": players, "count": len(players)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/top-player")
async def top_player(
    league: str = Query("PL"),
    season: str = Query("2024-25"),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Get the top performing player for a league (by xG+xA per 90)."""
    try:
        row = conn.execute(
            """SELECT p.player_id, p.name, p.position, t.name AS team, l.code AS league,
                      s.xg_per_90, s.xa_per_90, s.goals, s.assists, s.minutes_played
               FROM players p
               JOIN player_season_stats s ON s.player_id = p.player_id AND s.season = ?
               LEFT JOIN teams t ON t.team_id = p.team_id
               LEFT JOIN leagues l ON l.league_id = t.league_id
               WHERE l.code = ? AND s.minutes_played >= 900
               ORDER BY (COALESCE(s.xg_per_90,0) + COALESCE(s.xa_per_90,0)) DESC
               LIMIT 1""",
            [season, league],
        ).fetchone()

        if not row:
            return {"player": None}

        return {
            "player": {
                "player_id": row[0], "name": row[1], "position": row[2],
                "team": row[3] or "", "league": row[4] or "",
                "xg_per_90": round(float(row[5] or 0), 2),
                "xa_per_90": round(float(row[6] or 0), 2),
                "goals": row[7] or 0, "assists": row[8] or 0,
                "minutes": row[9] or 0,
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
