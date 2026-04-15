"""Multi-league mock data generator for the Football Analytics Module.

Call ``seed_mock_data(conn)`` with a DuckDB connection to populate all tables
with statistically plausible data for PL, PD, BL1, SA, FL1, KL1.
Uses ``numpy.random.seed(42)`` for full reproducibility.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta
from typing import Any

import duckdb
import numpy as np

# ---------------------------------------------------------------------------
# League & Team definitions
# ---------------------------------------------------------------------------

LEAGUES_DATA: list[dict[str, Any]] = [
    {
        "league_id": 1, "code": "PL", "name": "Premier League", "country": "England", "season": "2025-26",
        "teams": [
            {"name": "Arsenal",           "short": "ARS", "strength": 0.88},
            {"name": "Manchester City",    "short": "MCI", "strength": 0.92},
            {"name": "Liverpool",          "short": "LIV", "strength": 0.87},
            {"name": "Chelsea",            "short": "CHE", "strength": 0.78},
            {"name": "Manchester United",  "short": "MUN", "strength": 0.72},
            {"name": "Tottenham Hotspur",  "short": "TOT", "strength": 0.74},
            {"name": "Newcastle United",   "short": "NEW", "strength": 0.76},
            {"name": "Aston Villa",        "short": "AVL", "strength": 0.75},
            {"name": "Brighton",           "short": "BHA", "strength": 0.70},
            {"name": "West Ham United",    "short": "WHU", "strength": 0.65},
            {"name": "Crystal Palace",     "short": "CRY", "strength": 0.60},
            {"name": "Brentford",          "short": "BRE", "strength": 0.62},
            {"name": "Fulham",             "short": "FUL", "strength": 0.63},
            {"name": "Wolverhampton",      "short": "WOL", "strength": 0.58},
            {"name": "Bournemouth",        "short": "BOU", "strength": 0.59},
            {"name": "Nottingham Forest",  "short": "NFO", "strength": 0.61},
            {"name": "Everton",            "short": "EVE", "strength": 0.55},
            {"name": "Leicester City",     "short": "LEI", "strength": 0.56},
            {"name": "Ipswich Town",       "short": "IPS", "strength": 0.42},
            {"name": "Southampton",        "short": "SOU", "strength": 0.40},
        ],
    },
    {
        "league_id": 2, "code": "PD", "name": "La Liga", "country": "Spain", "season": "2025-26",
        "teams": [
            {"name": "Real Madrid",        "short": "RMA", "strength": 0.93},
            {"name": "Barcelona",          "short": "BAR", "strength": 0.91},
            {"name": "Atletico Madrid",    "short": "ATM", "strength": 0.84},
            {"name": "Real Sociedad",      "short": "RSO", "strength": 0.74},
            {"name": "Athletic Bilbao",    "short": "ATH", "strength": 0.73},
            {"name": "Real Betis",         "short": "BET", "strength": 0.70},
            {"name": "Villarreal",         "short": "VIL", "strength": 0.72},
            {"name": "Sevilla",            "short": "SEV", "strength": 0.68},
            {"name": "Girona",             "short": "GIR", "strength": 0.67},
            {"name": "Valencia",           "short": "VAL", "strength": 0.62},
            {"name": "Osasuna",            "short": "OSA", "strength": 0.58},
            {"name": "Getafe",             "short": "GET", "strength": 0.55},
            {"name": "Celta Vigo",         "short": "CEL", "strength": 0.57},
            {"name": "Mallorca",           "short": "MLL", "strength": 0.54},
            {"name": "Las Palmas",         "short": "LPA", "strength": 0.50},
            {"name": "Rayo Vallecano",     "short": "RAY", "strength": 0.53},
            {"name": "Espanyol",           "short": "ESP", "strength": 0.48},
            {"name": "Alaves",             "short": "ALA", "strength": 0.46},
            {"name": "Leganes",            "short": "LEG", "strength": 0.44},
            {"name": "Real Valladolid",    "short": "VLL", "strength": 0.42},
        ],
    },
    {
        "league_id": 3, "code": "BL1", "name": "Bundesliga", "country": "Germany", "season": "2025-26",
        "teams": [
            {"name": "Bayern Munich",      "short": "BAY", "strength": 0.92},
            {"name": "Bayer Leverkusen",   "short": "LEV", "strength": 0.88},
            {"name": "Borussia Dortmund",  "short": "BVB", "strength": 0.82},
            {"name": "RB Leipzig",         "short": "RBL", "strength": 0.80},
            {"name": "VfB Stuttgart",      "short": "STU", "strength": 0.76},
            {"name": "Eintracht Frankfurt","short": "SGE", "strength": 0.73},
            {"name": "SC Freiburg",        "short": "SCF", "strength": 0.68},
            {"name": "VfL Wolfsburg",      "short": "WOB", "strength": 0.65},
            {"name": "Borussia Monchengladbach","short": "BMG", "strength": 0.62},
            {"name": "1. FC Union Berlin", "short": "FCU", "strength": 0.60},
            {"name": "TSG Hoffenheim",     "short": "HOF", "strength": 0.58},
            {"name": "FC Augsburg",        "short": "FCA", "strength": 0.53},
            {"name": "Werder Bremen",      "short": "SVW", "strength": 0.57},
            {"name": "1. FSV Mainz 05",    "short": "M05", "strength": 0.55},
            {"name": "VfL Bochum",         "short": "BOC", "strength": 0.45},
            {"name": "1. FC Heidenheim",   "short": "HDH", "strength": 0.48},
            {"name": "FC St. Pauli",       "short": "STP", "strength": 0.47},
            {"name": "Holstein Kiel",      "short": "KIE", "strength": 0.42},
        ],
    },
    {
        "league_id": 4, "code": "SA", "name": "Serie A", "country": "Italy", "season": "2025-26",
        "teams": [
            {"name": "Inter Milan",        "short": "INT", "strength": 0.90},
            {"name": "AC Milan",           "short": "ACM", "strength": 0.82},
            {"name": "Juventus",           "short": "JUV", "strength": 0.84},
            {"name": "Napoli",             "short": "NAP", "strength": 0.86},
            {"name": "AS Roma",            "short": "ROM", "strength": 0.76},
            {"name": "Atalanta",           "short": "ATA", "strength": 0.80},
            {"name": "Lazio",              "short": "LAZ", "strength": 0.74},
            {"name": "Fiorentina",         "short": "FIO", "strength": 0.72},
            {"name": "Bologna",            "short": "BOL", "strength": 0.70},
            {"name": "Torino",             "short": "TOR", "strength": 0.62},
            {"name": "Udinese",            "short": "UDI", "strength": 0.58},
            {"name": "Monza",              "short": "MON", "strength": 0.52},
            {"name": "Sassuolo",           "short": "SAS", "strength": 0.55},
            {"name": "Genoa",              "short": "GEN", "strength": 0.56},
            {"name": "Cagliari",           "short": "CAG", "strength": 0.50},
            {"name": "Empoli",             "short": "EMP", "strength": 0.48},
            {"name": "Lecce",              "short": "LEC", "strength": 0.46},
            {"name": "Hellas Verona",      "short": "VER", "strength": 0.47},
            {"name": "Frosinone",          "short": "FRO", "strength": 0.42},
            {"name": "Salernitana",        "short": "SAL", "strength": 0.40},
        ],
    },
    {
        "league_id": 5, "code": "FL1", "name": "Ligue 1", "country": "France", "season": "2025-26",
        "teams": [
            {"name": "Paris Saint-Germain","short": "PSG", "strength": 0.91},
            {"name": "Marseille",          "short": "OM",  "strength": 0.78},
            {"name": "Monaco",             "short": "MON", "strength": 0.76},
            {"name": "Lille",              "short": "LIL", "strength": 0.74},
            {"name": "Lyon",               "short": "OL",  "strength": 0.73},
            {"name": "Nice",               "short": "NIC", "strength": 0.68},
            {"name": "Lens",               "short": "LEN", "strength": 0.67},
            {"name": "Rennes",             "short": "REN", "strength": 0.65},
            {"name": "Strasbourg",         "short": "STR", "strength": 0.58},
            {"name": "Toulouse",           "short": "TFC", "strength": 0.57},
            {"name": "Montpellier",        "short": "MTP", "strength": 0.53},
            {"name": "Reims",              "short": "REI", "strength": 0.52},
            {"name": "Nantes",             "short": "NAN", "strength": 0.54},
            {"name": "Brest",              "short": "BRS", "strength": 0.60},
            {"name": "Le Havre",           "short": "HAV", "strength": 0.46},
            {"name": "Auxerre",            "short": "AUX", "strength": 0.45},
            {"name": "Angers",             "short": "ANG", "strength": 0.44},
            {"name": "Saint-Etienne",      "short": "STE", "strength": 0.48},
        ],
    },
    {
        "league_id": 6, "code": "KL1", "name": "K League 1", "country": "South Korea", "season": "2025",
        "teams": [
            {"name": "울산 HD",            "short": "ULS", "strength": 0.88},
            {"name": "전북 현대",          "short": "JBH", "strength": 0.82},
            {"name": "포항 스틸러스",      "short": "POH", "strength": 0.76},
            {"name": "FC 서울",            "short": "SEO", "strength": 0.74},
            {"name": "수원 FC",            "short": "SWF", "strength": 0.65},
            {"name": "인천 유나이티드",    "short": "ICN", "strength": 0.64},
            {"name": "제주 유나이티드",    "short": "JEJ", "strength": 0.60},
            {"name": "대구 FC",            "short": "DAE", "strength": 0.58},
            {"name": "대전 하나 시티즌",   "short": "DAJ", "strength": 0.56},
            {"name": "강원 FC",            "short": "GAN", "strength": 0.55},
            {"name": "광주 FC",            "short": "GWJ", "strength": 0.53},
            {"name": "김천 상무",          "short": "KIM", "strength": 0.50},
        ],
    },
]

# ---------------------------------------------------------------------------
# Name pools per nationality
# ---------------------------------------------------------------------------

_NAMES: dict[str, tuple[list[str], list[str]]] = {
    "England": (
        ["James","John","Harry","Oliver","Ethan","Mason","Jack","Leo","Owen","Ben","Tom","Will","Jake","Dan","Matt","Chris","Ryan","Kyle","Aaron","Declan","Jordan","Bukayo","Callum","Dominic","Cole","Jude"],
        ["Smith","Jones","Williams","Taylor","Brown","Wilson","White","Hall","Walker","Allen","Young","Wood","Cooper","Ward","Turner","Collins","Morris","Bell","Price","Bennett"],
    ),
    "Spain": (
        ["Alvaro","Pablo","Marco","Carlos","Sergio","Luis","Diego","Alejandro","Daniel","Iker","Pedri","Gavi","Nico","Ferran","Ansu","Dani","Rodri","Mikel","Lamine","Pau"],
        ["Garcia","Martinez","Lopez","Gonzalez","Rodriguez","Hernandez","Perez","Sanchez","Torres","Ramirez","Fernandez","Ruiz","Jimenez","Moreno","Diaz","Alvarez","Romero","Navarro","Molina","Ortiz"],
    ),
    "Germany": (
        ["Florian","Kai","Leon","Jamal","Joshua","Niklas","Leroy","Serge","Robin","Timo","Thomas","Julian","Ilkay","Lars","Lukas","Marc","Nico","Jonas","Maximilian","Emre"],
        ["Muller","Schmidt","Schneider","Fischer","Weber","Meyer","Wagner","Becker","Hoffmann","Schulz","Koch","Richter","Klein","Wolf","Neumann","Schwarz","Braun","Krause","Werner","Lehmann"],
    ),
    "Italy": (
        ["Federico","Lorenzo","Alessandro","Marco","Nicolo","Sandro","Andrea","Matteo","Giacomo","Luca","Gianluca","Riccardo","Davide","Gianluigi","Ciro","Roberto","Giovanni","Stefano","Simone","Pietro"],
        ["Rossi","Russo","Ferrari","Esposito","Bianchi","Romano","Colombo","Ricci","Marino","Greco","Bruno","Gallo","Conti","Costa","Giordano","Mancini","Barbieri","Leone","Lombardi","Moretti"],
    ),
    "France": (
        ["Kylian","Ousmane","Antoine","Aurelien","Eduardo","Randal","Theo","Jules","William","Marcus","Olivier","Hugo","Adrien","Youssouf","Moussa","Ibrahima","Dayot","Raphael","Matteo","Rayan"],
        ["Martin","Bernard","Dubois","Thomas","Robert","Richard","Petit","Durand","Leroy","Moreau","Simon","Laurent","Lefebvre","Michel","Garcia","Roux","Fontaine","Boyer","Girard","Bonnet"],
    ),
    "South Korea": (
        ["민재","영권","승호","진수","인범","기훈","상호","동건","주영","태욱","성민","현우","재성","도현","우진","건희","상민","정우","준서","시우"],
        ["김","이","박","최","정","강","조","윤","장","임","한","오","서","신","권","황","안","송","류","전"],
    ),
}

def _rng_name(rng: np.random.Generator, country: str, used: set[str]) -> str:
    firsts, lasts = _NAMES.get(country, _NAMES["England"])
    for _ in range(300):
        if country == "South Korea":
            name = f"{rng.choice(lasts)}{rng.choice(firsts)}"
        else:
            name = f"{rng.choice(firsts)} {rng.choice(lasts)}"
        if name not in used:
            used.add(name)
            return name
    name = f"{rng.choice(firsts)} {rng.choice(lasts)} {len(used)}"
    used.add(name)
    return name


# ---------------------------------------------------------------------------
# Main seeding function
# ---------------------------------------------------------------------------

def seed_mock_data(conn: duckdb.DuckDBPyConnection) -> None:
    """Populate all tables with multi-league mock data. Safe to call repeatedly."""
    rng = np.random.default_rng(42)
    random.seed(42)

    # Clear all tables
    for tbl in [
        "fpl_gameweek_history", "fpl_fixtures", "fpl_players",
        "player_season_stats", "shots", "match_predictions",
        "player_embeddings", "fpl_projections", "collector_runs",
        "matches", "players", "teams", "leagues",
    ]:
        try:
            conn.execute(f"DELETE FROM {tbl}")
        except Exception:
            pass

    all_teams: list[dict[str, Any]] = []
    all_players: list[dict[str, Any]] = []
    all_matches: list[dict[str, Any]] = []
    strength_map: dict[int, float] = {}

    team_id_counter = 1
    player_id_counter = 1
    match_id_counter = 1
    used_names: set[str] = set()

    for league in LEAGUES_DATA:
        lid = league["league_id"]
        code = league["code"]
        season = league["season"]
        country = league["country"]

        # Insert league
        conn.execute(
            "INSERT INTO leagues VALUES (?, ?, ?, ?, ?)",
            [lid, code, league["name"], country, season],
        )

        league_teams = league["teams"]
        league_team_ids: list[int] = []

        # --- Teams ---
        for t in league_teams:
            tid = team_id_counter
            team_id_counter += 1
            league_team_ids.append(tid)
            strength_map[tid] = t["strength"]
            all_teams.append({
                "team_id": tid, "name": t["name"], "short": t["short"],
                "strength": t["strength"], "league_id": lid,
            })
            conn.execute(
                "INSERT INTO teams VALUES (?, ?, ?, ?, ?)",
                [tid, t["name"], t["short"], None, lid],
            )

        # --- Players ---
        n_teams = len(league_teams)
        squad_size = 25 if n_teams == 20 else (22 if n_teams == 18 else 20)

        for team_info in all_teams[-n_teams:]:
            tid = team_info["team_id"]
            str_ = team_info["strength"]
            positions = (
                ["GK"] * 2
                + ["DEF"] * (squad_size * 7 // 25)
                + ["MID"] * (squad_size * 8 // 25)
                + ["FWD"] * (squad_size * 5 // 25)
            )
            # Fill remaining
            while len(positions) < squad_size:
                positions.append(str(rng.choice(["DEF", "MID", "FWD"])))

            for pos in positions:
                name = _rng_name(rng, country, used_names)
                dob = date(int(rng.integers(1990, 2005)), int(rng.integers(1, 13)), int(rng.integers(1, 28)))
                base_val = str_ * 35_000_000
                mv = int(rng.lognormal(np.log(base_val), 0.6))
                mv = max(300_000, min(mv, 150_000_000))

                p = {
                    "player_id": player_id_counter,
                    "name": name, "dob": dob, "nationality": country,
                    "position": pos, "team_id": tid,
                    "market_value_eur": mv,
                    "contract_until": date(int(rng.integers(2026, 2030)), 6, 30),
                    "fpl_id": player_id_counter if code == "PL" else None,
                    "team_strength": str_,
                    "league_code": code,
                }
                all_players.append(p)
                conn.execute(
                    """INSERT INTO players
                       (player_id, name, date_of_birth, nationality, position,
                        team_id, market_value_eur, contract_until, fpl_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [player_id_counter, name, dob, country, pos, tid, mv,
                     p["contract_until"], p["fpl_id"]],
                )
                player_id_counter += 1

        # --- Matches ---
        pairs: list[tuple[int, int]] = []
        for i, h in enumerate(league_team_ids):
            for a in league_team_ids[i + 1:]:
                pairs.append((h, a))
                pairs.append((a, h))
        rng.shuffle(pairs)

        n_matchdays = len(pairs) // (n_teams // 2)
        matches_per_day = n_teams // 2
        matchdays_list = [pairs[i * matches_per_day: (i + 1) * matches_per_day] for i in range(n_matchdays)]

        if code == "KL1":
            season_start = datetime(2025, 2, 22)
            finished_mds = 8
        else:
            season_start = datetime(2025, 8, 16)
            finished_mds = 28 if n_matchdays >= 34 else int(n_matchdays * 0.75)

        for md_idx, md_pairs in enumerate(matchdays_list):
            matchday = md_idx + 1
            base_date = season_start + timedelta(weeks=md_idx)
            finished = matchday <= finished_mds

            for home_id, away_id in md_pairs:
                kickoff = base_date + timedelta(hours=int(rng.integers(0, 48)))

                if finished:
                    hs, as_, hxg, axg = _simulate_match(home_id, away_id, strength_map, rng)
                    status = "FINISHED"
                else:
                    hs = as_ = hxg = axg = None
                    status = "SCHEDULED"

                m = {
                    "match_id": match_id_counter, "league_id": lid,
                    "season": season, "matchday": matchday,
                    "kickoff": kickoff, "status": status,
                    "home_team_id": home_id, "away_team_id": away_id,
                    "home_score": hs, "away_score": as_,
                    "home_xg": hxg, "away_xg": axg,
                }
                all_matches.append(m)
                conn.execute(
                    """INSERT INTO matches
                       (match_id, league_id, season, matchday, kickoff, status,
                        home_team_id, away_team_id, home_score, away_score,
                        home_xg, away_xg)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [match_id_counter, lid, season, matchday, kickoff, status,
                     home_id, away_id, hs, as_, hxg, axg],
                )
                match_id_counter += 1

    # --- Shots (all leagues) ---
    _seed_shots(conn, rng, all_matches, all_players, strength_map)

    # --- Player season stats (all leagues) ---
    _seed_player_season_stats(conn, rng, all_players, all_matches)

    # --- FPL data (PL only) ---
    pl_players = [p for p in all_players if p["league_code"] == "PL"]
    pl_teams = [t for t in all_teams if t["league_id"] == 1]
    fpl_players = _seed_fpl_players(conn, rng, pl_players, pl_teams)
    _seed_fpl_fixtures(conn, rng, pl_teams, strength_map)
    _seed_fpl_gameweek_history(conn, rng, fpl_players)

    print(f"[mock_data] Seeded {len(LEAGUES_DATA)} leagues, {len(all_teams)} teams, "
          f"{len(all_players)} players, {len(all_matches)} matches.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simulate_match(
    home_id: int, away_id: int,
    strength_map: dict[int, float],
    rng: np.random.Generator,
) -> tuple[int, int, float, float]:
    h_str = strength_map[home_id]
    a_str = strength_map[away_id]
    home_adv = 0.08
    h_lambda = max(0.3, (h_str - a_str * 0.7 + home_adv) * 2.2)
    a_lambda = max(0.3, (a_str - h_str * 0.7) * 1.8)
    h_xg = float(rng.gamma(h_lambda, 0.55))
    a_xg = float(rng.gamma(a_lambda, 0.55))
    h_score = int(rng.poisson(h_xg))
    a_score = int(rng.poisson(a_xg))
    return h_score, a_score, round(h_xg, 3), round(a_xg, 3)


def _seed_shots(
    conn: duckdb.DuckDBPyConnection,
    rng: np.random.Generator,
    matches: list[dict[str, Any]],
    players: list[dict[str, Any]],
    strength_map: dict[int, float],
) -> None:
    team_players: dict[int, list[dict[str, Any]]] = {}
    for p in players:
        if p["position"] != "GK":
            team_players.setdefault(p["team_id"], []).append(p)

    situations = ["OpenPlay", "SetPiece", "FromCorner", "DirectFreekick", "Penalty"]
    sit_w = [0.60, 0.15, 0.12, 0.08, 0.05]
    shot_types = ["RightFoot", "LeftFoot", "Head"]
    stype_w = [0.55, 0.30, 0.15]
    results = ["Goal", "SavedShot", "MissedShots", "BlockedShot", "ShotOnPost"]
    result_w_base = [0.10, 0.33, 0.35, 0.18, 0.04]
    shot_counter = 0
    batch: list[tuple] = []

    for m in matches:
        if m["status"] != "FINISHED":
            continue
        h_xg = m["home_xg"] or 1.0
        a_xg = m["away_xg"] or 1.0
        h_shots = max(3, int(rng.normal(h_xg / 0.12, 2)))
        a_shots = max(3, int(rng.normal(a_xg / 0.12, 2)))

        for team_id, n_shots, team_xg in [
            (m["home_team_id"], h_shots, h_xg),
            (m["away_team_id"], a_shots, a_xg),
        ]:
            tp = team_players.get(team_id, [])
            if not tp:
                continue
            weights = np.array([3.0 if p["position"] == "FWD" else 1.5 if p["position"] == "MID" else 0.5 for p in tp])
            weights /= weights.sum()
            per_shot_xg = team_xg / max(n_shots, 1)

            for _ in range(n_shots):
                shot_counter += 1
                shooter = tp[int(rng.choice(len(tp), p=weights))]
                minute = int(rng.integers(1, 95))
                x = float(rng.uniform(70, 105))
                y = float(rng.uniform(15, 65))
                xg_val = float(np.clip(rng.normal(per_shot_xg, per_shot_xg * 0.5), 0.01, 0.95))
                situation = str(rng.choice(situations, p=sit_w))
                stype = str(rng.choice(shot_types, p=stype_w))
                rw = list(result_w_base)
                rw[0] = min(0.50, xg_val)
                total = sum(rw)
                rw = [w / total for w in rw]
                result = str(rng.choice(results, p=rw))
                shot_id = hashlib.md5(f"{m['match_id']}_{shooter['player_id']}_{shot_counter}".encode()).hexdigest()
                batch.append((
                    shot_id, m["match_id"], shooter["player_id"], team_id,
                    minute, x, y, round(xg_val, 4), result, situation, stype, m["season"],
                ))

    conn.executemany(
        """INSERT INTO shots (shot_id, match_id, player_id, team_id, minute, x, y, xg,
           result, situation, shot_type, season) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        batch,
    )


