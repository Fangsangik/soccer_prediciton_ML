"""Transfermarkt market value collector.

Scrapes player market values directly from Transfermarkt squad pages using
browser-like headers. No external API dependency.

Each squad page returns all players with their current market values.
Players are matched to our DB by name (exact -> last-name fallback).
"""
from __future__ import annotations

import re
import time
import unicodedata
from typing import Any

import duckdb

# ---------------------------------------------------------------------------
# Team -> Transfermarkt club ID mapping for 5 major leagues
# ---------------------------------------------------------------------------
TEAM_TM_IDS: dict[str, int] = {
    # Premier League
    "Arsenal": 11,
    "Aston Villa": 405,
    "Bournemouth": 989,
    "Brentford": 1148,
    "Brighton": 1237,
    "Chelsea": 631,
    "Crystal Palace": 873,
    "Everton": 29,
    "Fulham": 931,
    "Ipswich": 677,
    "Leicester": 1003,
    "Liverpool": 31,
    "Man City": 281,
    "Manchester City": 281,
    "Man United": 985,
    "Manchester United": 985,
    "Newcastle": 762,
    "Newcastle United": 762,
    "Nottm Forest": 703,
    "Nottingham Forest": 703,
    "Southampton": 180,
    "Tottenham": 148,
    "Tottenham Hotspur": 148,
    "West Ham": 379,
    "West Ham United": 379,
    "Wolves": 543,
    "Wolverhampton": 543,
    # La Liga
    "Real Madrid": 418,
    "Barcelona": 131,
    "Atletico Madrid": 13,
    "Athletic Club": 621,
    "Real Sociedad": 681,
    "Real Betis": 150,
    "Villarreal": 1050,
    "Girona": 12321,
    "Sevilla": 368,
    "Valencia": 1049,
    "Osasuna": 331,
    "Celta Vigo": 940,
    "Getafe": 3709,
    "Rayo Vallecano": 367,
    "Mallorca": 237,
    "Las Palmas": 472,
    "Alaves": 1108,
    "Espanyol": 714,
    "Leganes": 1244,
    "Valladolid": 366,
    # Bundesliga
    "Bayern Munich": 27,
    "Dortmund": 16,
    "Borussia Dortmund": 16,
    "Leverkusen": 15,
    "Bayer Leverkusen": 15,
    "RB Leipzig": 23826,
    "Frankfurt": 9,
    "Eintracht Frankfurt": 9,
    "Stuttgart": 79,
    "VfB Stuttgart": 79,
    "Wolfsburg": 82,
    "VfL Wolfsburg": 82,
    "Werder Bremen": 86,
    "Hoffenheim": 533,
    "TSG Hoffenheim": 533,
    "Freiburg": 83,
    "SC Freiburg": 83,
    "Augsburg": 167,
    "FC Augsburg": 167,
    "Mainz": 39,
    "Mainz 05": 39,
    "Borussia Mönchengladbach": 18,
    "Gladbach": 18,
    "Union Berlin": 89,
    "1. FC Union Berlin": 89,
    "Bochum": 80,
    "VfL Bochum": 80,
    "Holstein Kiel": 514,
    "St. Pauli": 35,
    "FC St. Pauli": 35,
    "Heidenheim": 2756,
    # Serie A
    "Inter Milan": 46,
    "Inter": 46,
    "AC Milan": 5,
    "Milan": 5,
    "Juventus": 506,
    "Napoli": 6195,
    "Atalanta": 800,
    "Roma": 12,
    "AS Roma": 12,
    "Lazio": 398,
    "SS Lazio": 398,
    "Fiorentina": 430,
    "Bologna": 1025,
    "Torino": 416,
    "Udinese": 410,
    "Genoa": 252,
    "Cagliari": 419,
    "Lecce": 394,
    "Verona": 276,
    "Hellas Verona": 276,
    "Venezia": 2409,
    "Como": 201,
    "Empoli": 749,
    "Parma": 98,
    "Monza": 5765,
    # Ligue 1
    "PSG": 583,
    "Paris Saint-Germain": 583,
    "Marseille": 244,
    "Olympique Marseille": 244,
    "Monaco": 162,
    "AS Monaco": 162,
    "Lyon": 1041,
    "Olympique Lyonnais": 1041,
    "Lens": 826,
    "RC Lens": 826,
    "Lille": 1082,
    "LOSC Lille": 1082,
    "Nice": 417,
    "OGC Nice": 417,
    "Rennes": 273,
    "Stade Rennais": 273,
    "Strasbourg": 667,
    "RC Strasbourg": 667,
    "Nantes": 995,
    "FC Nantes": 995,
    "Toulouse": 415,
    "Montpellier": 969,
    "Le Havre": 738,
    "Brest": 3911,
    "Stade Brest": 3911,
    "Reims": 1421,
    "Stade de Reims": 1421,
    "Auxerre": 974,
    "Saint-Etienne": 618,
    "AS Saint-Etienne": 618,
    "Angers": 1079,
}

