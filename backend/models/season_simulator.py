"""Monte Carlo season simulator for league title & CL/EL/ECL winner prediction.

Improvements over v1:
- Poisson goal simulation for realistic scorelines
- Elo-based fallback when XGBoost predictions are unavailable
- CL knockout bracket auto-generation from league stage standings
- Europa League & Conference League simulation support
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from typing import Any

import duckdb
import numpy as np


# ---------------------------------------------------------------------------
# Elo Rating System
# ---------------------------------------------------------------------------

# Default Elo for teams without historical data
DEFAULT_ELO = 1500.0
ELO_K_FACTOR = 20.0
ELO_HOME_ADVANTAGE = 65.0


def _compute_elo_ratings(
    conn: duckdb.DuckDBPyConnection, league: str, season: str
) -> dict[int, float]:
    """Compute Elo ratings for all teams based on finished matches this season."""
    rows = conn.execute(
        """
        SELECT m.home_team_id, m.away_team_id, m.home_score, m.away_score
        FROM matches m
        JOIN leagues l ON l.league_id = m.league_id
        WHERE m.status = 'FINISHED' AND l.code = ? AND m.season = ?
        ORDER BY m.kickoff ASC
        """,
        [league, season],
    ).fetchall()

    elo: dict[int, float] = defaultdict(lambda: DEFAULT_ELO)

    for home_id, away_id, home_score, away_score in rows:
        # Expected scores
        r_home = elo[home_id] + ELO_HOME_ADVANTAGE
        r_away = elo[away_id]
        exp_home = 1.0 / (1.0 + 10 ** ((r_away - r_home) / 400.0))
        exp_away = 1.0 - exp_home

        # Actual scores
        if home_score > away_score:
            s_home, s_away = 1.0, 0.0
        elif home_score == away_score:
            s_home, s_away = 0.5, 0.5
        else:
            s_home, s_away = 0.0, 1.0

        # Goal difference multiplier (larger wins → bigger Elo change)
        gd = abs(home_score - away_score)
        gd_mult = math.log(max(gd, 1) + 1)

        elo[home_id] += ELO_K_FACTOR * gd_mult * (s_home - exp_home)
        elo[away_id] += ELO_K_FACTOR * gd_mult * (s_away - exp_away)

    return dict(elo)


def _elo_to_probabilities(
    elo_home: float, elo_away: float
) -> tuple[float, float, float]:
    """Convert Elo ratings to (home_win, draw, away_win) probabilities."""
    dr = (elo_home + ELO_HOME_ADVANTAGE) - elo_away
    exp_home = 1.0 / (1.0 + 10 ** (-dr / 400.0))
    exp_away = 1.0 - exp_home

    # Model draw probability based on closeness of teams
    # Closer teams → higher draw probability (max ~30%)
    draw_base = 0.26 * math.exp(-(dr ** 2) / (2 * 200 ** 2))
    draw_prob = max(0.15, min(0.32, draw_base + 0.10))

    # Distribute remaining probability
    remaining = 1.0 - draw_prob
    home_prob = remaining * exp_home
    away_prob = remaining * exp_away

    return (home_prob, draw_prob, away_prob)


def _elo_to_expected_goals(
    elo_home: float, elo_away: float
) -> tuple[float, float]:
    """Convert Elo ratings to expected goals for Poisson simulation."""
    # Base expected goals (league average ~1.4 per team per match)
    base_goals = 1.35
    dr = (elo_home + ELO_HOME_ADVANTAGE) - elo_away

    # Elo difference affects expected goals (sigmoid-like scaling)
    home_factor = 1.0 + 0.4 * math.tanh(dr / 400.0)
    away_factor = 1.0 - 0.4 * math.tanh(dr / 400.0)

    home_xg = base_goals * home_factor
    away_xg = base_goals * away_factor

    # Clamp to reasonable range
    home_xg = max(0.4, min(3.5, home_xg))
    away_xg = max(0.3, min(3.0, away_xg))

    return (home_xg, away_xg)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_current_standings(
    conn: duckdb.DuckDBPyConnection, league: str, season: str
) -> list[dict[str, Any]]:
    """Return current league standings computed from finished matches."""
    rows = conn.execute(
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
        WHERE m.status = 'FINISHED' AND l.code = ? AND m.season = ?
        GROUP BY t.team_id, t.name, t.short_name
        """,
        [league, season],
    ).fetchall()

    standings: list[dict[str, Any]] = []
    for r in rows:
        pts = r[4] * 3 + r[5]
        standings.append({
            "team_id": r[0],
            "name": r[1],
            "short_name": r[2],
            "played": r[3],
            "wins": r[4],
            "draws": r[5],
            "losses": r[6],
            "goals_for": r[7],
            "goals_against": r[8],
            "points": pts,
            "goal_difference": r[7] - r[8],
        })
    standings.sort(key=lambda s: (-s["points"], -s["goal_difference"], -s["goals_for"]))
    return standings


