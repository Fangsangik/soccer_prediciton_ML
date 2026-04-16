"""Football Analytics API - FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routers import health, matches, predictions, betting, fpl, scouting, sync, user, standings
from backend.scheduler import setup_scheduler, shutdown_scheduler
from backend.middleware import global_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.db import init_db, get_db, close_db
    from backend.config import settings

    init_db()
    print("[startup] DB initialized. Server ready. Data syncs in background.")

    # Start scheduler (handles all syncing in background, non-blocking)
    setup_scheduler(lambda: get_db().cursor())

    yield

    shutdown_scheduler()
    close_db()


app = FastAPI(
    title="Football Analytics API",
    version="0.1.0",
    description="Match prediction, FPL optimization, and player scouting.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(Exception, global_exception_handler)

# Include all routers under /api/v1
API_PREFIX = "/api/v1"

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(matches.router, prefix=API_PREFIX)
app.include_router(predictions.router, prefix=API_PREFIX)
app.include_router(betting.router, prefix=API_PREFIX)
app.include_router(fpl.router, prefix=API_PREFIX)
app.include_router(scouting.router, prefix=API_PREFIX)
app.include_router(sync.router, prefix=API_PREFIX)
app.include_router(user.router, prefix=API_PREFIX)
app.include_router(standings.router, prefix=API_PREFIX)

# Serve frontend static files in production
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    from backend.config import settings

    uvicorn.run("backend.main:app", host="0.0.0.0", port=settings.API_PORT, reload=True)
