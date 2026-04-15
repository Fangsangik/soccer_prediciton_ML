"""football-data.org API collector.

Free tier: 10 requests/minute. Covers matches, teams, standings for major leagues.
API docs: https://www.football-data.org/documentation/api

Requires API key: register free at https://www.football-data.org/client/register
Set FOOTBALL_DATA_API_KEY in .env or config.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import httpx
import duckdb

from backend.config import settings

BASE_URL = "https://api.football-data.org/v4"

# football-data.org league codes
LEAGUE_MAP = {
    "PL": "PL",       # Premier League
    "PD": "PD",       # La Liga
    "BL1": "BL1",     # Bundesliga
    "SA": "SA",        # Serie A
    "FL1": "FL1",      # Ligue 1
    "CL": "CL",       # UEFA Champions League (free tier supported)
    # EL (Europa League) and Conference League require paid tier
}

# Map API team IDs to our internal IDs (populated during sync)
_team_id_cache: dict[int, int] = {}


def _headers() -> dict[str, str]:
    return {"X-Auth-Token": settings.FOOTBALL_DATA_API_KEY}


def _get(path: str, params: dict | None = None) -> dict[str, Any]:
    """Make a rate-limited GET request to football-data.org."""
    url = f"{BASE_URL}{path}"
    resp = httpx.get(url, headers=_headers(), params=params, timeout=15)
    if resp.status_code == 429:
        # Rate limited - wait and retry once
        time.sleep(6)
        resp = httpx.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def sync_league(conn: duckdb.DuckDBPyConnection, league_code: str, season: str = "2025") -> dict[str, int]:
    """Sync a league's teams and matches from football-data.org.

    Args:
        conn: DuckDB connection
        league_code: One of PL, PD, BL1, SA, FL1
        season: Year the season starts (e.g. "2025" for 2025-26)

    Returns:
        Dict with counts: teams_synced, matches_synced
    """
    if not settings.FOOTBALL_DATA_API_KEY:
        raise ValueError("FOOTBALL_DATA_API_KEY not set. Register free at https://www.football-data.org/client/register")

    api_code = LEAGUE_MAP.get(league_code)
    if not api_code:
        raise ValueError(f"Unsupported league: {league_code}")

    stats = {"teams_synced": 0, "matches_synced": 0}

    # 1. Get competition info + teams
    comp_data = _get(f"/competitions/{api_code}/teams", {"season": season})
    competition = comp_data.get("competition", {})
    season_info = comp_data.get("season", {})

    # Upsert league
    season_label = f"{season}-{str(int(season)+1)[2:]}"  # "2025-26"
    league_row = conn.execute(
        "SELECT league_id FROM leagues WHERE code = ? AND season = ?",
        [league_code, season_label]
    ).fetchone()

    if league_row:
        league_id = league_row[0]
    else:
        max_id = conn.execute("SELECT COALESCE(MAX(league_id), 0) FROM leagues").fetchone()[0]
        league_id = max_id + 1
        conn.execute(
            "INSERT INTO leagues VALUES (?, ?, ?, ?, ?)",
            [league_id, league_code, competition.get("name", league_code),
             competition.get("area", {}).get("name", ""), season_label]
        )

    # 2. Sync teams
    api_teams = comp_data.get("teams", [])
    for t in api_teams:
        api_team_id = t["id"]
        name = t.get("shortName") or t.get("name", "")
        tla = t.get("tla", name[:3].upper())
        crest = t.get("crest", "")

        existing = conn.execute(
            "SELECT team_id FROM teams WHERE name = ? AND league_id = ?",
            [name, league_id]
        ).fetchone()

        if existing:
            internal_id = existing[0]
        else:
            max_tid = conn.execute("SELECT COALESCE(MAX(team_id), 0) FROM teams").fetchone()[0]
            internal_id = max_tid + 1
            conn.execute(
                "INSERT INTO teams VALUES (?, ?, ?, ?, ?)",
                [internal_id, name, tla, crest, league_id]
            )
            stats["teams_synced"] += 1

        _team_id_cache[api_team_id] = internal_id

    time.sleep(6)  # Rate limit

    # 3. Sync matches
    matches_data = _get(f"/competitions/{api_code}/matches", {"season": season})
    api_matches = matches_data.get("matches", [])

    for m in api_matches:
        home_api_id = m.get("homeTeam", {}).get("id")
        away_api_id = m.get("awayTeam", {}).get("id")

        home_id = _team_id_cache.get(home_api_id)
        away_id = _team_id_cache.get(away_api_id)
        if not home_id or not away_id:
            continue

        api_status = m.get("status", "SCHEDULED")
        status_map = {
            "FINISHED": "FINISHED",
            "IN_PLAY": "IN_PLAY",
            "PAUSED": "IN_PLAY",
            "SCHEDULED": "SCHEDULED",
            "TIMED": "SCHEDULED",
            "POSTPONED": "POSTPONED",
            "CANCELLED": "POSTPONED",
        }
        status = status_map.get(api_status, "SCHEDULED")

        kickoff_str = m.get("utcDate", "")
        try:
            kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        score = m.get("score", {})
        ft = score.get("fullTime", {})
        home_score = ft.get("home")
        away_score = ft.get("away")

        matchday = m.get("matchday", 0)
        api_match_id = m.get("id", 0)

        # Use API match ID as our match_id for dedup
        existing = conn.execute(
            "SELECT match_id FROM matches WHERE match_id = ?",
            [api_match_id]
        ).fetchone()

        if existing:
            # Update score/status
            conn.execute(
                """UPDATE matches SET status = ?, home_score = ?, away_score = ?
                   WHERE match_id = ?""",
                [status, home_score, away_score, api_match_id]
            )
        else:
            conn.execute(
                """INSERT INTO matches
                   (match_id, league_id, season, matchday, kickoff, status,
                    home_team_id, away_team_id, home_score, away_score,
                    home_xg, away_xg)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
                [api_match_id, league_id, season_label, matchday, kickoff,
                 status, home_id, away_id, home_score, away_score]
            )
            stats["matches_synced"] += 1

    return stats


def sync_all_leagues(conn: duckdb.DuckDBPyConnection, season: str = "2025") -> dict[str, Any]:
    """Sync all supported leagues. Respects rate limits (6s between requests)."""
    results = {}
    for code in LEAGUE_MAP:
        try:
            stats = sync_league(conn, code, season)
            results[code] = stats
            print(f"[football-data] {code}: {stats}")
            time.sleep(6)
        except Exception as e:
            results[code] = {"error": str(e)}
            print(f"[football-data] {code} failed: {e}")
    return results