# League code -> list of (team_name, tm_id)
LEAGUE_TEAMS: dict[str, list[tuple[str, int]]] = {
    "PL": [
        ("Arsenal", 11), ("Aston Villa", 405), ("Bournemouth", 989),
        ("Brentford", 1148), ("Brighton", 1237), ("Chelsea", 631),
        ("Crystal Palace", 873), ("Everton", 29), ("Fulham", 931),
        ("Ipswich", 677), ("Leicester", 1003), ("Liverpool", 31),
        ("Man City", 281), ("Man United", 985), ("Newcastle", 762),
        ("Nottm Forest", 703), ("Southampton", 180), ("Tottenham", 148),
        ("West Ham", 379), ("Wolves", 543),
    ],
    "PD": [
        ("Real Madrid", 418), ("Barcelona", 131), ("Atletico Madrid", 13),
        ("Athletic Club", 621), ("Real Sociedad", 681), ("Real Betis", 150),
        ("Villarreal", 1050), ("Girona", 12321), ("Sevilla", 368),
        ("Valencia", 1049), ("Osasuna", 331), ("Celta Vigo", 940),
        ("Getafe", 3709), ("Rayo Vallecano", 367), ("Mallorca", 237),
        ("Las Palmas", 472), ("Alaves", 1108), ("Espanyol", 714),
        ("Leganes", 1244), ("Valladolid", 366),
    ],
    "BL1": [
        ("Bayern Munich", 27), ("Dortmund", 16), ("Leverkusen", 15),
        ("RB Leipzig", 23826), ("Frankfurt", 9), ("Stuttgart", 79),
        ("Wolfsburg", 82), ("Werder Bremen", 86), ("Hoffenheim", 533),
        ("Freiburg", 83), ("Augsburg", 167), ("Mainz", 39),
        ("Gladbach", 18), ("Union Berlin", 89), ("Bochum", 80),
        ("Holstein Kiel", 514), ("St. Pauli", 35), ("Heidenheim", 2756),
    ],
    "SA": [
        ("Inter Milan", 46), ("AC Milan", 5), ("Juventus", 506),
        ("Napoli", 6195), ("Atalanta", 800), ("Roma", 12),
        ("Lazio", 398), ("Fiorentina", 430), ("Bologna", 1025),
        ("Torino", 416), ("Udinese", 410), ("Genoa", 252),
        ("Cagliari", 419), ("Lecce", 394), ("Verona", 276),
        ("Venezia", 2409), ("Como", 201), ("Empoli", 749),
        ("Parma", 98), ("Monza", 5765),
    ],
    "FL1": [
        ("PSG", 583), ("Marseille", 244), ("Monaco", 162),
        ("Lyon", 1041), ("Lens", 826), ("Lille", 1082),
        ("Nice", 417), ("Rennes", 273), ("Strasbourg", 667),
        ("Nantes", 995), ("Toulouse", 415), ("Montpellier", 969),
        ("Le Havre", 738), ("Brest", 3911), ("Reims", 1421),
        ("Auxerre", 974), ("Saint-Etienne", 618), ("Angers", 1079),
    ],
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/webp,*/*;q=0.8"
    ),
    "Referer": "https://www.transfermarkt.com/",
}

_DELAY_BETWEEN_TEAMS = 3.0  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_accents(s: str) -> str:
    """Normalize unicode and remove combining characters."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _normalize_name(name: str) -> str:
    return _strip_accents(name).lower().strip()


def _parse_market_value(raw: str) -> int:
    """Parse Transfermarkt market value string to EUR integer.

    Examples: '€45.00m' -> 45_000_000, '€500k' -> 500_000, '-' -> 0
    """
    raw = raw.strip()
    if not raw or raw in ("-", "—", "?"):
        return 0
    # Remove euro sign and spaces
    raw = raw.replace("€", "").replace(",", "").strip()
    try:
        if raw.endswith("m"):
            return int(float(raw[:-1]) * 1_000_000)
        if raw.endswith("k"):
            return int(float(raw[:-1]) * 1_000)
        return int(float(raw))
    except (ValueError, TypeError):
        return 0


def _fetch_squad_page(tm_id: int) -> list[dict[str, Any]]:
    """Fetch and parse a Transfermarkt squad page.

    Returns list of dicts: {name, tm_id, market_value_eur}
    """
    import httpx

    url = f"https://www.transfermarkt.com/-/startseite/verein/{tm_id}"
    try:
        with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        print(f"[transfermarkt] Failed to fetch club {tm_id}: {e}")
        return []

    return _parse_squad_html(html)


def _parse_squad_html(html: str) -> list[dict[str, Any]]:
    """Extract player name, TM id, and market value from squad page HTML."""
    items_start = html.find('class="items"')
    if items_start < 0:
        return []

    chunk = html[items_start: items_start + 80_000]

    # Split on player rows (odd/even)
    rows = re.split(r'<tr class="(?:odd|even)">', chunk)[1:]

    players = []
    for row in rows:
        # Player name + TM player id
        name_m = re.search(
            r'href="/[^"]+/profil/spieler/(\d+)"\s*>\s*([^<]+?)\s*</a>',
            row,
        )
        # Market value cell (marktwertverlauf link)
        mv_m = re.search(
            r'href="/[^"]+/marktwertverlauf/spieler/\d+">([^<]+)</a>',
            row,
        )
        if not name_m:
            continue

        tm_player_id = int(name_m.group(1))
        name = name_m.group(2).strip()
        mv_raw = mv_m.group(1).strip() if mv_m else "-"
        market_value_eur = _parse_market_value(mv_raw)

        players.append({
            "name": name,
            "tm_id": tm_player_id,
            "market_value_eur": market_value_eur,
        })

    return players


def _match_player(
    conn: duckdb.DuckDBPyConnection,
    name: str,
    team_id: int | None,
) -> int | None:
    """Find player_id by name, trying exact then last-name match.

    Comparison uses lowercased, accent-stripped names.
    """
    norm = _normalize_name(name)

    # 1. Exact normalized match within team
    if team_id is not None:
        rows = conn.execute(
            "SELECT player_id, name FROM players WHERE team_id = ?",
            [team_id],
        ).fetchall()
        for pid, db_name in rows:
            if _normalize_name(db_name) == norm:
                return pid

    # 2. Exact normalized match across all players
    rows = conn.execute("SELECT player_id, name FROM players").fetchall()
    for pid, db_name in rows:
        if _normalize_name(db_name) == norm:
            return pid

    # 3. Last-name match within team
    last = norm.split()[-1] if norm.split() else norm
    if team_id is not None:
        rows = conn.execute(
            "SELECT player_id, name FROM players WHERE team_id = ?",
            [team_id],
        ).fetchall()
        for pid, db_name in rows:
            if _normalize_name(db_name).split()[-1] == last if _normalize_name(db_name).split() else False:
                return pid

    # 4. Last-name match across all players (only if team_id known)
    if team_id is not None:
        rows = conn.execute("SELECT player_id, name FROM players").fetchall()
        for pid, db_name in rows:
            parts = _normalize_name(db_name).split()
            if parts and parts[-1] == last:
                return pid

    return None


# ---------------------------------------------------------------------------
# Public sync functions
# ---------------------------------------------------------------------------

def sync_market_values(
    conn: duckdb.DuckDBPyConnection,
    league_code: str,
) -> dict[str, Any]:
    """Sync market values from Transfermarkt for all teams in a league.

    Args:
        conn: DuckDB connection.
        league_code: One of PL, PD, BL1, SA, FL1.

    Returns:
        dict with league_code, teams_processed, players_updated, players_not_found.
    """
    league_code = league_code.upper()
    teams = LEAGUE_TEAMS.get(league_code)
    if not teams:
        raise ValueError(
            f"Unsupported league: {league_code}. Supported: {list(LEAGUE_TEAMS.keys())}"
        )

    # Build team name -> team_id map from DB
    league_row = conn.execute(
        "SELECT league_id FROM leagues WHERE code = ? LIMIT 1", [league_code]
    ).fetchone()
    league_id = league_row[0] if league_row else None

    team_db_map: dict[str, int] = {}
    if league_id is not None:
        db_teams = conn.execute(
            "SELECT team_id, name, short_name FROM teams WHERE league_id = ?",
            [league_id],
        ).fetchall()
        for tid, tname, tshort in db_teams:
            team_db_map[_normalize_name(tname)] = tid
            team_db_map[_normalize_name(tshort)] = tid

    teams_processed = 0
    players_updated = 0
    players_not_found = 0

    for team_name, tm_id in teams:
        print(f"[transfermarkt] Fetching {team_name} (tm_id={tm_id})...")

        # Resolve DB team_id
        db_team_id: int | None = None
        tn_norm = _normalize_name(team_name)
        for key, tid in team_db_map.items():
            if key == tn_norm or tn_norm in key or key in tn_norm:
                db_team_id = tid
                break

        squad = _fetch_squad_page(tm_id)
        if not squad:
            print(f"[transfermarkt] {team_name}: no players returned")
            time.sleep(_DELAY_BETWEEN_TEAMS)
            continue

        team_updated = 0
        team_not_found = 0
        for player in squad:
            if player["market_value_eur"] == 0:
                continue
            try:
                pid = _match_player(conn, player["name"], db_team_id)
                if pid is not None:
                    conn.execute(
                        "UPDATE players SET market_value_eur = ?, updated_at = current_timestamp WHERE player_id = ?",
                        [player["market_value_eur"], pid],
                    )
                    team_updated += 1
                else:
                    team_not_found += 1
                    print(
                        f"[transfermarkt] No match: {player['name']} "
                        f"({team_name}, €{player['market_value_eur']:,})"
                    )
            except Exception as e:
                print(f"[transfermarkt] Error updating {player['name']}: {e}")

        print(
            f"[transfermarkt] {team_name}: {team_updated} updated, "
            f"{team_not_found} not found (of {len(squad)} scraped)"
        )
        players_updated += team_updated
        players_not_found += team_not_found
        teams_processed += 1

        time.sleep(_DELAY_BETWEEN_TEAMS)

    return {
        "league_code": league_code,
        "teams_processed": teams_processed,
        "players_updated": players_updated,
        "players_not_found": players_not_found,
    }


def sync_all_market_values(conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Sync market values for all 5 major leagues."""
    results: dict[str, Any] = {}
    for code in LEAGUE_TEAMS:
        try:
            results[code] = sync_market_values(conn, code)
        except Exception as e:
            results[code] = {"error": str(e)}
            print(f"[transfermarkt] {code} failed: {e}")
        time.sleep(5)
    return results