def _get_remaining_fixtures(
    conn: duckdb.DuckDBPyConnection, league: str, season: str
) -> list[dict[str, Any]]:
    """Return fixtures not yet played (SCHEDULED)."""
    rows = conn.execute(
        """
        SELECT m.match_id, m.home_team_id, m.away_team_id,
               ht.name AS home_name, awt.name AS away_name,
               ht.short_name AS home_short, awt.short_name AS away_short
        FROM matches m
        JOIN leagues l ON l.league_id = m.league_id
        JOIN teams ht ON ht.team_id = m.home_team_id
        JOIN teams awt ON awt.team_id = m.away_team_id
        WHERE m.status = 'SCHEDULED' AND l.code = ? AND m.season = ?
        ORDER BY m.kickoff ASC
        """,
        [league, season],
    ).fetchall()
    return [
        {
            "match_id": r[0],
            "home_team_id": r[1],
            "away_team_id": r[2],
            "home_name": r[3],
            "away_name": r[4],
            "home_short": r[5],
            "away_short": r[6],
        }
        for r in rows
    ]


def _get_match_probabilities(
    conn: duckdb.DuckDBPyConnection, match_id: int,
    elo_ratings: dict[int, float] | None = None,
    home_team_id: int | None = None,
    away_team_id: int | None = None,
) -> tuple[float, float, float]:
    """Get cached prediction probabilities, Elo fallback, or heuristic."""
    # 1. Try cached XGBoost prediction
    row = conn.execute(
        """
        SELECT prob_home_win, prob_draw, prob_away_win
        FROM match_predictions
        WHERE match_id = ?
        ORDER BY model_version DESC
        LIMIT 1
        """,
        [match_id],
    ).fetchone()

    if row and row[0] is not None:
        return (float(row[0]), float(row[1]), float(row[2]))

    # 2. Try live XGBoost prediction
    try:
        from backend.models.match_predictor import predict
        result = predict(match_id, conn)
        if "error" not in result:
            p = result["probabilities"]
            return (p["home_win"], p["draw"], p["away_win"])
    except Exception:
        pass

    # 3. Elo-based fallback (NEW - much better than fixed heuristic)
    if elo_ratings and home_team_id and away_team_id:
        elo_h = elo_ratings.get(home_team_id, DEFAULT_ELO)
        elo_a = elo_ratings.get(away_team_id, DEFAULT_ELO)
        return _elo_to_probabilities(elo_h, elo_a)

    # 4. Last resort: generic home advantage heuristic
    return (0.45, 0.27, 0.28)


def _get_expected_goals(
    elo_ratings: dict[int, float] | None,
    home_team_id: int,
    away_team_id: int,
) -> tuple[float, float]:
    """Get expected goals for Poisson simulation based on Elo."""
    if elo_ratings:
        elo_h = elo_ratings.get(home_team_id, DEFAULT_ELO)
        elo_a = elo_ratings.get(away_team_id, DEFAULT_ELO)
        return _elo_to_expected_goals(elo_h, elo_a)
    # Fallback: generic expected goals with home advantage
    return (1.50, 1.15)


