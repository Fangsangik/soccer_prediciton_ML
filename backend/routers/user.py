"""User management, coin system, and betting endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import duckdb

from backend.deps import get_database, get_current_user
from backend.auth import create_access_token
from backend.services.coin_service import (
    register_user,
    login_user,
    daily_checkin,
    place_bet,
    settle_bets,
    get_odds,
    cancel_bet,
    modify_bet,
)

router = APIRouter(prefix="/user", tags=["user"])


# ─── Request models ────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(default="", max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(default="", max_length=128)


class CheckinRequest(BaseModel):
    user_id: int


class BetRequest(BaseModel):
    user_id: int
    match_id: int
    bet_type: str
    amount: int = Field(..., ge=100)


class PreferencesRequest(BaseModel):
    user_id: int
    favorite_league: str | None = None
    favorite_team_id: int | None = None


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/register")
async def register(
    body: RegisterRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        result = register_user(body.username, conn, body.password)
        token = create_access_token(
            user_id=result["user_id"],
            username=result["username"],
            is_admin=result.get("is_admin", False),
        )
        return {**result, "token": token}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/login")
async def login(
    body: LoginRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        result = login_user(body.username, body.password, conn)
        token = create_access_token(
            user_id=result["user_id"],
            username=result["username"],
            is_admin=result.get("is_admin", False),
        )
        return {**result, "token": token}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/checkin")
async def checkin(
    body: CheckinRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return daily_checkin(body.user_id, conn)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        row = conn.execute(
            """
            SELECT user_id, username, coins, favorite_league, favorite_team_id,
                   created_at, last_checkin, is_admin
            FROM users WHERE user_id = ?
            """,
            [user_id],
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        last_checkin = row[6]
        if hasattr(last_checkin, "isoformat"):
            last_checkin = last_checkin.isoformat()

        return {
            "user_id": row[0],
            "username": row[1],
            "coins": row[2],
            "favorite_league": row[3],
            "favorite_team_id": row[4],
            "created_at": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
            "last_checkin": last_checkin,
            "is_admin": bool(row[7]) if row[7] is not None else False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/{user_id}/transactions")
async def get_transactions(
    user_id: int,
    limit: int = 50,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        rows = conn.execute(
            """
            SELECT tx_id, amount, type, description, match_id, created_at
            FROM coin_transactions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [user_id, limit],
        ).fetchall()

        transactions = [
            {
                "tx_id": r[0],
                "amount": r[1],
                "type": r[2],
                "description": r[3],
                "match_id": r[4],
                "created_at": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5]),
            }
            for r in rows
        ]

        return {"user_id": user_id, "transactions": transactions}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/bet")