def _seed_player_season_stats(
    conn: duckdb.DuckDBPyConnection,
    rng: np.random.Generator,
    players: list[dict[str, Any]],
    matches: list[dict[str, Any]],
) -> None:
    finished = [m for m in matches if m["status"] == "FINISHED"]
    team_match_count: dict[int, int] = {}
    for m in finished:
        team_match_count[m["home_team_id"]] = team_match_count.get(m["home_team_id"], 0) + 1
        team_match_count[m["away_team_id"]] = team_match_count.get(m["away_team_id"], 0) + 1

    rows: list[tuple] = []
    for p in players:
        pos = p["position"]
        str_ = p["team_strength"]
        code = p["league_code"]
        season = [lg["season"] for lg in LEAGUES_DATA if lg["code"] == code][0]
        team_matches = team_match_count.get(p["team_id"], 15)

        if pos == "GK":
            mp = int(rng.integers(max(1, team_matches - 5), team_matches + 1))
            mins = mp * int(rng.integers(87, 95))
        else:
            mp = int(rng.integers(max(3, team_matches - 12), team_matches + 1))
            mins = mp * int(rng.integers(55, 90))
        mins = max(90, mins)
        per_90 = mins / 90.0

        if pos == "GK":
            xg_p90, xa_p90, shots_p90 = 0.0, 0.0, 0.0
            kp, pc, pp = float(rng.uniform(0.1, 0.5)), float(rng.uniform(0, 0.3)), float(rng.uniform(1, 3))
            tk, it, ae, dr = float(rng.uniform(0, 0.3)), float(rng.uniform(0, 0.3)), float(rng.uniform(0.5, 2.5)), 0.0
            pass_pct = float(rng.uniform(60, 80))
        elif pos == "DEF":
            xg_p90 = float(rng.gamma(0.3 + str_ * 0.1, 0.05))
            xa_p90 = float(rng.gamma(0.2 + str_ * 0.08, 0.04))
            shots_p90 = float(rng.gamma(0.8, 0.3))
            kp, pc, pp = float(rng.uniform(0.3, 1.2)), float(rng.uniform(1, 4)), float(rng.uniform(2, 6))
            tk, it, ae, dr = float(rng.uniform(1.5, 4.5)), float(rng.uniform(1, 3.5)), float(rng.uniform(1, 4.5)), float(rng.uniform(0.3, 1.5))
            pass_pct = float(rng.uniform(72, 90))
        elif pos == "MID":
            xg_p90 = float(rng.gamma(0.5 + str_ * 0.15, 0.08))
            xa_p90 = float(rng.gamma(0.4 + str_ * 0.15, 0.07))
            shots_p90 = float(rng.gamma(1.5, 0.5))
            kp, pc, pp = float(rng.uniform(1, 3.5)), float(rng.uniform(2, 8)), float(rng.uniform(4, 10))
            tk, it, ae, dr = float(rng.uniform(1, 3.5)), float(rng.uniform(0.8, 2.5)), float(rng.uniform(0.3, 2)), float(rng.uniform(0.5, 3.5))
            pass_pct = float(rng.uniform(78, 92))
        else:
            xg_p90 = float(rng.gamma(0.8 + str_ * 0.25, 0.12))
            xa_p90 = float(rng.gamma(0.3 + str_ * 0.1, 0.06))
            shots_p90 = float(rng.gamma(2.5, 0.7))
            kp, pc, pp = float(rng.uniform(0.5, 2.5)), float(rng.uniform(2, 7)), float(rng.uniform(1.5, 5))
            tk, it, ae, dr = float(rng.uniform(0.3, 1.5)), float(rng.uniform(0.2, 1)), float(rng.uniform(0.5, 3.5)), float(rng.uniform(1, 5))
            pass_pct = float(rng.uniform(68, 85))

        xg_tot = xg_p90 * per_90
        xa_tot = xa_p90 * per_90
        goals = int(rng.poisson(max(0.01, xg_tot)))
        assists = int(rng.poisson(max(0.01, xa_tot)))

        rows.append((
            p["player_id"], season, code, mins, mp, goals, assists,
            round(xg_tot, 3), round(xa_tot, 3), round(xg_p90, 4), round(xa_p90, 4),
            round(shots_p90, 3), round(kp, 3), round(pc, 3), round(pp, 3),
            round(tk, 3), round(it, 3), round(ae, 3), round(dr, 3), round(pass_pct, 2),
        ))

    conn.executemany(
        """INSERT INTO player_season_stats
           (player_id, season, league_code, minutes_played, matches_played,
            goals, assists, xg, xa, xg_per_90, xa_per_90, shots_per_90,
            key_passes_per_90, progressive_carries_per_90, progressive_passes_per_90,
            tackles_per_90, interceptions_per_90, aerials_won_per_90, dribbles_per_90,
            pass_completion_pct)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )


def _seed_fpl_players(
    conn: duckdb.DuckDBPyConnection,
    rng: np.random.Generator,
    pl_players: list[dict[str, Any]],
    pl_teams: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fpl_pos_map = {"GK": "GKP", "DEF": "DEF", "MID": "MID", "FWD": "FWD"}
    team_name_map = {t["team_id"]: t["name"] for t in pl_teams}
    records: list[dict[str, Any]] = []

    for p in pl_players:
        str_ = p["team_strength"]
        fpl_pos = fpl_pos_map[p["position"]]
        price_ranges = {"GKP": (4.5, 5.5 + str_ * 1.5), "DEF": (4.0, 5.0 + str_ * 3.5), "MID": (4.5, 6.0 + str_ * 9.0), "FWD": (4.5, 6.0 + str_ * 10.5)}
        lo, hi = price_ranges[fpl_pos]
        price = round(float(rng.uniform(lo, hi)) * 2) / 2
        base_pts = {"GKP": 80 + str_ * 60, "DEF": 60 + str_ * 80, "MID": 60 + str_ * 140, "FWD": 60 + str_ * 150}[fpl_pos]
        total_points = max(10, int(rng.normal(base_pts, base_pts * 0.25)))
        minutes = int(rng.uniform(400, 2400))
        ppg = round(total_points / max(1, minutes / 90), 2)
        form = min(12.0, round(float(rng.uniform(1.0, 10.0) * str_), 1))
        selected_pct = min(60.0, round(float(rng.exponential(str_ * 8.0)), 1))
        goals = int(rng.poisson({"GKP": 0.02, "DEF": 0.5 + str_, "MID": 1.5 + str_ * 3, "FWD": 3 + str_ * 8}[fpl_pos]))
        assists = int(rng.poisson({"GKP": 0.01, "DEF": 0.3 + str_ * 0.5, "MID": 1 + str_ * 3, "FWD": 1 + str_ * 2}[fpl_pos]))
        cs = int(rng.poisson(str_ * 6 if fpl_pos in ("GKP", "DEF") else str_ * 2))
        bonus = int(rng.poisson(str_ * 10))
        infl = round(float(rng.normal(str_ * 600, 150)), 1)
        crea = round(float(rng.normal(str_ * 500, 130)), 1)
        thr = round(float(rng.normal(str_ * 700 if fpl_pos == "FWD" else str_ * 400, 180)), 1)
        ict = round((infl + crea + thr) / 300, 1)
        inj_roll = rng.random()
        inj_status = "Doubtful" if inj_roll > 0.95 else ("Unavailable" if inj_roll > 0.97 else "Available")
        inj_note = "Knock" if inj_status == "Doubtful" else ("Muscle injury" if inj_status == "Unavailable" else None)

        rec = {
            "fpl_id": p["player_id"], "player_id": p["player_id"],
            "web_name": p["name"].split()[-1], "position": fpl_pos,
            "team_code": p["team_id"], "team_name": team_name_map.get(p["team_id"], ""),
            "price": price, "total_points": total_points, "form": form,
            "points_per_game": ppg, "selected_by_pct": selected_pct,
            "minutes": minutes, "goals_scored": goals, "assists": assists,
            "clean_sheets": cs, "bonus": bonus, "influence": infl,
            "creativity": crea, "threat": thr, "ict_index": ict,
            "injury_status": inj_status, "injury_note": inj_note,
        }
        records.append(rec)

    conn.executemany(
        """INSERT INTO fpl_players
           (fpl_id, player_id, web_name, position, team_code, team_name,
            price, total_points, form, points_per_game, selected_by_pct,
            minutes, goals_scored, assists, clean_sheets, bonus,
            influence, creativity, threat, ict_index, injury_status, injury_note)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [(r["fpl_id"], r["player_id"], r["web_name"], r["position"],
          r["team_code"], r["team_name"], r["price"], r["total_points"],
          r["form"], r["points_per_game"], r["selected_by_pct"],
          r["minutes"], r["goals_scored"], r["assists"], r["clean_sheets"],
          r["bonus"], r["influence"], r["creativity"], r["threat"],
          r["ict_index"], r["injury_status"], r["injury_note"]) for r in records],
    )
    return records


