from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
import duckdb

from backend.deps import get_database
from backend.features.match_features import (
    get_team_form,
    get_head_to_head,
    get_home_away_splits,
    get_rest_days,
)

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("")
async def list_matches(
    league: str | None = Query(None, description="League code e.g. PL"),
    season: str | None = Query(None, description="Season e.g. 2024-25"),
    status: str | None = Query(None, description="FINISHED | SCHEDULED"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        where_clauses = []
        params: list[Any] = []

        if league:
            where_clauses.append("l.code = ?")
            params.append(league)
        if season:
            where_clauses.append("m.season = ?")
            params.append(season)
        if status:
            where_clauses.append("m.status = ?")
            params.append(status.upper())

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        count_row = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM matches m
            LEFT JOIN leagues l ON l.league_id = m.league_id
            {where_sql}
            """,
            params,
        ).fetchone()
        total = count_row[0] if count_row else 0

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT
                m.match_id, m.season, m.matchday, m.kickoff, m.status,
                m.home_team_id, ht.name AS home_team,
                m.away_team_id, awt.name AS away_team,
                m.home_score, m.away_score,
                m.home_xg, m.away_xg,
                l.code AS league_code, l.name AS league_name
            FROM matches m
            LEFT JOIN leagues l ON l.league_id = m.league_id
            LEFT JOIN teams ht ON ht.team_id = m.home_team_id
            LEFT JOIN teams awt ON awt.team_id = m.away_team_id
            {where_sql}
            ORDER BY CASE WHEN m.status = 'SCHEDULED' THEN 0 ELSE 1 END,
                     CASE WHEN m.status = 'SCHEDULED' THEN m.kickoff END ASC,
                     CASE WHEN m.status != 'SCHEDULED' THEN m.kickoff END DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()

        matches = [
            {
                "match_id": r[0],
                "season": r[1],
                "matchday": r[2],
                "kickoff": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
                "status": r[4],
                "home_team_id": r[5],
                "home_team": r[6],
                "away_team_id": r[7],
                "away_team": r[8],
                "home_score": r[9],
                "away_score": r[10],
                "home_xg": r[11],
                "away_xg": r[12],
                "league_code": r[13],
                "league_name": r[14],
            }
            for r in rows
        ]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "matches": matches,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/{match_id}")
async def get_match(
    match_id: int,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        row = conn.execute(
            """
            SELECT
                m.match_id, m.season, m.matchday, m.kickoff, m.status,
                m.home_team_id, ht.name AS home_team,
                m.away_team_id, awt.name AS away_team,
                m.home_score, m.away_score,
                m.home_xg, m.away_xg,
                l.code AS league_code, l.name AS league_name
            FROM matches m
            LEFT JOIN leagues l ON l.league_id = m.league_id
            LEFT JOIN teams ht ON ht.team_id = m.home_team_id
            LEFT JOIN teams awt ON awt.team_id = m.away_team_id
            WHERE m.match_id = ?
            """,
            [match_id],
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

        match_data: dict[str, Any] = {
            "match_id": row[0],
            "season": row[1],
            "matchday": row[2],
            "kickoff": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
            "status": row[4],
            "home_team_id": row[5],
            "home_team": row[6],
            "away_team_id": row[7],
            "away_team": row[8],
            "home_score": row[9],
            "away_score": row[10],
            "home_xg": row[11],
            "away_xg": row[12],
            "league_code": row[13],
            "league_name": row[14],
        }

        home_id = row[5]
        away_id = row[7]
        kickoff = row[3]
        if hasattr(kickoff, "replace"):
            kickoff_dt = kickoff
        else:
            from datetime import datetime
            kickoff_dt = datetime.fromisoformat(str(kickoff))

        match_data["home_form"] = get_team_form(conn, home_id)
        match_data["away_form"] = get_team_form(conn, away_id)
        match_data["home_splits"] = get_home_away_splits(conn, home_id)
        match_data["away_splits"] = get_home_away_splits(conn, away_id)
        match_data["head_to_head"] = get_head_to_head(conn, home_id, away_id)
        match_data["home_rest_days"] = get_rest_days(conn, home_id, kickoff_dt)
        match_data["away_rest_days"] = get_rest_days(conn, away_id, kickoff_dt)

        return match_data
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/{match_id}/events")
async def get_match_events(
    match_id: int,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        # Check cache first
        rows = conn.execute(
            """SELECT elapsed, extra_time, type, detail, player_name, assist_name, team_name
               FROM match_events WHERE match_id = ? ORDER BY elapsed, extra_time""",
            [match_id],
        ).fetchall()

        if not rows:
            # Try fetching on-demand from API-Football
            rows = _fetch_and_cache_events(match_id, conn)

        events = [
            {"elapsed": r[0], "extra_time": r[1], "type": r[2], "detail": r[3],
             "player_name": r[4], "assist_name": r[5], "team_name": r[6]}
            for r in rows
        ]
        return {"match_id": match_id, "events": events}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/{match_id}/statistics")
async def get_match_statistics(
    match_id: int,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        rows = conn.execute(
            """SELECT team_name, stat_type, stat_value
               FROM match_statistics WHERE match_id = ? ORDER BY team_name, stat_type""",
            [match_id],
        ).fetchall()

        if not rows:
            # Force re-fetch even if events exist (stats may have been missed)
            conn.execute("DELETE FROM match_events WHERE match_id = ?", [match_id])
            _fetch_and_cache_events(match_id, conn)
            rows = conn.execute(
                """SELECT team_name, stat_type, stat_value
                   FROM match_statistics WHERE match_id = ? ORDER BY team_name, stat_type""",
                [match_id],
            ).fetchall()

        teams: dict[str, dict[str, str]] = {}
        for team_name, stat_type, stat_value in rows:
            if team_name not in teams:
                teams[team_name] = {}
            teams[team_name][stat_type] = stat_value

        return {"match_id": match_id, "statistics": teams}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


def _fetch_and_cache_events(match_id: int, conn: duckdb.DuckDBPyConnection) -> list:
    """Fetch events from API-Football by matching team names, cache in DB."""
    import httpx
    from backend.config import settings

    if not settings.API_FOOTBALL_KEY:
        return []

    # Get match info
    match_row = conn.execute(
        """SELECT ht.name, awt.name, m.kickoff, m.status
           FROM matches m
           LEFT JOIN teams ht ON ht.team_id = m.home_team_id
           LEFT JOIN teams awt ON awt.team_id = m.away_team_id
           WHERE m.match_id = ?""",
        [match_id],
    ).fetchone()

    if not match_row or match_row[3] not in ("FINISHED", "IN_PLAY", "PAUSED", "HALFTIME"):
        return []

    home_team, away_team = match_row[0], match_row[1]
    kickoff_date = str(match_row[2])[:10]

    try:
        fixture_id = None

        # For API-Football matches (id > 1M), fixture_id is directly known
        if match_id > 1_000_000:
            fixture_id = match_id - 1_000_000
        else:
            # Check fixture mapping file
            import json
            from pathlib import Path as _Path
            map_path = _Path(__file__).parent.parent.parent / "data" / "match_fixture_map.json"
            if map_path.exists():
                try:
                    with open(map_path) as f:
                        fmap = json.load(f)
                    fixture_id = fmap.get(str(match_id))
                except Exception:
                    pass

            if not fixture_id:
                # For football-data.org matches, try to find on API-Football by today's date only
                api_league_map = {"PL": 39, "PD": 140, "BL1": 78, "SA": 135, "FL1": 61,
                                  "CL": 2, "EL": 3, "ECL": 848}
                league_row = conn.execute(
                    "SELECT l.code FROM matches m JOIN leagues l ON l.league_id = m.league_id WHERE m.match_id = ?",
                    [match_id],
                ).fetchone()
                league_code = league_row[0] if league_row else ""
                api_league_id = api_league_map.get(league_code)

                if api_league_id:
                    from datetime import datetime, timedelta
                    today = datetime.utcnow().strftime("%Y-%m-%d")
                    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
                # Search today and yesterday (free tier allows current day queries)
                if kickoff_date >= yesterday:
                    search_date = kickoff_date if kickoff_date <= today else today
                    try:
                        resp_search = httpx.get(
                            "https://v3.football.api-sports.io/fixtures",
                            params={"league": api_league_id, "season": 2024, "date": search_date},
                            headers={"x-apisports-key": settings.API_FOOTBALL_KEY},
                            timeout=15,
                        )
                        for f in resp_search.json().get("response", []):
                            h = f["teams"]["home"]["name"].lower()
                            a = f["teams"]["away"]["name"].lower()
                            if home_team.lower()[:5] in h and away_team.lower()[:5] in a:
                                fixture_id = f["fixture"]["id"]
                                break
                    except Exception:
                        pass

        if not fixture_id:
            return []

        # Fetch detailed fixture from API-Football by ID
        resp3 = httpx.get(
            "https://v3.football.api-sports.io/fixtures",
            params={"id": fixture_id},
            headers={"x-apisports-key": settings.API_FOOTBALL_KEY},
            timeout=15,
        )
        detail = resp3.json().get("response", [])
        if not detail:
            return []

        fix = detail[0]

        # Store events
        events = fix.get("events", [])
        conn.execute("DELETE FROM match_events WHERE match_id = ?", [match_id])
        max_eid = conn.execute("SELECT COALESCE(MAX(event_id), 0) FROM match_events").fetchone()[0]
        eid = max_eid + 1
        for i, e in enumerate(events):
            try:
                conn.execute(
                    "INSERT INTO match_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)",
                    [eid + i, match_id,
                     e["time"]["elapsed"], e["time"].get("extra"),
                     e["type"], e.get("detail"),
                     e["player"]["name"] if e.get("player") else None,
                     e["assist"]["name"] if e.get("assist") else None,
                     e["team"]["name"] if e.get("team") else None],
                )
            except Exception:
                pass

        # Store statistics
        statistics = fix.get("statistics", [])
        conn.execute("DELETE FROM match_statistics WHERE match_id = ?", [match_id])
        max_sid = conn.execute("SELECT COALESCE(MAX(stat_id), 0) FROM match_statistics").fetchone()[0]
        sid = max_sid + 1
        for ts in statistics:
            tn = ts["team"]["name"]
            for s in ts.get("statistics", []):
                try:
                    conn.execute(
                        "INSERT INTO match_statistics VALUES (?, ?, ?, ?, ?, current_timestamp)",
                        [sid, match_id, tn, s["type"], str(s["value"]) if s["value"] is not None else "0"],
                    )
                    sid += 1
                except Exception:
                    pass

        # Re-fetch from DB
        return conn.execute(
            """SELECT elapsed, extra_time, type, detail, player_name, assist_name, team_name
               FROM match_events WHERE match_id = ? ORDER BY elapsed, extra_time""",
            [match_id],
        ).fetchall()

    except Exception as e:
        print(f"[events] Failed to fetch from API-Football: {e}")
        return []


@router.get("/teams/list")
async def list_teams(
    league: str | None = Query(None, description="League code e.g. PL"),
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        params: list[Any] = []
        where_sql = ""
        if league:
            where_sql = "WHERE l.code = ?"
            params.append(league)

        rows = conn.execute(
            f"""
            SELECT MIN(t.team_id) AS team_id, t.name, MIN(t.short_name) AS short_name, MIN(l.code) AS league_code
            FROM teams t
            LEFT JOIN leagues l ON l.league_id = t.league_id
            {where_sql}
            GROUP BY t.name
            ORDER BY t.name
            """,
            params,
        ).fetchall()

        teams = [
            {"team_id": r[0], "name": r[1], "short_name": r[2], "league_code": r[3]}
            for r in rows
        ]
        return {"teams": teams}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
