"""FBref player stats collector using soccerdata package.

Uses soccerdata (with undetected-chromedriver) to bypass Cloudflare.
Covers 5 major leagues: PL, La Liga, Bundesliga, Serie A, Ligue 1.
"""
from __future__ import annotations

import time
import warnings
from typing import Any

import duckdb
import numpy as np

LEAGUE_MAP: dict[str, str] = {
    "PL": "ENG-Premier League",
    "PD": "ESP-La Liga",
    "BL1": "GER-Bundesliga",
    "SA": "ITA-Serie A",
    "FL1": "FRA-Ligue 1",
}

SEASONS = [
    {"sd_season": "2024-2025", "label": "2024-25"},
    {"sd_season": "2025-2026", "label": "2025-26"},
]


def _safe(val: Any) -> float:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return 0.0
    return float(val)


def sync_fbref_league(
    conn: duckdb.DuckDBPyConnection,
    league_code: str,
    season: str | None = None,
) -> dict[str, Any]:
    """Sync player stats from FBref for one league. Tries all configured seasons."""
    import soccerdata as sd

    sd_league = LEAGUE_MAP.get(league_code)
    if not sd_league:
        raise ValueError(f"Unsupported league: {league_code}. Supported: {list(LEAGUE_MAP.keys())}")

    # If specific season requested, use it; otherwise try all
    if season:
        seasons_to_try = [{"sd_season": season, "label": season.replace("20", "", 1) if len(season) == 9 else season}]
    else:
        seasons_to_try = SEASONS

    total_upserted = 0
    for s_info in seasons_to_try:
        try:
            result = _sync_single_season(conn, league_code, sd_league, s_info["sd_season"], s_info["label"])
            total_upserted += result
        except Exception as e:
            print(f"[fbref] {league_code} {s_info['label']}: {e}")

    return {"league_code": league_code, "players_upserted": total_upserted}