# ---------------------------------------------------------------------------
# League Simulation (Improved with Poisson goals + Elo)
# ---------------------------------------------------------------------------

def simulate_league(
    conn: duckdb.DuckDBPyConnection,
    league: str,
    season: str,
    n_simulations: int = 5000,
) -> dict[str, Any]:
    """Monte Carlo simulation for league title race.

    Improvements:
    - Poisson goal distribution for realistic scorelines & goal difference
    - Elo-based fallback probabilities when XGBoost unavailable
    """
    standings = _get_current_standings(conn, league, season)
    if not standings:
        return {"error": "No standings data available"}

    remaining = _get_remaining_fixtures(conn, league, season)
    total_teams = len(standings)

    # Compute Elo ratings for this league/season
    elo_ratings = _compute_elo_ratings(conn, league, season)

    # Pre-compute probabilities AND expected goals for all remaining matches
    match_probs: dict[int, tuple[float, float, float]] = {}
    match_xg: dict[int, tuple[float, float]] = {}
    for fix in remaining:
        match_probs[fix["match_id"]] = _get_match_probabilities(
            conn, fix["match_id"],
            elo_ratings=elo_ratings,
            home_team_id=fix["home_team_id"],
            away_team_id=fix["away_team_id"],
        )
        match_xg[fix["match_id"]] = _get_expected_goals(
            elo_ratings, fix["home_team_id"], fix["away_team_id"]
        )

    # Current points & GD per team
    base_points: dict[int, int] = {s["team_id"]: s["points"] for s in standings}
    base_gd: dict[int, int] = {s["team_id"]: s["goal_difference"] for s in standings}
    base_gf: dict[int, int] = {s["team_id"]: s["goals_for"] for s in standings}

    team_ids = [s["team_id"] for s in standings]

    # Counters
    title_count: Counter[int] = Counter()
    top4_count: Counter[int] = Counter()
    relegation_count: Counter[int] = Counter()
    position_counts: dict[int, Counter[int]] = {
        tid: Counter() for tid in team_ids
    }
    points_sum: dict[int, float] = {tid: 0.0 for tid in team_ids}

    # Relegation zone size by league
    rel_zone = {"PL": 3, "PD": 3, "BL1": 2, "SA": 3, "FL1": 3}.get(league, 3)

    rng = np.random.default_rng(seed=42)

    for _ in range(n_simulations):
        sim_points = dict(base_points)
        sim_gd = dict(base_gd)
        sim_gf = dict(base_gf)

        for fix in remaining:
            mid = fix["match_id"]
            hid = fix["home_team_id"]
            aid = fix["away_team_id"]

            # --- Poisson Goal Simulation ---
            home_xg, away_xg = match_xg[mid]
            home_goals = int(rng.poisson(home_xg))
            away_goals = int(rng.poisson(away_xg))

            # Update goals for/against and goal difference
            sim_gf[hid] = sim_gf.get(hid, 0) + home_goals
            sim_gf[aid] = sim_gf.get(aid, 0) + away_goals
            sim_gd[hid] = sim_gd.get(hid, 0) + (home_goals - away_goals)
            sim_gd[aid] = sim_gd.get(aid, 0) + (away_goals - home_goals)

            # Points
            if home_goals > away_goals:
                sim_points[hid] = sim_points.get(hid, 0) + 3
            elif home_goals == away_goals:
                sim_points[hid] = sim_points.get(hid, 0) + 1
                sim_points[aid] = sim_points.get(aid, 0) + 1
            else:
                sim_points[aid] = sim_points.get(aid, 0) + 3

        # Sort by points → GD → GF (standard tiebreaker)
        sorted_teams = sorted(
            team_ids,
            key=lambda t: (
                -sim_points.get(t, 0),
                -sim_gd.get(t, 0),
                -sim_gf.get(t, 0),
            ),
        )

        for pos, tid in enumerate(sorted_teams):
            position_counts[tid][pos + 1] += 1
            points_sum[tid] += sim_points.get(tid, 0)

        title_count[sorted_teams[0]] += 1
        for tid in sorted_teams[:4]:
            top4_count[tid] += 1
        for tid in sorted_teams[-rel_zone:]:
            relegation_count[tid] += 1

    # Build results
    team_map = {s["team_id"]: s for s in standings}
    results = []
    for tid in team_ids:
        s = team_map[tid]
        avg_pts = points_sum[tid] / n_simulations
        most_likely_pos = position_counts[tid].most_common(1)[0][0]

        results.append({
            "team_id": tid,
            "name": s["name"],
            "short_name": s["short_name"],
            "current_points": s["points"],
            "current_gd": s["goal_difference"],
            "played": s["played"],
            "title_probability": round(title_count[tid] / n_simulations, 4),
            "top4_probability": round(top4_count[tid] / n_simulations, 4),
            "relegation_probability": round(relegation_count[tid] / n_simulations, 4),
            "predicted_points": round(avg_pts, 1),
            "most_likely_position": most_likely_pos,
        })

    results.sort(key=lambda r: (-r["title_probability"], -r["current_points"]))

    return {
        "league": league,
        "season": season,
        "simulations": n_simulations,
        "remaining_matches": len(remaining),
        "teams": results,
    }