def _seed_fpl_fixtures(
    conn: duckdb.DuckDBPyConnection,
    rng: np.random.Generator,
    pl_teams: list[dict[str, Any]],
    strength_map: dict[int, float],
) -> None:
    team_ids = [t["team_id"] for t in pl_teams]

    def _fdr(opp_id: int) -> int:
        s = strength_map.get(opp_id, 0.5)
        if s >= 0.85: return 5
        if s >= 0.75: return 4
        if s >= 0.65: return 3
        if s >= 0.55: return 2
        return 1

    pairs: list[tuple[int, int]] = []
    for i, h in enumerate(team_ids):
        for a in team_ids[i + 1:]:
            pairs.append((h, a))
            pairs.append((a, h))
    rng.shuffle(pairs)
    matchdays = [pairs[i * 10: (i + 1) * 10] for i in range(38)]

    season_start = datetime(2025, 8, 16)
    fid = 1
    rows: list[tuple] = []
    for md_idx, md_pairs in enumerate(matchdays):
        gw = md_idx + 1
        base_date = season_start + timedelta(weeks=md_idx)
        finished = gw <= 28
        for hc, ac in md_pairs:
            kickoff = base_date + timedelta(hours=int(rng.integers(0, 48)))
            rows.append((fid, gw, kickoff, hc, ac, _fdr(ac), _fdr(hc), finished))
            fid += 1

    conn.executemany(
        """INSERT INTO fpl_fixtures
           (fixture_id, gameweek, kickoff, home_team_code, away_team_code,
            home_difficulty, away_difficulty, finished)
           VALUES (?,?,?,?,?,?,?,?)""",
        rows,
    )


