"""Scouting service: player profiles, similarity, undervalued - all leagues."""
from __future__ import annotations

from typing import Any

import numpy as np
import duckdb


def get_player_profile(
    player_id: int,
    conn: duckdb.DuckDBPyConnection,
    season: str = "2024-25",
) -> dict[str, Any] | None:
    """Get player profile. Checks players+stats table first, then fpl_players."""

    # Try players + player_season_stats (works for all leagues)
    row = conn.execute(
        """SELECT p.player_id, p.name, p.position, p.nationality, p.market_value_eur,
                  t.name AS team, l.code AS league,
                  s.minutes_played, s.matches_played, s.goals, s.assists,
                  s.xg, s.xa, s.xg_per_90, s.xa_per_90,
                  s.shots_per_90, s.key_passes_per_90,
                  s.progressive_carries_per_90, s.tackles_per_90,
                  s.interceptions_per_90, s.aerials_won_per_90
           FROM players p
           LEFT JOIN teams t ON t.team_id = p.team_id
           LEFT JOIN leagues l ON l.league_id = t.league_id
           LEFT JOIN player_season_stats s ON s.player_id = p.player_id AND s.season = ?
           WHERE p.player_id = ?""",
        [season, player_id],
    ).fetchone()

    if row:
        (pid, name, pos, nat, mv, team, league,
         mins, mp, goals, assists, xg, xa, xg_p90, xa_p90,
         shots, kp, pc, tk, inter, ae) = row

        nineties = (mins or 1) / 90.0
        stats_per_90 = {
            "goals": round((goals or 0) / max(0.1, nineties), 3),
            "assists": round((assists or 0) / max(0.1, nineties), 3),
            "xg": round(float(xg_p90 or 0), 3),
            "xa": round(float(xa_p90 or 0), 3),
            "shots": round(float(shots or 0), 3),
            "key_passes": round(float(kp or 0), 3),
            "progressive_carries": round(float(pc or 0), 3),
            "tackles": round(float(tk or 0), 3),
            "interceptions": round(float(inter or 0), 3),
            "aerials_won": round(float(ae or 0), 3),
        }

        refs = {"goals": 0.7, "assists": 0.5, "xg": 0.7, "xa": 0.5, "shots": 3.5,
                "key_passes": 2.5, "progressive_carries": 4.0, "tackles": 3.5,
                "interceptions": 2.5, "aerials_won": 2.5}
        percentile_ranks = {k: round(min(99, stats_per_90.get(k, 0) / refs[k] * 100), 1) for k in refs}

        # Check for FPL data too
        fpl = None
        fpl_row = conn.execute(
            "SELECT fpl_id, price, total_points, form, points_per_game, selected_by_pct, injury_status FROM fpl_players WHERE web_name LIKE ? LIMIT 1",
            [f"%{name.split()[-1]}%"],
        ).fetchone()
        if fpl_row:
            fpl = {"fpl_id": fpl_row[0], "price": fpl_row[1], "total_points": fpl_row[2],
                   "form": fpl_row[3], "points_per_game": fpl_row[4],
                   "selected_by_pct": fpl_row[5], "injury_status": fpl_row[6]}

        # Estimate market value if missing (mv can be 0 or None)
        if (mv is None or mv == 0) and fpl and fpl.get("price"):
            mv = int(fpl["price"] * 1_000_000)
        elif (mv is None or mv == 0) and mins and goals:
            # Rough estimate from output: ~€2M per goal/90 base
            ga_p90 = ((goals or 0) + (assists or 0)) / max(0.1, (mins or 1) / 90)
            mv = int(max(500_000, ga_p90 * 8_000_000))

        age = None
        dob_row = conn.execute("SELECT date_of_birth FROM players WHERE player_id = ?", [pid]).fetchone()
        if dob_row and dob_row[0]:
            from datetime import date
            dob = dob_row[0]
            if isinstance(dob, str):
                dob = date.fromisoformat(dob)
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        return {
            "player": {"id": pid, "name": name, "team": team or "", "league": league or "",
                       "position": pos or "", "age": age, "nationality": nat or "",
                       "market_value_eur": mv or 0, "contract_until": ""},
            "stats_per_90": stats_per_90,
            "percentile_ranks": percentile_ranks,
            "fpl": fpl,
        }

    # Fallback: try fpl_players directly (PL only, using fpl_id)
    fpl_row = conn.execute(
        """SELECT fpl_id, web_name, position, team_name, price, total_points,
                  form, points_per_game, selected_by_pct, minutes,
                  goals_scored, assists, influence, creativity, threat
           FROM fpl_players WHERE fpl_id = ?""",
        [player_id],
    ).fetchone()

    if fpl_row:
        (fid, name, pos, team, price, pts, form, ppg, sel, mins,
         goals, assists, infl, crea, thr) = fpl_row
        mins = mins or 1
        p90 = 90.0 / mins
        stats_per_90 = {
            "goals": round((goals or 0) * p90, 3), "assists": round((assists or 0) * p90, 3),
            "xg": round((goals or 0) * p90 * 0.9, 3), "xa": round((assists or 0) * p90 * 0.9, 3),
            "shots": round(float(thr or 0) / mins * 9, 3),
            "key_passes": round(float(crea or 0) / mins * 7.5, 3),
            "progressive_carries": round(float(infl or 0) / mins * 4.5, 3),
            "tackles": round(float(infl or 0) / mins * 3, 3),
            "interceptions": round(float(infl or 0) / mins * 2.5, 3),
            "aerials_won": round(float(infl or 0) / mins * 2.2, 3),
        }
        refs = {"goals": 0.7, "assists": 0.5, "xg": 0.7, "xa": 0.5, "shots": 3.5,
                "key_passes": 2.5, "progressive_carries": 4.0, "tackles": 3.5,
                "interceptions": 2.5, "aerials_won": 2.5}
        percentile_ranks = {k: round(min(99, stats_per_90.get(k, 0) / refs[k] * 100), 1) for k in refs}
        return {
            "player": {"id": fid, "name": name, "team": team or "", "league": "PL",
                       "position": pos or "", "age": None, "nationality": "",
                       "market_value_eur": int((price or 5) * 1e6), "contract_until": ""},
            "stats_per_90": stats_per_90, "percentile_ranks": percentile_ranks,
            "fpl": {"fpl_id": fid, "price": price, "total_points": pts, "form": form,
                    "points_per_game": ppg, "selected_by_pct": sel},
        }

    return None