# ---------------------------------------------------------------------------
# Champions League Simulation (Fixed + Improved)
# ---------------------------------------------------------------------------

def _get_cl_knockout_matches(
    conn: duckdb.DuckDBPyConnection, season: str, competition: str = "CL"
) -> dict[str, list[dict]]:
    """Get knockout matches grouped by stage for CL/EL/ECL."""
    rows = conn.execute(
        """
        SELECT m.match_id, m.matchday, m.status,
               m.home_team_id, m.away_team_id,
               ht.name AS home_name, awt.name AS away_name,
               ht.short_name AS home_short, awt.short_name AS away_short,
               m.home_score, m.away_score
        FROM matches m
        JOIN leagues l ON l.league_id = m.league_id
        LEFT JOIN teams ht ON ht.team_id = m.home_team_id
        LEFT JOIN teams awt ON awt.team_id = m.away_team_id
        WHERE l.code = ? AND m.season = ? AND m.matchday > 8
        ORDER BY m.matchday ASC, m.kickoff ASC
        """,
        [competition, season],
    ).fetchall()

    stage_names = {96: "Round of 16", 97: "Quarter-Finals", 98: "Semi-Finals", 99: "Final"}
    stages: dict[str, list[dict]] = {}
    for r in rows:
        stage = stage_names.get(r[1], f"Round {r[1]}")
        if stage not in stages:
            stages[stage] = []
        stages[stage].append({
            "match_id": r[0],
            "matchday": r[1],
            "status": r[2],
            "home_team_id": r[3],
            "away_team_id": r[4],
            "home_name": r[5],
            "away_name": r[6],
            "home_short": r[7],
            "away_short": r[8],
            "home_score": r[9],
            "away_score": r[10],
        })
    return stages


def _get_cl_league_stage_teams(
    conn: duckdb.DuckDBPyConnection, season: str, competition: str = "CL"
) -> list[dict[str, Any]]:
    """Get league stage standings for CL/EL/ECL."""
    rows = conn.execute(
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
        [competition, season],
    ).fetchall()

    teams = []
    for i, r in enumerate(rows):
        pts = r[4] * 3 + r[5]
        teams.append({
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
            "points": pts,
            "goal_difference": r[7] - r[8],
        })
    return teams


def _simulate_knockout_match(
    rng: np.random.Generator,
    team_a: int,
    team_b: int,
    elo_ratings: dict[int, float],
) -> int:
    """Simulate a single knockout match using Elo-based Poisson goals.
    Returns the winning team_id."""
    elo_a = elo_ratings.get(team_a, DEFAULT_ELO)
    elo_b = elo_ratings.get(team_b, DEFAULT_ELO)

    # team_a is "home" (higher seed or first drawn)
    xg_a, xg_b = _elo_to_expected_goals(elo_a, elo_b)

    goals_a = int(rng.poisson(xg_a))
    goals_b = int(rng.poisson(xg_b))

    if goals_a > goals_b:
        return team_a
    elif goals_b > goals_a:
        return team_b
    else:
        # Extra time / penalties — slight advantage to higher Elo
        prob_a = 0.5 + 0.05 * math.tanh((elo_a - elo_b) / 200.0)
        return team_a if rng.random() < prob_a else team_b


