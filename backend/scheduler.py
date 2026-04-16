"""Smart polling scheduler with adaptive intervals + APScheduler for daily/weekly jobs."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

POLL_INTERVAL_IDLE = 1800       # 30 min when no matches
POLL_INTERVAL_PREMATCH = 300    # 5 min when match starts within 1 hour
POLL_INTERVAL_LIVE = 60         # 1 min during live matches

scheduler = AsyncIOScheduler()
_poll_task: asyncio.Task | None = None


def check_and_sync(conn) -> int:
    """Sync matches and return next poll interval in seconds."""
    now = datetime.utcnow()

    # Check for live matches
    live = conn.execute(
        "SELECT COUNT(*) FROM matches WHERE status IN ('IN_PLAY','PAUSED','HALFTIME')"
    ).fetchone()[0]

    # Check for upcoming matches (within 1 hour)
    upcoming = conn.execute(
        "SELECT COUNT(*) FROM matches WHERE status = 'SCHEDULED' AND kickoff BETWEEN ? AND ?",
        [now, now + timedelta(hours=1)],
    ).fetchone()[0]

    # Always sync football-data.org leagues (generous rate limit)
    # NOTE: current season (2025) only in poll loop. Previous season (2024) runs once daily.
    try:
        from backend.collectors.football_data import sync_all_leagues
        print("[scheduler] Starting match sync...")
        sync_all_leagues(conn, season="2025")
        print("[scheduler] Match sync complete.")
    except Exception as e:
        print(f"[scheduler] Match sync failed: {e}")

    # Sync European cups only during match times to save 100/day quota
    if live > 0 or upcoming > 0:
        try:
            from backend.collectors.api_football import sync_all_european
            print("[scheduler] Syncing European cups (live/upcoming detected)...")
            sync_all_european(conn, season=2024)
            print("[scheduler] European cups sync complete.")
        except Exception as e:
            print(f"[scheduler] European cups sync failed: {e}")

        # Sync fixture details for live matches (events & statistics)
        if live > 0:
            try:
                from backend.collectors.api_football import sync_fixture_details
                live_matches = conn.execute(
                    """SELECT match_id FROM matches
                       WHERE status IN ('IN_PLAY','PAUSED','HALFTIME')
                         AND match_id > 1000000""",
                ).fetchall()
                for (match_id,) in live_matches:
                    fixture_id = match_id - 1_000_000
                    try:
                        sync_fixture_details(conn, fixture_id)
                    except Exception as e:
                        print(f"[scheduler] Fixture details {fixture_id} failed: {e}")
            except Exception as e:
                print(f"[scheduler] Live fixture detail sync failed: {e}")

    if live > 0:
        print(f"[scheduler] {live} live match(es) detected -> polling every {POLL_INTERVAL_LIVE}s")
        return POLL_INTERVAL_LIVE
    elif upcoming > 0:
        print(f"[scheduler] {upcoming} upcoming match(es) within 1h -> polling every {POLL_INTERVAL_PREMATCH}s")
        return POLL_INTERVAL_PREMATCH

    print(f"[scheduler] No live/upcoming matches -> polling every {POLL_INTERVAL_IDLE}s")
    return POLL_INTERVAL_IDLE


def _sync_historical(conn, season: str) -> None:
    """Sync a single historical season. Used at startup for 2023/2024."""
    from backend.collectors.football_data import sync_all_leagues
    print(f"[scheduler] Starting historical sync for {season}...")
    sync_all_leagues(conn, season=season)
    print(f"[scheduler] Historical sync for {season} complete.")


async def smart_poll_loop(conn_factory: Callable) -> None:
    """Async loop with adaptive poll intervals. Runs sync in executor to avoid blocking."""
    await asyncio.sleep(10)  # Wait for server to fully start
    loop = asyncio.get_event_loop()
    while True:
        try:
            interval = await loop.run_in_executor(
                None, lambda: check_and_sync(conn_factory())
            )
        except Exception as e:
            print(f"[scheduler] Smart poll error: {e}")
            interval = POLL_INTERVAL_IDLE
        await asyncio.sleep(interval)


def setup_scheduler(conn_factory: Callable) -> None:
    """Configure smart polling loop + APScheduler for daily/weekly jobs."""

    # One-time startup sync for historical seasons (2023, 2024).
    # These are completed seasons so data doesn't change — only need to run
    # once per cold start (Render free tier wipes filesystem on restart).
    async def _startup_historical_sync():
        """Run historical season sync once at startup, in background."""
        await asyncio.sleep(15)  # Wait for main poll loop to finish first cycle
        loop = asyncio.get_event_loop()
        for season in ("2023", "2024"):
            try:
                await loop.run_in_executor(
                    None, lambda s=season: _sync_historical(conn_factory(), s)
                )
            except Exception as e:
                print(f"[scheduler] Startup historical sync {season} failed: {e}")

    loop = asyncio.get_event_loop()
    loop.create_task(_startup_historical_sync())
    print("[scheduler] Historical startup sync queued (2023, 2024)")

    # Start smart poll loop as asyncio task
    global _poll_task
    _poll_task = loop.create_task(smart_poll_loop(conn_factory))
    print("[scheduler] Smart poll loop started (adaptive intervals: 60s/300s/1800s)")

    # Keep APScheduler for FPL (6h), FBref (daily), Transfermarkt (weekly)
    @scheduler.scheduled_job("interval", hours=6, id="sync_fpl")
    def sync_fpl() -> None:
        conn = conn_factory()
        try:
            from backend.collectors.fpl_api import sync_fpl_data
            print("[scheduler] Starting FPL sync...")
            sync_fpl_data(conn)
            print("[scheduler] FPL sync complete.")
        except Exception as e:
            print(f"[scheduler] FPL sync failed: {e}")

    @scheduler.scheduled_job("cron", hour=4, id="sync_historical_2024")
    def sync_historical_2024() -> None:
        """Previous season (2024) syncs once a day. Historical reference data."""
        conn = conn_factory()
        try:
            from backend.collectors.football_data import sync_all_leagues
            print("[scheduler] Starting 2024 historical sync...")
            sync_all_leagues(conn, season="2024")
            print("[scheduler] 2024 historical sync complete.")
        except Exception as e:
            print(f"[scheduler] 2024 historical sync failed: {e}")

    @scheduler.scheduled_job("cron", hour=6, id="sync_fbref")
    def sync_fbref() -> None:
        conn = conn_factory()
        try:
            from backend.collectors.fbref import sync_all_fbref
            print("[scheduler] Starting FBref sync...")
            sync_all_fbref(conn)
            print("[scheduler] FBref sync complete.")
        except Exception as e:
            print(f"[scheduler] FBref sync failed: {e}")

    @scheduler.scheduled_job("cron", day_of_week="mon", hour=3, id="sync_transfermarkt")
    def sync_transfermarkt() -> None:
        conn = conn_factory()
        try:
            from backend.collectors.transfermarkt import sync_all_market_values
            print("[scheduler] Starting Transfermarkt market value sync...")
            sync_all_market_values(conn)
            print("[scheduler] Transfermarkt sync complete.")
        except Exception as e:
            print(f"[scheduler] Transfermarkt sync failed: {e}")

    scheduler.start()
    print("[scheduler] APScheduler started with jobs: sync_fpl (6h), sync_fbref (cron 06:00), sync_transfermarkt (mon 03:00)")


def shutdown_scheduler() -> None:
    """Shut down both the poll loop and APScheduler."""
    global _poll_task
    if _poll_task and not _poll_task.done():
        _poll_task.cancel()
    scheduler.shutdown(wait=False)