def _seed_fpl_gameweek_history(
    conn: duckdb.DuckDBPyConnection,
    rng: np.random.Generator,
    fpl_players: list[dict[str, Any]],
) -> None:
    n_gws = 28
    rows: list[tuple] = []
    for p in fpl_players:
        fid = p["fpl_id"]
        avg_pts = p["total_points"] / n_gws
        price = p["price"]
        for gw in range(1, n_gws + 1):
            if rng.random() < 0.15:
                mins, pts, goals, assists, bonus, bps = 0, 1, 0, 0, 0, 0
            else:
                mins = int(rng.choice([45, 60, 75, 90], p=[0.10, 0.15, 0.25, 0.50]))
                pts = max(1, int(rng.normal(avg_pts, avg_pts * 0.55)))
                goals = int(rng.poisson(p.get("goals_scored", 0) / n_gws))
                assists = int(rng.poisson(p.get("assists", 0) / n_gws))
                bonus = int(rng.choice([0, 1, 2, 3], p=[0.65, 0.20, 0.10, 0.05]))
                bps = int(rng.integers(0, 50))
            drift = float(rng.normal(0, 0.1))
            gw_price = round(max(3.5, price + drift * (gw / 38)), 1)
            sel = round(max(0.1, p["selected_by_pct"] + float(rng.normal(0, 0.5))), 1)
            rows.append((fid, gw, pts, mins, goals, assists, bonus, bps, gw_price, sel))

    conn.executemany(
        """INSERT INTO fpl_gameweek_history
           (fpl_id, gameweek, points, minutes, goals, assists, bonus, bps, price, selected_by_pct)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
