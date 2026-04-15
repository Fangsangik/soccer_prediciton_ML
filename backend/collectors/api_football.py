"""API-Football (RapidAPI) collector for European competitions.

Covers: Champions League, Europa League, Conference League.
Free tier: 100 requests/day.
"""
from __future__ import annotations

import time
from typing import Any
from datetime import datetime

import httpx
import duckdb

from backend.config import settings

BASE_URL = "https://v3.football.api-sports.io"

COMPETITIONS = {
    "CL": {"api_id": 2, "name": "UEFA Champions League"},
    "EL": {"api_id": 3, "name": "UEFA Europa League"},
    "ECL": {"api_id": 848, "name": "UEFA Conference League"},
}


def _headers() -> dict[str, str]:
    return {"x-apisports-key": settings.API_FOOTBALL_KEY}


def _get(path: str, params: dict | None = None) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    resp = httpx.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    # Check for API errors
    errors = data.get("errors", {})
    if errors:
        raise ValueError(f"API-Football error: {errors}")
    return data


def sync_competition(
    conn: duckdb.DuckDBPyConnection,
    comp_code: str,
    season: int = 2024,
) -> dict[str, Any]:
    """Sync matches for a European competition from API-Football."""
    comp = COMPETITIONS.get(comp_code)
    if not comp:
        raise ValueError(f"Unknown competition: {comp_code}. Use: {list(COMPETITIONS.keys())}")

    api_id = comp["api_id"]
    comp_name = comp["name"]
    season_label = f"{season}-{str(season + 1)[2:]}"

    print(f"[api-football] Syncing {comp_code} ({comp_name}) season {season}...")

    # Upsert league
    league_row = conn.execute(
        "SELECT league_id FROM leagues WHERE code = ? AND season = ?",
        [comp_code, season_label],
    ).fetchone()

    if league_row:
        league_id = league_row[0]
    else:
        max_id = conn.execute("SELECT COALESCE(MAX(league_id), 0) FROM leagues").fetchone()[0]
        league_id = max_id + 1
        conn.execute(
            "INSERT INTO leagues VALUES (?, ?, ?, ?, ?)",
            [league_id, comp_code, comp_name, "Europe", season_label],
        )

    # Fetch fixtures
    data = _get("/fixtures", {"league": api_id, "season": season})
    fixtures = data.get("response", [])

    teams_synced = set()
    matches_synced = 0

    for f in fixtures:
        fix = f.get("fixture", {})
        teams_data = f.get("teams", {})
        goals = f.get("goals", {})
        score = f.get("score", {})

        home_info = teams_data.get("home", {})
        away_info = teams_data.get("away", {})

        # Upsert teams
        for team_info in [home_info, away_info]:
            api_team_id = team_info.get("id", 0)
            if api_team_id in teams_synced:
                continue

            team_name = team_info.get("name", "")
            short = team_name[:3].upper() if team_name else "UNK"

            existing = conn.execute(
                "SELECT team_id FROM teams WHERE name = ? AND league_id = ?",
                [team_name, league_id],
            ).fetchone()

            if not existing:
                max_tid = conn.execute("SELECT COALESCE(MAX(team_id), 0) FROM teams").fetchone()[0]
                conn.execute(
                    "INSERT INTO teams VALUES (?, ?, ?, ?, ?)",
                    [max_tid + 1, team_name, short, team_info.get("logo"), league_id],
                )
            teams_synced.add(api_team_id)

        # Map team names to our IDs
        home_row = conn.execute(
            "SELECT team_id FROM teams WHERE name = ? AND league_id = ?",
            [home_info.get("name"), league_id],
        ).fetchone()
        away_row = conn.execute(
            "SELECT team_id FROM teams WHERE name = ? AND league_id = ?",
            [away_info.get("name"), league_id],
        ).fetchone()

        if not home_row or not away_row:
            continue

        home_id = home_row[0]
        away_id = away_row[0]

        # Match status mapping
        api_status = fix.get("status", {}).get("short", "NS")
        status_map = {
            "FT": "FINISHED", "AET": "FINISHED", "PEN": "FINISHED",
            "NS": "SCHEDULED", "TBD": "SCHEDULED",
            "1H": "IN_PLAY", "HT": "IN_PLAY", "2H": "IN_PLAY",
            "ET": "IN_PLAY", "P": "IN_PLAY", "BT": "IN_PLAY",
            "PST": "POSTPONED", "CANC": "POSTPONED",
        }
        status = status_map.get(api_status, "SCHEDULED")

        # Kickoff
        kickoff_str = fix.get("date", "")
        try:
            kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        home_score = goals.get("home")
        away_score = goals.get("away")

        # Use API fixture ID + offset to avoid collision with football-data.org IDs
        match_id = fix.get("id", 0) + 1_000_000

        # Round info
        round_str = f.get("league", {}).get("round", "")
        matchday = _parse_round(round_str)

        # Upsert match
        existing_match = conn.execute(
            "SELECT match_id FROM matches WHERE match_id = ?", [match_id]
        ).fetchone()

        if existing_match:
            conn.execute(
                "UPDATE matches SET status = ?, home_score = ?, away_score = ? WHERE match_id = ?",
                [status, home_score, away_score, match_id],
            )
        else:
            conn.execute(
                """INSERT INTO matches
                   (match_id, league_id, season, matchday, kickoff, status,
                    home_team_id, away_team_id, home_score, away_score, home_xg, away_xg)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
                [match_id, league_id, season_label, matchday, kickoff,
                 status, home_id, away_id, home_score, away_score],
            )
            matches_synced += 1

    result = {"comp_code": comp_code, "season": season_label,
              "teams_synced": len(teams_synced), "matches_synced": matches_synced}
    print(f"[api-football] {comp_code}: {result}")
    return result


def _parse_round(round_str: str) -> int:
    """Parse round string like 'League Stage - 1' or 'Round of 16' to matchday number."""
    if not round_str:
        return 0
    r = round_str.lower()
    if "final" in r and "semi" not in r and "quarter" not in r:
        return 99
    if "semi" in r:
        return 98
    if "quarter" in r:
        return 97
    if "16" in r:
        return 96
    # Try to extract number
    import re
    nums = re.findall(r'\d+', round_str)
    return int(nums[-1]) if nums else 0


def sync_fixture_details(conn: duckdb.DuckDBPyConnection, fixture_id: int) -> dict[str, Any]:
    """Fetch events and statistics for a specific fixture from API-Football."""
    data = _get("/fixtures", {"id": fixture_id})
    response = data.get("response", [])
    if not response:
        return {"events": 0, "statistics": 0}

    fixture = response[0]
    match_id = fixture_id + 1_000_000

    # Sync events (goals, cards, substitutions)
    events = fixture.get("events", [])
    conn.execute("DELETE FROM match_events WHERE match_id = ?", [match_id])
    for i, e in enumerate(events):
        conn.execute(
            "INSERT INTO match_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)",
            [fixture_id * 100 + i, match_id,
             e["time"]["elapsed"], e["time"].get("extra"),
             e["type"], e.get("detail"),
             e["player"]["name"] if e.get("player") else None,
             e["assist"]["name"] if e.get("assist") else None,
             e["team"]["name"] if e.get("team") else None],
        )

    # Sync statistics
    statistics = fixture.get("statistics", [])
    conn.execute("DELETE FROM match_statistics WHERE match_id = ?", [match_id])
    stat_id_base = fixture_id * 1000
    for team_stat in statistics:
        team_name = team_stat["team"]["name"]
        for j, s in enumerate(team_stat.get("statistics", [])):
            conn.execute(
                "INSERT INTO match_statistics VALUES (?, ?, ?, ?, ?, current_timestamp)",
                [stat_id_base + j, match_id, team_name,
                 s["type"], str(s["value"]) if s["value"] is not None else "0"],
            )
        stat_id_base += 100

    result = {
        "events": len(events),
        "statistics": sum(len(ts.get("statistics", [])) for ts in statistics),
    }
    print(f"[api-football] Fixture {fixture_id}: {result}")
    return result


def sync_all_european(conn: duckdb.DuckDBPyConnection, season: int = 2024) -> dict[str, Any]:
    """Sync all European competitions. Uses ~3 requests (1 per comp)."""
    results = {}
    for code in COMPETITIONS:
        try:
            results[code] = sync_competition(conn, code, season)
            time.sleep(2)
        except Exception as e:
            results[code] = {"error": str(e)}
            print(f"[api-football] {code} failed: {e}")
    return results
