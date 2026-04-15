"""Data sync endpoints - trigger real API data collection."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
import duckdb

from backend.deps import get_database

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/status")
async def sync_status(
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Show last sync times and record counts for each data source."""
    try:
        runs = conn.execute(
            """SELECT collector_name, MAX(finished_at) AS last_run, SUM(records_fetched) AS total_records
               FROM collector_runs
               WHERE status = 'success'
               GROUP BY collector_name
               ORDER BY collector_name"""
        ).fetchall()

        status: dict[str, Any] = {}
        for name, last_run, total in runs:
            status[name] = {
                "last_run": last_run.isoformat() if last_run else None,
                "total_records": total,
            }

        # Add table counts
        counts = {
            "leagues": conn.execute("SELECT COUNT(*) FROM leagues").fetchone()[0],
            "teams": conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0],
            "matches": conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0],
            "players": conn.execute("SELECT COUNT(*) FROM players").fetchone()[0],
            "player_season_stats": conn.execute("SELECT COUNT(*) FROM player_season_stats").fetchone()[0],
            "fpl_players": conn.execute("SELECT COUNT(*) FROM fpl_players").fetchone()[0],
        }

        return {"status": "ok", "collector_runs": status, "table_counts": counts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/football-data/{league_code}")
async def sync_football_data(
    league_code: str,
    season: str = "2025",
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Sync matches and teams from football-data.org for a specific league."""
    try:
        from backend.collectors.football_data import sync_league
        result = sync_league(conn, league_code.upper(), season)
        return {"status": "ok", "league": league_code, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/football-data")
async def sync_all_football_data(
    season: str = "2025",
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Sync all supported leagues from football-data.org."""
    try:
        from backend.collectors.football_data import sync_all_leagues
        result = sync_all_leagues(conn, season)
        return {"status": "ok", "results": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/fpl")
async def sync_fpl(
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Sync Fantasy Premier League data (players, fixtures, history)."""
    try:
        from backend.collectors.fpl_api import sync_fpl_data
        result = sync_fpl_data(conn)
        return {"status": "ok", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/fbref/{league_code}")
async def sync_fbref_league(
    league_code: str,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Scrape and sync player season stats from FBref for a specific league.

    Valid league codes: PL, PD, BL1, SA, FL1, KL1
    Note: FBref rate-limits aggressively; this may take 10-30 seconds.
    """
    try:
        from backend.collectors.fbref import sync_fbref_league as _sync
        result = _sync(conn, league_code.upper())
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/fbref")
async def sync_all_fbref(
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Scrape and sync player season stats from FBref for all leagues.

    Note: Uses 5s delay between leagues. Full sync takes several minutes.
    """
    try:
        from backend.collectors.fbref import sync_all_fbref as _sync_all
        result = _sync_all(conn)
        return {"status": "ok", "results": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/transfermarkt/{league_code}")
async def sync_transfermarkt_league(
    league_code: str,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Scrape and sync player market values from Transfermarkt for a specific league.

    Valid league codes: PL, PD, BL1, SA, FL1
    Note: Scrapes ~20 squad pages with 3s delay between requests (~1 min per league).
    """
    try:
        from backend.collectors.transfermarkt import sync_market_values
        result = sync_market_values(conn, league_code.upper())
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/transfermarkt")
async def sync_all_transfermarkt(
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Scrape and sync player market values from Transfermarkt for all leagues.

    Note: Full sync covers ~100 teams with 3s delay each. Takes ~5-10 minutes.
    """
    try:
        from backend.collectors.transfermarkt import sync_all_market_values
        result = sync_all_market_values(conn)
        return {"status": "ok", "results": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/european/{comp_code}")
async def sync_european_comp(
    comp_code: str,
    season: int = 2024,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Sync European competition (CL, EL, ECL) from API-Football."""
    try:
        from backend.collectors.api_football import sync_competition
        result = sync_competition(conn, comp_code.upper(), season)
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/european")
async def sync_all_european(
    season: int = 2024,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Sync all European competitions (CL, EL, ECL) from API-Football."""
    try:
        from backend.collectors.api_football import sync_all_european
        result = sync_all_european(conn, season)
        return {"status": "ok", "results": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/refresh-all")
async def refresh_all(
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Refresh all data sources: football-data.org matches (2024+2025) and FPL.

    FBref is excluded here (use /sync/fbref for that) because it takes several
    minutes and is best triggered separately or via the daily cron job.
    """
    results: dict[str, Any] = {}

    try:
        from backend.collectors.football_data import sync_all_leagues
        results["matches_2024"] = sync_all_leagues(conn, "2024")
    except Exception as e:
        results["matches_2024"] = {"error": str(e)}

    try:
        from backend.collectors.football_data import sync_all_leagues
        results["matches_2025"] = sync_all_leagues(conn, "2025")
    except Exception as e:
        results["matches_2025"] = {"error": str(e)}

    try:
        from backend.collectors.fpl_api import sync_fpl_data
        results["fpl"] = sync_fpl_data(conn)
    except Exception as e:
        results["fpl"] = {"error": str(e)}

    return {"status": "ok", "results": results}


@router.post("/update-ages")
async def update_player_ages(
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Update player ages from cached born years file."""
    try:
        import json
        from pathlib import Path as _P
        from datetime import date
        born_path = _P(__file__).parent.parent.parent / "data" / "player_born_years.json"
        if not born_path.exists():
            return {"status": "error", "detail": "player_born_years.json not found"}
        with open(born_path) as f:
            born_data = json.load(f)
        updated = 0
        for name, year in born_data.items():
            if year and year > 1970:
                dob = date(int(year), 7, 1)
                rows = conn.execute("UPDATE players SET date_of_birth = ? WHERE name = ? AND date_of_birth IS NULL", [dob, name])
                updated += rows.rowcount if hasattr(rows, 'rowcount') else 0
        # Also try partial name matching
        for name, year in born_data.items():
            if year and year > 1970:
                dob = date(int(year), 7, 1)
                try:
                    conn.execute("UPDATE players SET date_of_birth = ? WHERE name = ? AND date_of_birth IS NULL", [dob, name])
                except Exception:
                    pass
        count = conn.execute("SELECT COUNT(*) FROM players WHERE date_of_birth IS NOT NULL").fetchone()[0]
        return {"status": "ok", "players_with_age": count, "total_born_data": len(born_data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/create-tables")
async def create_tables(
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Create missing tables (match_events, match_statistics)."""
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS match_events (
                event_id INTEGER PRIMARY KEY,
                match_id INTEGER,
                elapsed INTEGER,
                extra_time INTEGER,
                type VARCHAR(20),
                detail VARCHAR(50),
                player_name VARCHAR(100),
                assist_name VARCHAR(100),
                team_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT current_timestamp
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS match_statistics (
                stat_id INTEGER PRIMARY KEY,
                match_id INTEGER,
                team_name VARCHAR(100),
                stat_type VARCHAR(50),
                stat_value VARCHAR(20),
                created_at TIMESTAMP DEFAULT current_timestamp
            )
        """)
        return {"status": "ok", "tables_created": ["match_events", "match_statistics"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/import-historical")
async def import_historical(
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Import historical matches from football-data.co.uk JSON file."""
    try:
        import json
        from pathlib import Path as _P
        from datetime import datetime

        path = _P(__file__).parent.parent.parent / "data" / "historical_matches.json"
        if not path.exists():
            return {"status": "error", "detail": "historical_matches.json not found"}

        with open(path) as f:
            matches = json.load(f)

        LEAGUE_NAMES = {"PL": "Premier League", "PD": "La Liga", "BL1": "Bundesliga", "SA": "Serie A", "FL1": "Ligue 1"}
        inserted = 0
        max_mid = conn.execute("SELECT COALESCE(MAX(match_id), 0) FROM matches").fetchone()[0]
        mid = max_mid + 1

        for m in matches:
            league_code = m["league"]
            season = m["season"]

            # Get or create league
            lr = conn.execute("SELECT league_id FROM leagues WHERE code = ? AND season = ?", [league_code, season]).fetchone()
            if not lr:
                max_lid = conn.execute("SELECT COALESCE(MAX(league_id), 0) FROM leagues").fetchone()[0]
                lid = max_lid + 1
                conn.execute("INSERT INTO leagues VALUES (?,?,?,?,?)",
                    [lid, league_code, LEAGUE_NAMES.get(league_code, league_code), "Europe", season])
            else:
                lid = lr[0]

            # Get or create teams
            for team_name in [m["home"], m["away"]]:
                tr = conn.execute("SELECT team_id FROM teams WHERE name = ? AND league_id = ?", [team_name, lid]).fetchone()
                if not tr:
                    max_tid = conn.execute("SELECT COALESCE(MAX(team_id), 0) FROM teams").fetchone()[0]
                    conn.execute("INSERT INTO teams VALUES (?,?,?,?,?)",
                        [max_tid + 1, team_name, team_name[:3].upper(), None, lid])

            home_row = conn.execute("SELECT team_id FROM teams WHERE name = ? AND league_id = ?", [m["home"], lid]).fetchone()
            away_row = conn.execute("SELECT team_id FROM teams WHERE name = ? AND league_id = ?", [m["away"], lid]).fetchone()
            if not home_row or not away_row:
                continue

            # Parse date
            try:
                date_str = m.get("date", "")
                if "/" in date_str:
                    parts = date_str.split("/")
                    if len(parts[2]) == 4:
                        kickoff = datetime.strptime(date_str, "%d/%m/%Y")
                    else:
                        kickoff = datetime.strptime(date_str, "%d/%m/%y")
                else:
                    kickoff = datetime.fromisoformat(date_str)
            except Exception:
                kickoff = datetime(2023, 1, 1)

            conn.execute(
                """INSERT INTO matches (match_id, league_id, season, matchday, kickoff, status,
                   home_team_id, away_team_id, home_score, away_score, home_xg, away_xg)
                   VALUES (?,?,?,0,?,?,?,?,?,?,NULL,NULL)""",
                [mid, lid, season, kickoff, "FINISHED", home_row[0], away_row[0],
                 m["home_score"], m["away_score"]])
            mid += 1
            inserted += 1

        return {"status": "ok", "matches_inserted": inserted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/train-model")
async def train_prediction_model(
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Train the XGBoost match prediction model on all finished matches."""
    try:
        from backend.models.match_predictor import train_model

        import numpy as np

        # Gather matches for a holdout accuracy check (last 20%)
        matches = conn.execute(
            """
            SELECT match_id, home_score, away_score
            FROM matches
            WHERE status = 'FINISHED' AND home_score IS NOT NULL
            ORDER BY kickoff ASC
            """
        ).fetchall()

        model = train_model(conn)

        # Compute accuracy on last 20% of matches
        from backend.models.match_predictor import build_features

        n_total = len(matches)
        split = int(n_total * 0.8)
        holdout = matches[split:]

        correct = 0
        evaluated = 0
        for match_id, home_score, away_score in holdout:
            features = build_features(match_id, conn)
            if features is None:
                continue
            features = np.nan_to_num(features, nan=0.0)
            pred_class = int(np.argmax(model.predict_proba(features.reshape(1, -1))[0]))
            if home_score > away_score:
                true_class = 0
            elif home_score == away_score:
                true_class = 1
            else:
                true_class = 2
            if pred_class == true_class:
                correct += 1
            evaluated += 1

        accuracy = round(correct / evaluated, 4) if evaluated else 0.0

        return {
            "status": "ok",
            "model_version": "xgb-v1",
            "trained_on": n_total,
            "holdout_matches": evaluated,
            "holdout_accuracy": accuracy,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/fixture-details/{match_id}")
async def sync_fixture_details_endpoint(
    match_id: int,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Fetch events and statistics for a specific match from API-Football."""
    try:
        if match_id < 1_000_000:
            raise HTTPException(status_code=400, detail="Only API-Football matches (id > 1000000) have events")
        from backend.collectors.api_football import sync_fixture_details
        fixture_id = match_id - 1_000_000
        result = sync_fixture_details(conn, fixture_id)
        return {"status": "ok", "match_id": match_id, **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
