"""Fantasy Premier League API collector.

Completely free, no API key needed.
Base URL: https://fantasy.premierleague.com/api/

Endpoints used:
- /bootstrap-static/ - all players, teams, gameweeks
- /element-summary/{id}/ - individual player history
- /fixtures/ - all fixtures with difficulty ratings
"""
from __future__ import annotations

from typing import Any

import httpx
import duckdb

FPL_BASE = "https://fantasy.premierleague.com/api"

# FPL position ID -> code
POS_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def _get(path: str) -> dict[str, Any] | list:
    url = f"{FPL_BASE}{path}"
    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    return resp.json()


def sync_fpl_data(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Sync all FPL data: players, fixtures, gameweek history.

    Returns:
        Dict with counts of synced records.
    """
    stats = {"players": 0, "fixtures": 0, "history": 0}

    # 1. Bootstrap - players + teams + gameweeks
    bootstrap = _get("/bootstrap-static/")

    teams_data = bootstrap.get("teams", [])
    team_code_to_name = {t["code"]: t["name"] for t in teams_data}
    team_id_to_code = {t["id"]: t["code"] for t in teams_data}

    # Get PL league_id from our DB
    pl_league = conn.execute(
        "SELECT league_id FROM leagues WHERE code = 'PL' LIMIT 1"
    ).fetchone()
    if not pl_league:
        print("[fpl] No PL league found in DB. Run football-data sync first or use mock data.")
        return stats

    # Map FPL team codes to our internal team_ids
    our_teams = conn.execute(
        "SELECT team_id, name, short_name FROM teams WHERE league_id = ?",
        [pl_league[0]]
    ).fetchall()

    # Fuzzy match by name
    fpl_team_to_internal: dict[int, int] = {}
    for fpl_team in teams_data:
        fpl_name = fpl_team["name"].lower()
        fpl_short = fpl_team["short_name"].lower()
        for our_id, our_name, our_short in our_teams:
            if (fpl_name in our_name.lower() or our_name.lower() in fpl_name
                    or fpl_short == our_short.lower()):
                fpl_team_to_internal[fpl_team["id"]] = our_id
                break

    # 2. Sync players
    conn.execute("DELETE FROM fpl_players")
    elements = bootstrap.get("elements", [])

    player_rows = []
    for el in elements:
        fpl_id = el["id"]
        fpl_team_id = el["team"]
        internal_team_id = fpl_team_to_internal.get(fpl_team_id)
        team_code = team_id_to_code.get(fpl_team_id, 0)
        team_name = team_code_to_name.get(team_code, "")
        pos = POS_MAP.get(el.get("element_type", 0), "MID")

        # Map to internal player_id if possible
        player_name = f"{el.get('first_name', '')} {el.get('second_name', '')}"
        internal_player = None
        if internal_team_id:
            internal_player = conn.execute(
                "SELECT player_id FROM players WHERE team_id = ? AND name LIKE ? LIMIT 1",
                [internal_team_id, f"%{el.get('second_name', 'XXXX')}%"]
            ).fetchone()

        player_id = internal_player[0] if internal_player else None

        status_map = {"a": "Available", "d": "Doubtful", "i": "Unavailable", "s": "Suspended", "u": "Unavailable"}
        injury_status = status_map.get(el.get("status", "a"), "Available")
        injury_note = el.get("news") or None

        player_rows.append((
            fpl_id, player_id, el.get("web_name", ""), pos,
            team_code, team_name,
            el.get("now_cost", 50) / 10,  # FPL stores price * 10
            el.get("total_points", 0),
            float(el.get("form", 0) or 0),
            float(el.get("points_per_game", 0) or 0),
            float(el.get("selected_by_percent", 0) or 0),
            el.get("minutes", 0),
            el.get("goals_scored", 0),
            el.get("assists", 0),
            el.get("clean_sheets", 0),
            el.get("bonus", 0),
            float(el.get("influence", 0) or 0),
            float(el.get("creativity", 0) or 0),
            float(el.get("threat", 0) or 0),
            float(el.get("ict_index", 0) or 0),
            injury_status, injury_note,
        ))

    conn.executemany(
        """INSERT INTO fpl_players
           (fpl_id, player_id, web_name, position, team_code, team_name,
            price, total_points, form, points_per_game, selected_by_pct,
            minutes, goals_scored, assists, clean_sheets, bonus,
            influence, creativity, threat, ict_index, injury_status, injury_note)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        player_rows,
    )
    stats["players"] = len(player_rows)

    # 3. Sync fixtures
    conn.execute("DELETE FROM fpl_fixtures")
    fixtures = _get("/fixtures/")
    if isinstance(fixtures, list):
        fix_rows = []
        for f in fixtures:
            gw = f.get("event")
            if gw is None:
                continue
            kickoff = f.get("kickoff_time")
            fix_rows.append((
                f["id"], gw, kickoff,
                team_id_to_code.get(f.get("team_h"), 0),
                team_id_to_code.get(f.get("team_a"), 0),
                f.get("team_h_difficulty", 3),
                f.get("team_a_difficulty", 3),
                f.get("finished", False),
            ))

        conn.executemany(
            """INSERT INTO fpl_fixtures
               (fixture_id, gameweek, kickoff, home_team_code, away_team_code,
                home_difficulty, away_difficulty, finished)
               VALUES (?,?,?,?,?,?,?,?)""",
            fix_rows,
        )
        stats["fixtures"] = len(fix_rows)

    # 4. Sync gameweek history for top players (by total points, top 100)
    top_players = sorted(elements, key=lambda x: x.get("total_points", 0), reverse=True)[:100]

    conn.execute("DELETE FROM fpl_gameweek_history")
    gw_rows = []
    for el in top_players:
        fpl_id = el["id"]
        try:
            detail = _get(f"/element-summary/{fpl_id}/")
            history = detail.get("history", [])
            for h in history:
                gw_rows.append((
                    fpl_id, h.get("round", 0), h.get("total_points", 0),
                    h.get("minutes", 0), h.get("goals_scored", 0),
                    h.get("assists", 0), h.get("bonus", 0), h.get("bps", 0),
                    h.get("value", 50) / 10, float(h.get("selected", 0) or 0),
                ))
        except Exception:
            continue

    # Deduplicate: keep highest points per (fpl_id, gameweek)
    seen: dict[tuple[int, int], int] = {}
    deduped: list[tuple] = []
    for row in gw_rows:
        key = (row[0], row[1])  # fpl_id, gameweek
        pts = row[2]
        if key not in seen or pts > seen[key]:
            seen[key] = pts
            deduped = [r for r in deduped if (r[0], r[1]) != key]
            deduped.append(row)

    if deduped:
        conn.executemany(
            """INSERT INTO fpl_gameweek_history
               (fpl_id, gameweek, points, minutes, goals, assists, bonus, bps,
                price, selected_by_pct)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            deduped,
        )
    stats["history"] = len(gw_rows)

    print(f"[fpl] Synced: {stats}")
    return stats