def _strip_accents(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def search_players(
    query: str,
    conn: duckdb.DuckDBPyConnection,
    league: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search players by name across all leagues (accent-insensitive)."""
    q_clean = _strip_accents(query.lower())
    # Use DuckDB's strip_accents function for accent-insensitive search
    where = "WHERE lower(strip_accents(p.name)) LIKE ?"
    params: list[Any] = [f"%{q_clean}%"]
    if league:
        where += " AND l.code = ?"
        params.append(league)

    rows = conn.execute(
        f"""SELECT p.player_id, p.name, p.position, t.name AS team, l.code AS league,
                   s.goals, s.assists, s.xg_per_90, s.xa_per_90, s.minutes_played
            FROM players p
            LEFT JOIN teams t ON t.team_id = p.team_id
            LEFT JOIN leagues l ON l.league_id = t.league_id
            LEFT JOIN player_season_stats s ON s.player_id = p.player_id
            {where}
            ORDER BY COALESCE(s.minutes_played, 0) DESC
            LIMIT ?""",
        params + [limit],
    ).fetchall()

    return [
        {"player_id": r[0], "name": r[1], "position": r[2] or "", "team": r[3] or "",
         "league": r[4] or "", "goals": r[5] or 0, "assists": r[6] or 0,
         "xg_per_90": round(float(r[7] or 0), 3), "xa_per_90": round(float(r[8] or 0), 3),
         "minutes": r[9] or 0}
        for r in rows
    ]


def find_similar(
    player_id: int,
    filters: dict[str, Any],
    conn: duckdb.DuckDBPyConnection,
    season: str = "2024-25",
    top_n: int = 10,
) -> dict[str, Any]:
    """Find similar players using player_season_stats across all leagues."""

    target = conn.execute(
        """SELECT p.player_id, p.name, p.position,
                  s.xg_per_90, s.xa_per_90, s.shots_per_90, s.key_passes_per_90,
                  s.progressive_carries_per_90, s.tackles_per_90, s.interceptions_per_90,
                  s.goals, s.assists, s.minutes_played
           FROM players p
           JOIN player_season_stats s ON s.player_id = p.player_id AND s.season = ?
           WHERE p.player_id = ?""",
        [season, player_id],
    ).fetchone()

    empty = {"reference_player": {"id": player_id, "name": ""}, "similar_players": [], "embedding_2d": []}

    if not target:
        return empty

    pos_filter = filters.get("position_filter") or filters.get("position")
    league_filter = filters.get("league_filter") or filters.get("league")

    where = "WHERE s.minutes_played >= 450"
    params: list[Any] = [season]
    if pos_filter:
        where += " AND p.position = ?"
        params.append(pos_filter)
    if league_filter:
        where += " AND l.code = ?"
        params.append(league_filter)

    all_rows = conn.execute(
        f"""SELECT p.player_id, p.name, p.position, t.name AS team, l.code AS league,
                   COALESCE(s.xg_per_90,0), COALESCE(s.xa_per_90,0),
                   COALESCE(s.shots_per_90,0), COALESCE(s.key_passes_per_90,0),
                   COALESCE(s.progressive_carries_per_90,0),
                   COALESCE(s.tackles_per_90,0), COALESCE(s.interceptions_per_90,0),
                   s.goals, s.assists
            FROM players p
            JOIN player_season_stats s ON s.player_id = p.player_id AND s.season = ?
            LEFT JOIN teams t ON t.team_id = p.team_id
            LEFT JOIN leagues l ON l.league_id = t.league_id
            {where}""",
        params,
    ).fetchall()

    if len(all_rows) < 2:
        return {"reference_player": {"id": player_id, "name": target[1]}, "similar_players": [], "embedding_2d": []}

    ids = [r[0] for r in all_rows]
    names = [r[1] for r in all_rows]
    positions = [r[2] for r in all_rows]
    teams = [r[3] for r in all_rows]
    leagues = [r[4] for r in all_rows]

    matrix = np.array([[float(r[5]), float(r[6]), float(r[7]), float(r[8]),
                         float(r[9]), float(r[10]), float(r[11])] for r in all_rows], dtype=float)

    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0)
    std[std == 0] = 1.0
    normed = (matrix - mean) / std

    if player_id not in ids:
        return {"reference_player": {"id": player_id, "name": target[1]}, "similar_players": [], "embedding_2d": []}

    tidx = ids.index(player_id)
    from sklearn.metrics.pairwise import cosine_similarity
    sims = cosine_similarity(normed[tidx:tidx + 1], normed)[0]

    ranked = sorted(
        [(i, float(sims[i])) for i in range(len(ids)) if ids[i] != player_id],
        key=lambda x: x[1], reverse=True,
    )[:top_n]

    similar = [
        {"player_id": ids[i], "name": names[i], "team": teams[i] or "", "league": leagues[i] or "",
         "position": positions[i] or "", "age": None, "similarity_score": round(s, 3),
         "market_value_eur": 0, "stats_per_90": {}, "percentile_comparison": {}}
        for i, s in ranked
    ]

    embedding_2d: list[dict[str, Any]] = []
    try:
        from sklearn.decomposition import PCA
        if normed.shape[0] >= 3:
            coords = PCA(n_components=2, random_state=42).fit_transform(normed)
            include = {player_id} | {ids[i] for i, _ in ranked}
            for idx, pid in enumerate(ids):
                if pid in include:
                    embedding_2d.append({"player_id": pid, "x": round(float(coords[idx, 0]), 3),
                                         "y": round(float(coords[idx, 1]), 3), "label": names[idx]})
    except Exception:
        pass

    return {"reference_player": {"id": player_id, "name": target[1]}, "similar_players": similar, "embedding_2d": embedding_2d}


def get_undervalued(
    filters: dict[str, Any],
    conn: duckdb.DuckDBPyConnection,
    season: str = "2024-25",
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """Undervalued players across all leagues based on goals+assists output vs minutes."""
    pos = filters.get("position")
    league = filters.get("league")
    min_mins = filters.get("min_minutes", 450)

    where = "WHERE s.minutes_played >= ?"
    params: list[Any] = [season, min_mins]
    if pos:
        where += " AND p.position = ?"
        params.append(pos)

    # For European competitions (CL/EL/ECL), find teams in that competition
    # and show their players from domestic league stats
    european_comps = {"CL", "EL", "ECL"}
    if league and league in european_comps:
        team_names = conn.execute(
            "SELECT DISTINCT t.name FROM teams t JOIN leagues l ON l.league_id = t.league_id WHERE l.code = ?",
            [league],
        ).fetchall()
        if team_names:
            placeholders = ",".join(["?" for _ in team_names])
            where += f" AND t.name IN ({placeholders})"
            params.extend([tn[0] for tn in team_names])
    elif league:
        where += " AND l.code = ?"
        params.append(league)

    rows = conn.execute(
        f"""SELECT p.player_id, p.name, p.position, t.name AS team, l.code AS league,
                   s.minutes_played, s.goals, s.assists,
                   s.xg_per_90, s.xa_per_90
            FROM players p
            JOIN player_season_stats s ON s.player_id = p.player_id AND s.season = ?
            LEFT JOIN teams t ON t.team_id = p.team_id
            LEFT JOIN leagues l ON l.league_id = t.league_id
            {where}
            ORDER BY (COALESCE(s.xg_per_90,0) + COALESCE(s.xa_per_90,0)) DESC
            LIMIT ?""",
        params + [top_n],
    ).fetchall()

    results = []
    for r in rows:
        pid, name, pos_code, team, lg, mins, goals, assists, xg_p90, xa_p90 = r
        nineties = max(0.1, (mins or 1) / 90.0)
        ga_p90 = ((goals or 0) + (assists or 0)) / nineties
        perf = min(100, ga_p90 * 50)

        strengths = []
        if (goals or 0) / nineties > 0.3:
            strengths.append("Goals")
        if (assists or 0) / nineties > 0.2:
            strengths.append("Assists")
        if float(xg_p90 or 0) > 0.4:
            strengths.append("High xG")
        if float(xa_p90 or 0) > 0.25:
            strengths.append("High xA")

        # Estimate market value: try FPL price first (PL players), then stats-based estimate
        mv = 0
        if lg == "PL":
            fpl_row = conn.execute(
                "SELECT price FROM fpl_players WHERE web_name LIKE ? LIMIT 1",
                [f"%{name.split()[-1]}%"],
            ).fetchone()
            if fpl_row and fpl_row[0]:
                mv = int(fpl_row[0] * 1_000_000)

        if mv == 0:
            mv = int(max(500_000, ga_p90 * 8_000_000))

        age = None
        dob_row = conn.execute("SELECT date_of_birth FROM players WHERE player_id = ?", [pid]).fetchone()
        if dob_row and dob_row[0]:
            from datetime import date as _date
            dob = dob_row[0]
            if isinstance(dob, str):
                dob = _date.fromisoformat(dob)
            today = _date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

        results.append({
            "player_id": pid, "name": name, "team": team or "", "league": lg or "",
            "position": pos_code or "", "age": age, "market_value_eur": mv,
            "performance_index": round(perf, 1),
            "value_ratio": round(ga_p90, 2),
            "overperformance_pct": round(float(xg_p90 or 0) + float(xa_p90 or 0), 2),
            "key_strengths": strengths[:3], "key_weaknesses": [],
        })
    return results