async def create_bet(
    body: BetRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return place_bet(body.user_id, body.match_id, body.bet_type, body.amount, conn)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/{user_id}/bets")
async def get_bets(
    user_id: int,
    limit: int = 50,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        rows = conn.execute(
            """
            SELECT ub.bet_id, ub.match_id, ub.bet_type, ub.amount, ub.odds,
                   ub.status, ub.payout, ub.created_at, ub.settled_at,
                   ht.name AS home_team, awt.name AS away_team,
                   m.kickoff
            FROM user_bets ub
            LEFT JOIN matches m ON m.match_id = ub.match_id
            LEFT JOIN teams ht ON ht.team_id = m.home_team_id
            LEFT JOIN teams awt ON awt.team_id = m.away_team_id
            WHERE ub.user_id = ?
            ORDER BY ub.created_at DESC
            LIMIT ?
            """,
            [user_id, limit],
        ).fetchall()

        bets = [
            {
                "bet_id": r[0],
                "match_id": r[1],
                "bet_type": r[2],
                "amount": r[3],
                "odds": r[4],
                "status": r[5],
                "payout": r[6],
                "created_at": r[7].isoformat() if hasattr(r[7], "isoformat") else str(r[7]),
                "settled_at": r[8].isoformat() if r[8] and hasattr(r[8], "isoformat") else (str(r[8]) if r[8] else None),
                "home_team": r[9],
                "away_team": r[10],
                "kickoff": r[11].isoformat() if r[11] and hasattr(r[11], "isoformat") else (str(r[11]) if r[11] else None),
                "potential_payout": int(r[3] * r[4]),
            }
            for r in rows
        ]

        return {"user_id": user_id, "bets": bets}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/preferences")
async def set_preferences(
    body: PreferencesRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        row = conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?", [body.user_id]
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"User {body.user_id} not found")

        conn.execute(
            """
            UPDATE users
            SET favorite_league = ?, favorite_team_id = ?
            WHERE user_id = ?
            """,
            [body.favorite_league, body.favorite_team_id, body.user_id],
        )

        return {
            "user_id": body.user_id,
            "favorite_league": body.favorite_league,
            "favorite_team_id": body.favorite_team_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/{user_id}/odds/{match_id}")
async def get_match_odds(
    user_id: int,
    match_id: int,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    """Get model-derived odds for all bet types for a match."""
    try:
        bet_types = ["home_win", "draw", "away_win", "over_2.5", "under_2.5"]
        odds_map = {bt: get_odds(match_id, bt, conn) for bt in bet_types}
        return {"match_id": match_id, "odds": odds_map}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/settle/{match_id}")
async def settle_match_bets(
    match_id: int,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
) -> dict[str, Any]:
    try:
        return settle_bets(match_id, conn)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


class AdminGiveCoinsRequest(BaseModel):
    admin_user_id: int
    target_user_id: int
    amount: int = Field(..., ge=1)


class AdminResetUserRequest(BaseModel):
    admin_user_id: int
    target_user_id: int


class CancelBetRequest(BaseModel):
    user_id: int
    bet_id: int


class ModifyBetRequest(BaseModel):
    user_id: int
    bet_id: int
    new_bet_type: str
    new_amount: int = Field(..., ge=100)


@router.post("/bet/modify")
async def modify_user_bet(
    body: ModifyBetRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Modify a pending bet (cancel + re-place). Must be 1h+ before kickoff."""
    try:
        return modify_bet(body.user_id, body.bet_id, body.new_bet_type, body.new_amount, conn)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/bet/cancel")
async def cancel_user_bet(
    body: CancelBetRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Cancel a pending bet and refund coins. Only if match hasn't started."""
    try:
        return cancel_bet(body.user_id, body.bet_id, conn)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


def _check_admin(conn: duckdb.DuckDBPyConnection, user_id: int) -> None:
    """Verify that the given user is an admin. Raises HTTPException if not."""
    row = conn.execute(
        "SELECT is_admin FROM users WHERE user_id = ?", [user_id]
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    if not row[0]:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.post("/admin/give-coins")
async def admin_give_coins(
    body: AdminGiveCoinsRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Admin-only: give coins to any user."""
    try:
        if not current_user.get("is_admin"):
            raise HTTPException(status_code=403, detail="Admin access required")

        target = conn.execute(
            "SELECT coins FROM users WHERE user_id = ?", [body.target_user_id]
        ).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail=f"Target user {body.target_user_id} not found")

        new_coins = target[0] + body.amount
        conn.execute(
            "UPDATE users SET coins = ? WHERE user_id = ?",
            [new_coins, body.target_user_id],
        )

        from backend.services.coin_service import _next_id
        tx_id = _next_id(conn, "coin_transactions", "tx_id")
        conn.execute(
            """INSERT INTO coin_transactions (tx_id, user_id, amount, type, description, created_at)
               VALUES (?, ?, ?, 'admin_grant', 'Admin coin grant', current_timestamp)""",
            [tx_id, body.target_user_id, body.amount],
        )

        return {"target_user_id": body.target_user_id, "coins_added": body.amount, "new_balance": new_coins}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/admin/reset-user")
async def admin_reset_user(
    body: AdminResetUserRequest,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Admin-only: reset a user's coins to 50,000."""
    try:
        if not current_user.get("is_admin"):
            raise HTTPException(status_code=403, detail="Admin access required")

        target = conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?", [body.target_user_id]
        ).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail=f"Target user {body.target_user_id} not found")

        conn.execute(
            "UPDATE users SET coins = 50000 WHERE user_id = ?", [body.target_user_id]
        )

        from backend.services.coin_service import _next_id
        tx_id = _next_id(conn, "coin_transactions", "tx_id")
        conn.execute(
            """INSERT INTO coin_transactions (tx_id, user_id, amount, type, description, created_at)
               VALUES (?, ?, 50000, 'admin_reset', 'Admin coin reset to 50,000', current_timestamp)""",
            [tx_id, body.target_user_id],
        )

        return {"target_user_id": body.target_user_id, "coins": 50000}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/admin/all-users")
async def admin_list_users(
    admin_user_id: int,
    conn: duckdb.DuckDBPyConnection = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Admin-only: list all users."""
    try:
        if not current_user.get("is_admin"):
            raise HTTPException(status_code=403, detail="Admin access required")

        rows = conn.execute(
            "SELECT user_id, username, coins, is_admin, created_at FROM users ORDER BY user_id"
        ).fetchall()

        users = [
            {
                "user_id": r[0],
                "username": r[1],
                "coins": r[2],
                "is_admin": bool(r[3]) if r[3] is not None else False,
                "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
            }
            for r in rows
        ]
        return {"users": users}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
