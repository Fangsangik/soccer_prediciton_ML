"""Monte Carlo season simulator for league title & CL winner prediction."""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import Any

import duckdb
import numpy as np


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
    conn: duckdb.DuckDBPyConnection, match_id: int
) -> tuple[float, float, float]:
    """Get cached prediction probabilities, or use heuristic fallback."""
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

    # Fallback: try live prediction
    try:
        from backend.models.match_predictor import predict
        result = predict(match_id, conn)
        if "error" not in result:
            p = result["probabilities"]
            return (p["home_win"], p["draw"], p["away_win"])
    except Exception:
        pass

    # Default heuristic (home advantage)
    return (0.45, 0.27, 0.28)


# ---------------------------------------------------------------------------
# League Simulation
# ---------------------------------------------------------------------------

def simulate_league(
    conn: duckdb.DuckDBPyConnection,
    league: str,
    season: str,
    n_simulations: int = 5000,
) -> dict[str, Any]:
    """Monte Carlo simulation for league title race.

    Runs *n_simulations* of the remaining season and returns the probability
    of each team finishing in each position (title, top 4, relegation).
    """
    standings = _get_current_standings(conn, league, season)
    if not standings:
        return {"error": "No standings data available"}

    remaining = _get_remaining_fixtures(conn, league, season)
    total_teams = len(standings)

    # Pre-compute probabilities for all remaining matches
    match_probs: dict[int, tuple[float, float, float]] = {}
    for fix in remaining:
        match_probs[fix["match_id"]] = _get_match_probabilities(
            conn, fix["match_id"]
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
            h_prob, d_prob, _ = match_probs[mid]

            r = rng.random()
            if r < h_prob:
                sim_points[hid] = sim_points.get(hid, 0) + 3
                sim_gd[hid] = sim_gd.get(hid, 0) + 1
                sim_gd[aid] = sim_gd.get(aid, 0) - 1
                sim_gf[hid] = sim_gf.get(hid, 0) + 1
            elif r < h_prob + d_prob:
                sim_points[hid] = sim_points.get(hid, 0) + 1
                sim_points[aid] = sim_points.get(aid, 0) + 1
            else:
                sim_points[aid] = sim_points.get(aid, 0) + 3
                sim_gd[aid] = sim_gd.get(aid, 0) + 1
                sim_gd[hid] = sim_gd.get(hid, 0) - 1
                sim_gf[aid] = sim_gf.get(aid, 0) + 1

        # Sort by points â GD â GF (standard tiebreaker)
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
        # Most likely final position
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

    # Sort by title probability desc, then current points desc
    results.sort(key=lambda r: (-r["title_probability"], -r["current_points"]))

    return {
        "league": league,
        "season": season,
        "simulations": n_simulations,
        "remaining_matches": len(remaining),
        "teams": results,
    }


# ---------------------------------------------------------------------------
# Champions League Simulation
# ---------------------------------------------------------------------------

def _get_cl_knockout_matches(
    conn: duckdb.DuckDBPyConnection, season: str
) -> dict[str, list[dict]]:
    """Get CL knockout matches grouped by stage."""
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
        WHERE l.code = 'CL' AND m.season = ? AND m.matchday > 8
        ORDER BY m.matchday ASC, m.kickoff ASC
        """,
        [season],
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
    conn: duckdb.DuckDBPyConnection, season: str
) -> list[dict[str, Any]]:
    """Get CL league stage standings."""
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
        WHERE m.status = 'FINISHED' AND l.code = 'CL' AND m.season = ? AND m.matchday <= 8
        GROUP BY t.team_id, t.name, t.short_name
        ORDER BY (SUM(CASE WHEN (m.home_team_id = t.team_id AND m.home_score > m.away_score)
                       OR (m.away_team_id = t.team_id AND m.away_score > m.home_score) THEN 3
                       WHEN m.home_score = m.away_score THEN 1 ELSE 0 END)) DESC,
                 (SUM(CASE WHEN m.home_team_id = t.team_id THEN m.home_score ELSE m.away_score END) -
                  SUM(CASE WHEN m.home_team_id = t.team_id THEN m.away_score ELSE m.home_score END)) DESC
        """,
        [season],
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


def simulate_champions_league(
    conn: duckdb.DuckDBPyConnection,
    season: str,
    n_simulations: int = 5000,
) -> dict[str, Any]:
    """Monte Carlo simulation for Champions League winner.

    Strategy:
    - For knockout matches: simulate each tie using match probabilities
    - If knockout bracket is incomplete, fill remaining slots from league stage
    - For each simulation, propagate winners through the bracket
    """
    knockout_stages = _get_cl_knockout_matches(conn, season)
    league_stage = _get_cl_league_stage_teams(conn, season)

    # Collect all CL teams (from knockout + league stage)
    all_teams: dict[int, dict] = {}
    for team in league_stage:
        all_teams[team["team_id"]] = {"name": team["name"], "short_name": team["short_name"]}

    for stage_matches in knockout_stages.values():
        for m in stage_matches:
            if m["home_team_id"] and m["home_team_id"] not in all_teams:
                all_teams[m["home_team_id"]] = {"name": m["home_name"] or "TBD", "short_name": m["home_short"] or ""}
            if m["away_team_id"] and m["away_team_id"] not in all_teams:
                all_teams[m["away_team_id"]] = {"name": m["away_name"] or "TBD", "short_name": m["away_short"] or ""}

    if not all_teams:
        return {"error": "No Champions League data available"}

    # Determine which teams are still alive in the tournament
    # Check finished knockout results to find eliminated teams
    eliminated: set[int] = set()
    stage_order = ["Round of 16", "Quarter-Finals", "Semi-Finals", "Final"]

    for stage_name in stage_order:
        if stage_name not in knockout_stages:
            continue
        matches = knockout_stages[stage_name]
        # Group by pair (two legs per tie, except final)
        for m in matches:
            if m["status"] == "FINISHED" and m["home_score"] is not None:
                hid, aid = m["home_team_id"], m["away_team_id"]
                hs, as_ = m["home_score"], m["away_score"]
                if stage_name == "Final":
                    if hs > as_:
                        eliminated.add(aid)
                    elif as_ > hs:
                        eliminated.add(hid)

    # Teams still in competition
    active_teams = [tid for tid in all_teams if tid not in eliminated]

    if not active_teams:
        # All matches done, tournament finished
        return {
            "league": "CL",
            "season": season,
            "simulations": 0,
            "teams": [],
            "status": "completed",
        }

    # For simulation, we use a simplified approach:
    # Each remaining match gets simulated with match probabilities
    # Teams advance based on single-match results (simplified from two-leg)
    rng = np.random.default_rng(seed=42)
    winner_count: Counter[int] = Counter()
    semifinal_count: Counter[int] = Counter()
    quarterfinal_count: Counter[int] = Counter()

    # Collect scheduled knockout matches
    scheduled_knockout: list[dict] = []
    finished_results: dict[int, tuple[int, int]] = {}  # match_id â (winner_id, loser_id)

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
                    # Draw in knockout (penalties) â home team slight advantage
                    finished_results[m["match_id"]] = (hid, aid)
            elif m["status"] == "SCHEDULED":
                scheduled_knockout.append(m)

    # Pre-compute probabilities for scheduled knockout matches
    ko_probs: dict[int, tuple[float, float, float]] = {}
    for m in scheduled_knockout:
        ko_probs[m["match_id"]] = _get_match_probabilities(conn, m["match_id"])

    for _ in range(n_simulations):
        # Simulate scheduled knockout matches
        sim_winners: dict[int, int] = {}  # match_id â winner_team_id
        for m in scheduled_knockout:
            h_prob, d_prob, a_prob = ko_probs[m["match_id"]]
            # In knockout, draws go to extra time / penalties
            # Redistribute draw probability
            total_win = h_prob + a_prob
            if total_win > 0:
                adj_h = h_prob + d_prob * (h_prob / total_win)
            else:
                adj_h = 0.5
            r = rng.random()
            sim_winners[m["match_id"]] = m["home_team_id"] if r < adj_h else m["away_team_id"]

        # Determine simulation winners from finished + simulated results
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

        # The final winner
        if "Final" in stage_winners and stage_winners["Final"]:
            winner_count[stage_winners["Final"][0]] += 1
        elif "Semi-Finals" in stage_winners and stage_winners["Semi-Finals"]:
            # No final yet â simulate from SF winners
            sf_winners = stage_winners["Semi-Finals"]
            if len(sf_winners) >= 2:
                r = rng.random()
                winner_count[sf_winners[0] if r < 0.5 else sf_winners[1]] += 1
            elif sf_winners:
                winner_count[sf_winners[0]] += 1

        # Track semi-final reach
        for stage_name in ["Semi-Finals", "Final"]:
            if stage_name in stage_winners:
                for tid in stage_winners[stage_name]:
                    semifinal_count[tid] += 1

        for stage_name in ["Quarter-Finals", "Semi-Finals", "Final"]:
            if stage_name in stage_winners:
                for tid in stage_winners[stage_name]:
                    quarterfinal_count[tid] += 1

    # Build results
    results = []
    for tid in active_teams:
        info = all_teams[tid]
        results.append({
            "team_id": tid,
            "name": info["name"],
            "short_name": info["short_name"],
            "win_probability": round(winner_count[tid] / max(1, n_simulations), 4),
            "semifinal_probability": round(semifinal_count[tid] / max(1, n_simulations), 4),
            "quarterfinal_probability": round(quarterfinal_count[tid] / max(1, n_simulations), 4),
        })

    results.sort(key=lambda r: -r["win_probability"])

    return {
        "league": "CL",
        "season": season,
        "simulations": n_simulations,
        "remaining_knockout_matches": len(scheduled_knockout),
        "active_teams": len(active_teams),
        "teams": results,
    }