def _generate_bracket_from_league_stage(
    league_stage: list[dict[str, Any]],
    rng: np.random.Generator,
) -> list[tuple[int, int]]:
    """Generate knockout bracket from league stage standings.

    CL new format:
    - Top 8 → directly to Round of 16
    - 9th-24th → Knockout playoffs (8 ties), winners join R16
    - 25th-36th → eliminated

    Returns list of (team_a, team_b) pairs for R16 after resolving playoffs.
    """
    if len(league_stage) < 16:
        # Not enough teams, use what we have
        teams = [t["team_id"] for t in league_stage]
        pairs = []
        for i in range(0, len(teams) - 1, 2):
            pairs.append((teams[i], teams[i + 1]))
        return pairs

    top_8 = [t["team_id"] for t in league_stage[:8]]
    playoff_teams = [t["team_id"] for t in league_stage[8:24]]

    # Playoff: 9v24, 10v23, 11v22, ... (seeded)
    playoff_pairs = []
    for i in range(min(8, len(playoff_teams) // 2)):
        playoff_pairs.append((playoff_teams[i], playoff_teams[-(i + 1)]))

    return top_8, playoff_pairs


def simulate_champions_league(
    conn: duckdb.DuckDBPyConnection,
    season: str,
    n_simulations: int = 5000,
) -> dict[str, Any]:
    """Monte Carlo simulation for Champions League winner.

    Fixed: generates bracket from league stage when no knockout matches in DB.
    Improved: Elo-based Poisson goal simulation for knockout matches.
    """
    return _simulate_european_competition(conn, season, "CL", n_simulations)


def simulate_europa_league(
    conn: duckdb.DuckDBPyConnection,
    season: str,
    n_simulations: int = 5000,
) -> dict[str, Any]:
    """Monte Carlo simulation for Europa League winner."""
    return _simulate_european_competition(conn, season, "EL", n_simulations)


def simulate_conference_league(
    conn: duckdb.DuckDBPyConnection,
    season: str,
    n_simulations: int = 5000,
) -> dict[str, Any]:
    """Monte Carlo simulation for Conference League winner."""
    return _simulate_european_competition(conn, season, "ECL", n_simulations)


def _simulate_european_competition(
    conn: duckdb.DuckDBPyConnection,
    season: str,
    competition: str,
    n_simulations: int = 5000,
) -> dict[str, Any]:
    """Unified Monte Carlo simulation for CL/EL/ECL.

    Strategy:
    1. Get knockout matches from DB (if any exist)
    2. Get league stage standings
    3. If no knockout bracket exists, generate one from league stage
    4. Simulate full tournament using Elo-based Poisson goals
    """
    knockout_stages = _get_cl_knockout_matches(conn, season, competition)
    league_stage = _get_cl_league_stage_teams(conn, season, competition)

    # Collect all teams
    all_teams: dict[int, dict] = {}
    for team in league_stage:
        all_teams[team["team_id"]] = {
            "name": team["name"],
            "short_name": team["short_name"],
            "position": team["position"],
        }

    for stage_matches in knockout_stages.values():
        for m in stage_matches:
            if m["home_team_id"] and m["home_team_id"] not in all_teams:
                all_teams[m["home_team_id"]] = {
                    "name": m["home_name"] or "TBD",
                    "short_name": m["home_short"] or "",
                }
            if m["away_team_id"] and m["away_team_id"] not in all_teams:
                all_teams[m["away_team_id"]] = {
                    "name": m["away_name"] or "TBD",
                    "short_name": m["away_short"] or "",
                }

    if not all_teams:
        return {"error": f"No {competition} data available"}

    # Compute Elo ratings from all CL matches this season
    elo_ratings = _compute_elo_ratings(conn, competition, season)
    # Also pull domestic Elo as supplement (teams may not have enough CL matches)
    for league_code in ["PL", "PD", "BL1", "SA", "FL1"]:
        domestic_elo = _compute_elo_ratings(conn, league_code, season)
        for tid, elo_val in domestic_elo.items():
            if tid not in elo_ratings:
                elo_ratings[tid] = elo_val

    rng = np.random.default_rng(seed=42)

    # Determine which knockout matches are finished vs scheduled
    stage_order = ["Round of 16", "Quarter-Finals", "Semi-Finals", "Final"]
    finished_results: dict[int, tuple[int, int]] = {}
    scheduled_knockout: list[dict] = []

    for stage_name in stage_order:
        if stage_name not in knockout_stages:
            continue
        for m in knockout_stages[stage_name]:
            if m["status"] == "FINISHED" and m["home_score"] is not None:
                hid, aid = m["home_team_id"], m["away_team_id"]
                if m["home_score"] > m["away_score"]:
                    finished_results[m["match_id"]] = (hid, aid)
                elif m["away_score"] > m["home_score"]:
                    finished_results[m["match_id"]] = (aid, hid)
                else:
                    finished_results[m["match_id"]] = (hid, aid)
            elif m["status"] == "SCHEDULED":
                scheduled_knockout.append(m)

    # --- KEY FIX: Generate bracket from league stage if no knockout data ---
    use_generated_bracket = (
        not knockout_stages or
        (not scheduled_knockout and not finished_results)
    )

    # Pre-compute probs for existing scheduled knockout matches
    ko_probs: dict[int, tuple[float, float, float]] = {}
    for m in scheduled_knockout:
        ko_probs[m["match_id"]] = _get_match_probabilities(
            conn, m["match_id"],
            elo_ratings=elo_ratings,
            home_team_id=m["home_team_id"],
            away_team_id=m["away_team_id"],
        )

    # Counters
    winner_count: Counter[int] = Counter()
    final_count: Counter[int] = Counter()
    semifinal_count: Counter[int] = Counter()
    quarterfinal_count: Counter[int] = Counter()
    r16_count: Counter[int] = Counter()

    for _ in range(n_simulations):
        if use_generated_bracket and len(league_stage) >= 16:
            # --- GENERATED BRACKET (when no knockout matches in DB) ---
            top_8 = [t["team_id"] for t in league_stage[:8]]
            playoff_seeds = [t["team_id"] for t in league_stage[8:24]]

            # Simulate playoffs: 9v24, 10v23, ...
            playoff_winners = []
            n_playoff = min(8, len(playoff_seeds) // 2)
            for i in range(n_playoff):
                high_seed = playoff_seeds[i]
                low_seed = playoff_seeds[-(i + 1)] if (i + 1) <= len(playoff_seeds) else playoff_seeds[i]
                winner = _simulate_knockout_match(rng, high_seed, low_seed, elo_ratings)
                playoff_winners.append(winner)

            # R16: top 8 vs playoff winners (1v lowest playoff winner, etc.)
            r16_teams = []
            for i in range(min(8, len(top_8))):
                r16_teams.append(top_8[i])
            for w in playoff_winners:
                r16_teams.append(w)

            # Track R16 participation
            for tid in r16_teams:
                r16_count[tid] += 1

            # R16 matches: 1st vs 16th, 2nd vs 15th, etc.
            qf_teams = []
            n_r16 = min(8, len(r16_teams) // 2)
            for i in range(n_r16):
                team_a = r16_teams[i]
                team_b = r16_teams[-(i + 1)] if (i + 1) <= len(r16_teams) else r16_teams[i]
                winner = _simulate_knockout_match(rng, team_a, team_b, elo_ratings)
                qf_teams.append(winner)
                quarterfinal_count[winner] += 1

            # QF
            sf_teams = []
            n_qf = min(4, len(qf_teams) // 2)
            for i in range(n_qf):
                team_a = qf_teams[i * 2] if i * 2 < len(qf_teams) else qf_teams[0]
                team_b = qf_teams[i * 2 + 1] if i * 2 + 1 < len(qf_teams) else qf_teams[-1]
                winner = _simulate_knockout_match(rng, team_a, team_b, elo_ratings)
                sf_teams.append(winner)
                semifinal_count[winner] += 1

            # SF
            finalists = []
            if len(sf_teams) >= 2:
                for i in range(0, min(2, len(sf_teams) // 2) * 2, 2):
                    team_a = sf_teams[i]
                    team_b = sf_teams[i + 1] if i + 1 < len(sf_teams) else sf_teams[i]
                    winner = _simulate_knockout_match(rng, team_a, team_b, elo_ratings)
                    finalists.append(winner)
                    final_count[winner] += 1
            elif len(sf_teams) == 1:
                finalists = sf_teams
                final_count[sf_teams[0]] += 1

            # Final
            if len(finalists) >= 2:
                champion = _simulate_knockout_match(rng, finalists[0], finalists[1], elo_ratings)
                winner_count[champion] += 1
            elif len(finalists) == 1:
                winner_count[finalists[0]] += 1

        else:
            # --- EXISTING BRACKET (use DB knockout data) ---
            sim_winners: dict[int, int] = {}
            for m in scheduled_knockout:
                h_prob, d_prob, a_prob = ko_probs[m["match_id"]]
                total_win = h_prob + a_prob
                if total_win > 0:
                    adj_h = h_prob + d_prob * (h_prob / total_win)
                else:
                    adj_h = 0.5
                r = rng.random()
                sim_winners[m["match_id"]] = (
                    m["home_team_id"] if r < adj_h else m["away_team_id"]
                )

            stage_winners: dict[str, list[int]] = {}
            for stage_name in stage_order:
                if stage_name not in knockout_stages:
                    continue
                winners = []
                for m in knockout_stages[stage_name]:
                    if m["match_id"] in finished_results:
                        winners.append(finished_results[m["match_id"]][0])
                    elif m["match_id"] in sim_winners:
                        winners.append(sim_winners[m["match_id"]])
                stage_winners[stage_name] = winners

            # Track progression
            if "Final" in stage_winners and stage_winners["Final"]:
                winner_count[stage_winners["Final"][0]] += 1
            elif "Semi-Finals" in stage_winners and len(stage_winners.get("Semi-Finals", [])) >= 2:
                sf_w = stage_winners["Semi-Finals"]
                champion = _simulate_knockout_match(rng, sf_w[0], sf_w[1], elo_ratings)
                winner_count[champion] += 1

            for stage_name in ["Semi-Finals", "Final"]:
                for tid in stage_winners.get(stage_name, []):
                    semifinal_count[tid] += 1
            for stage_name in ["Quarter-Finals", "Semi-Finals", "Final"]:
                for tid in stage_winners.get(stage_name, []):
                    quarterfinal_count[tid] += 1

    # Build results
    active_teams = list(all_teams.keys())
    results = []
    for tid in active_teams:
        info = all_teams[tid]
        wp = winner_count[tid] / max(1, n_simulations)
        sfp = semifinal_count[tid] / max(1, n_simulations)
        qfp = quarterfinal_count[tid] / max(1, n_simulations)

        results.append({
            "team_id": tid,
            "name": info["name"],
            "short_name": info["short_name"],
            "win_probability": round(wp, 4),
            "semifinal_probability": round(sfp, 4),
            "quarterfinal_probability": round(qfp, 4),
        })

    results.sort(key=lambda r: -r["win_probability"])

    return {
        "league": competition,
        "season": season,
        "simulations": n_simulations,
        "remaining_knockout_matches": len(scheduled_knockout),
        "active_teams": len(active_teams),
        "bracket_generated": use_generated_bracket if len(league_stage) >= 16 else False,
        "teams": results,
    }