def _sync_single_season(
    conn: duckdb.DuckDBPyConnection,
    league_code: str,
    sd_league: str,
    season: str,
    season_label: str,
) -> int:
    """Sync one league+season. Returns count of players upserted."""
    import soccerdata as sd

    print(f"[fbref] Scraping {league_code} ({sd_league})...")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fbref = sd.FBref(leagues=sd_league, seasons=season)
        stats_df = fbref.read_player_season_stats(stat_type="standard")

        # Also fetch shooting + misc for additional per-90 stats
        shooting_df = None
        misc_df = None
        try:
            time.sleep(3)
            shooting_df = fbref.read_player_season_stats(stat_type="shooting")
        except Exception:
            pass
        try:
            time.sleep(3)
            misc_df = fbref.read_player_season_stats(stat_type="misc")
        except Exception:
            pass

    if stats_df is None or stats_df.empty:
        return 0

    # Build lookup dicts for shooting/misc by (team, player) key
    def _build_lookup(df: Any) -> dict[tuple[str, str], Any]:
        if df is None or df.empty:
            return {}
        lookup = {}
        for idx, row in df.iterrows():
            key = (str(idx[2]) if len(idx) > 2 else "", str(idx[3]) if len(idx) > 3 else "")
            lookup[key] = row
        return lookup

    shooting_lookup = _build_lookup(shooting_df)
    misc_lookup = _build_lookup(misc_df)

    # Get league_id
    league_row = conn.execute(
        "SELECT league_id FROM leagues WHERE code = ? LIMIT 1", [league_code]
    ).fetchone()
    if not league_row:
        return 0
    league_id = league_row[0]

    # Build team name -> team_id map
    team_rows = conn.execute(
        "SELECT team_id, name, short_name FROM teams WHERE league_id = ?", [league_id]
    ).fetchall()
    team_map: dict[str, int] = {}
    for tid, tname, tshort in team_rows:
        team_map[tname.lower()] = tid
        team_map[tshort.lower()] = tid

    count = 0
    max_pid = conn.execute("SELECT COALESCE(MAX(player_id), 10000) FROM players").fetchone()[0]

    for idx, row in stats_df.iterrows():
        # idx is (league, season, team, player) multi-index
        team_name = idx[2] if len(idx) > 2 else ""
        player_name = idx[3] if len(idx) > 3 else str(idx)

        # Match team
        team_id = None
        tn_lower = team_name.lower()
        for key, tid in team_map.items():
            if key in tn_lower or tn_lower in key:
                team_id = tid
                break

        # Get or create player
        existing = conn.execute(
            "SELECT player_id FROM players WHERE name = ? AND team_id = ?",
            [player_name, team_id],
        ).fetchone() if team_id else None

        if existing:
            player_id = existing[0]
        else:
            max_pid += 1
            player_id = max_pid
            pos_raw = str(row.get(("pos", ""), "")) if ("pos", "") in row.index else ""
            pos = pos_raw.split(",")[0].strip() if pos_raw else "MID"
            pos_map = {"GK": "GK", "DF": "DEF", "MF": "MID", "FW": "FWD"}
            pos = pos_map.get(pos, pos)

            nation = str(row.get(("nation", ""), "")) if ("nation", "") in row.index else ""
            age_raw = row.get(("age", ""), None) if ("age", "") in row.index else None

            born_year = None
            if ("born", "") in row.index:
                try:
                    born_raw = row.get(("born", ""), None)
                    if born_raw is not None and not (isinstance(born_raw, float) and np.isnan(born_raw)):
                        born_year = int(born_raw)
                except Exception:
                    pass

            try:
                conn.execute(
                    """INSERT INTO players (player_id, name, nationality, position, team_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    [player_id, player_name, nation, pos, team_id],
                )
            except Exception:
                pass

            if born_year and born_year > 1970:
                from datetime import date
                try:
                    conn.execute("UPDATE players SET date_of_birth = ? WHERE player_id = ?",
                                 [date(int(born_year), 7, 1), player_id])
                except Exception:
                    pass

        # Extract stats - column names are multi-level tuples
        def g(level0: str, level1: str) -> float:
            try:
                return _safe(row.get((level0, level1), 0))
            except Exception:
                return 0.0

        minutes = int(g("Playing Time", "Min") or 0)
        matches = int(g("Playing Time", "MP") or 0)
        nineties = g("Playing Time", "90s") or max(0.1, minutes / 90)
        goals = int(g("Performance", "Gls") or 0)
        assists = int(g("Performance", "Ast") or 0)

        # xG columns may not exist in standard stats table; fall back to goals per 90
        xg = g("Expected", "xG") or goals
        xa = g("Expected", "xAG") or assists
        gls_p90 = g("Per 90 Minutes", "Gls") or (goals / nineties if nineties > 0 else 0)
        ast_p90 = g("Per 90 Minutes", "Ast") or (assists / nineties if nineties > 0 else 0)
        xg_p90 = g("Per 90 Minutes", "xG") or g("Expected", "xG/90") or gls_p90
        xa_p90 = g("Per 90 Minutes", "xAG") or g("Expected", "xAG/90") or ast_p90

        # Shooting stats
        player_key = (team_name, player_name)
        sh_row = shooting_lookup.get(player_key)
        shots_p90 = 0.0
        if sh_row is not None:
            try:
                shots_p90 = _safe(sh_row.get(("Standard", "Sh/90"), 0))
            except Exception:
                pass

        # Misc stats (tackles, interceptions, fouls drawn = key_passes proxy, crosses)
        ms_row = misc_lookup.get(player_key)
        tackles_p90 = interceptions_p90 = dribbles_p90 = key_passes_p90 = 0.0
        if ms_row is not None:
            try:
                tkl = _safe(ms_row.get(("Performance", "TklW"), 0))
                inter = _safe(ms_row.get(("Performance", "Int"), 0))
                crs = _safe(ms_row.get(("Performance", "Crs"), 0))
                fld = _safe(ms_row.get(("Performance", "Fld"), 0))
                tackles_p90 = round(tkl / nineties, 3) if nineties > 0 else 0
                interceptions_p90 = round(inter / nineties, 3) if nineties > 0 else 0
                key_passes_p90 = round(crs / nineties, 3) if nineties > 0 else 0
                dribbles_p90 = round(fld / nineties, 3) if nineties > 0 else 0
            except Exception:
                pass

        try:
            conn.execute("DELETE FROM player_season_stats WHERE player_id = ? AND season = ? AND league_code = ?",
                         [player_id, season_label, league_code])
            conn.execute(
                """INSERT INTO player_season_stats
                   (player_id, season, league_code, minutes_played, matches_played,
                    goals, assists, xg, xa, xg_per_90, xa_per_90,
                    shots_per_90, key_passes_per_90, progressive_carries_per_90,
                    progressive_passes_per_90, tackles_per_90, interceptions_per_90,
                    aerials_won_per_90, dribbles_per_90, pass_completion_pct)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,?,?,0,?,0)""",
                [player_id, season_label, league_code, minutes, matches,
                 goals, assists, round(xg, 2), round(xa, 2),
                 round(xg_p90, 4), round(xa_p90, 4),
                 round(shots_p90, 3), round(key_passes_p90, 3),
                 round(tackles_p90, 3), round(interceptions_p90, 3),
                 round(dribbles_p90, 3)],
            )
            count += 1
        except Exception as e:
            print(f"[fbref] Error inserting {player_name}: {e}")

    print(f"[fbref] {league_code} {season_label}: {count} players upserted")
    return count


def sync_all_fbref(conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Sync all supported leagues from FBref. ~30s per league."""
    results = {}
    for code in LEAGUE_MAP:
        try:
            results[code] = sync_fbref_league(conn, code)
            time.sleep(5)
        except Exception as e:
            results[code] = {"error": str(e)}
            print(f"[fbref] {code} failed: {e}")
    return results
