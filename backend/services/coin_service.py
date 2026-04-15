"""Coin system business logic: registration, check-in, betting."""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any

import duckdb


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _next_id(conn: duckdb.DuckDBPyConnection, table: str, pk: str) -> int:
    row = conn.execute(f"SELECT COALESCE(MAX({pk}), 0) + 1 FROM {table}").fetchone()
    return int(row[0]) if row else 1


def register_user(username: str, conn: duckdb.DuckDBPyConnection, password: str = "") -> dict[str, Any]:
    """Create a new user with 50,000 signup coins."""
    existing = conn.execute(
        "SELECT user_id FROM users WHERE username = ?", [username]
    ).fetchone()
    if existing:
        raise ValueError(f"Username '{username}' is already taken")

    user_id = _next_id(conn, "users", "user_id")
    pw_hash = _hash_password(password) if password else None
    conn.execute(
        """
        INSERT INTO users (user_id, username, coins, created_at, password_hash, is_admin)
        VALUES (?, ?, 50000, current_timestamp, ?, false)
        """,
        [user_id, username, pw_hash],
    )

    tx_id = _next_id(conn, "coin_transactions", "tx_id")
    conn.execute(
        """
        INSERT INTO coin_transactions (tx_id, user_id, amount, type, description, created_at)
        VALUES (?, ?, 50000, 'signup_bonus', 'Welcome bonus coins', current_timestamp)
        """,
        [tx_id, user_id],
    )

    return {"user_id": user_id, "username": username, "coins": 50000}


def login_user(username: str, password: str, conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Authenticate user by username and password. Returns user data on success."""
    row = conn.execute(
        """SELECT user_id, username, coins, favorite_league, favorite_team_id,
                  last_checkin, password_hash, is_admin
           FROM users WHERE username = ?""",
        [username],
    ).fetchone()
    if not row:
        raise ValueError("Invalid username or password")

    user_id, uname, coins, fav_league, fav_team, last_checkin, stored_hash = row[:7]
    is_admin = bool(row[7]) if row[7] is not None else False

    # If no password set, allow login without password (legacy accounts)
    if stored_hash is not None:
        input_hash = _hash_password(password)
        if input_hash != stored_hash:
            raise ValueError("Invalid username or password")

    if hasattr(last_checkin, "isoformat"):
        last_checkin = last_checkin.isoformat()

    return {
        "user_id": user_id,
        "username": uname,
        "coins": coins,
        "favorite_league": fav_league,
        "favorite_team_id": fav_team,
        "last_checkin": last_checkin,
        "is_admin": is_admin,
    }


def daily_checkin(user_id: int, conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Award 100 coins for daily check-in. Raises if already checked in today."""
    row = conn.execute(
        "SELECT coins, last_checkin FROM users WHERE user_id = ?", [user_id]
    ).fetchone()
    if not row:
        raise ValueError(f"User {user_id} not found")

    coins, last_checkin = row[0], row[1]
    today = date.today()

    if last_checkin is not None:
        # last_checkin may be a date or string
        if isinstance(last_checkin, str):
            last_checkin_date = date.fromisoformat(last_checkin)
        elif isinstance(last_checkin, datetime):
            last_checkin_date = last_checkin.date()
        else:
            last_checkin_date = last_checkin

        if last_checkin_date == today:
            raise ValueError("Already checked in today")

    new_coins = coins + 100
    conn.execute(
        "UPDATE users SET coins = ?, last_checkin = ? WHERE user_id = ?",
        [new_coins, today.isoformat(), user_id],
    )

    tx_id = _next_id(conn, "coin_transactions", "tx_id")
    conn.execute(
        """
        INSERT INTO coin_transactions (tx_id, user_id, amount, type, description, created_at)
        VALUES (?, ?, 100, 'daily_checkin', 'Daily check-in bonus', current_timestamp)
        """,
        [tx_id, user_id],
    )

    return {"coins": new_coins, "bonus": 100, "streak": 1}


def get_odds(
    match_id: int, bet_type: str, conn: duckdb.DuckDBPyConnection
) -> float:
    """Return decimal odds for the given bet type from prediction model."""
    row = conn.execute(
        """
        SELECT prob_home_win, prob_draw, prob_away_win
        FROM match_predictions
        WHERE match_id = ?
        ORDER BY predicted_at DESC
        LIMIT 1
        """,
        [match_id],
    ).fetchone()

    if row and row[0] is not None:
        prob_home, prob_draw, prob_away = row[0], row[1], row[2]
        prob_map = {
            "home_win": prob_home,
            "draw": prob_draw,
            "away_win": prob_away,
        }
        prob = prob_map.get(bet_type)
        if prob and prob > 0:
            # Add house edge of 5%
            return round((1 / prob) * 0.95, 2)

    # Fallback odds if no prediction available
    fallback = {"home_win": 2.10, "draw": 3.20, "away_win": 3.50,
                "over_2.5": 1.85, "under_2.5": 1.95}
    return fallback.get(bet_type, 2.00)


def place_bet(
    user_id: int,
    match_id: int,
    bet_type: str,
    amount: int,
    conn: duckdb.DuckDBPyConnection,
) -> dict[str, Any]:
    """Validate and place a bet, deducting coins from user balance."""
    valid_bet_types = {"home_win", "draw", "away_win", "over_2.5", "under_2.5"}
    if bet_type not in valid_bet_types:
        raise ValueError(f"Invalid bet_type '{bet_type}'. Must be one of {valid_bet_types}")

    if amount < 100:
        raise ValueError("Minimum bet amount is 100 coins")

    # Check user exists and has sufficient coins
    user_row = conn.execute(
        "SELECT coins FROM users WHERE user_id = ?", [user_id]
    ).fetchone()
    if not user_row:
        raise ValueError(f"User {user_id} not found")

    coins = user_row[0]
    if coins < amount:
        raise ValueError(f"Insufficient coins. Balance: {coins}, Required: {amount}")

    # Check match exists and hasn't started
    match_row = conn.execute(
        "SELECT status, kickoff FROM matches WHERE match_id = ?", [match_id]
    ).fetchone()
    if not match_row:
        raise ValueError(f"Match {match_id} not found")

    status = match_row[0]
    if status not in ("SCHEDULED", "TIMED"):
        raise ValueError(f"Cannot bet on match with status '{status}'")

    # Check no existing bet on this match at all (one bet per match)
    existing_bet = conn.execute(
        "SELECT bet_id, bet_type FROM user_bets WHERE user_id = ? AND match_id = ? AND status = 'pending'",
        [user_id, match_id],
    ).fetchone()
    if existing_bet:
        raise ValueError(f"You already have a pending bet ({existing_bet[1]}) on this match. Cancel it first to place a new one.")

    odds = get_odds(match_id, bet_type, conn)

    # Deduct coins
    new_coins = coins - amount
    conn.execute(
        "UPDATE users SET coins = ? WHERE user_id = ?", [new_coins, user_id]
    )

    # Create bet record
    bet_id = _next_id(conn, "user_bets", "bet_id")
    conn.execute(
        """
        INSERT INTO user_bets (bet_id, user_id, match_id, bet_type, amount, odds, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', current_timestamp)
        """,
        [bet_id, user_id, match_id, bet_type, amount, odds],
    )

    # Record transaction
    tx_id = _next_id(conn, "coin_transactions", "tx_id")
    conn.execute(
        """
        INSERT INTO coin_transactions (tx_id, user_id, amount, type, description, match_id, created_at)
        VALUES (?, ?, ?, 'bet_place', ?, ?, current_timestamp)
        """,
        [tx_id, user_id, -amount, f"Bet on {bet_type} @ {odds}", match_id],
    )

    return {
        "bet_id": bet_id,
        "match_id": match_id,
        "bet_type": bet_type,
        "amount": amount,
        "odds": odds,
        "potential_payout": int(amount * odds),
        "coins_remaining": new_coins,
    }


def settle_bets(match_id: int, conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Settle all pending bets for a finished match."""
    match_row = conn.execute(
        "SELECT status, home_score, away_score FROM matches WHERE match_id = ?", [match_id]
    ).fetchone()
    if not match_row:
        raise ValueError(f"Match {match_id} not found")

    status, home_score, away_score = match_row
    if status != "FINISHED":
        raise ValueError(f"Match {match_id} is not finished yet (status: {status})")

    if home_score is None or away_score is None:
        raise ValueError(f"Match {match_id} has no score data")

    # Determine actual outcomes
    if home_score > away_score:
        outcome = "home_win"
    elif home_score < away_score:
        outcome = "away_win"
    else:
        outcome = "draw"

    total_goals = home_score + away_score
    over_25 = total_goals > 2.5

    won_types = {outcome}
    if over_25:
        won_types.add("over_2.5")
    else:
        won_types.add("under_2.5")

    # Fetch pending bets
    bets = conn.execute(
        "SELECT bet_id, user_id, bet_type, amount, odds FROM user_bets WHERE match_id = ? AND status = 'pending'",
        [match_id],
    ).fetchall()

    settled = 0
    for bet_id, user_id, bet_type, amount, odds in bets:
        won = bet_type in won_types
        payout = int(amount * odds) if won else 0
        new_status = "won" if won else "lost"

        conn.execute(
            "UPDATE user_bets SET status = ?, payout = ?, settled_at = current_timestamp WHERE bet_id = ?",
            [new_status, payout, bet_id],
        )

        tx_id = _next_id(conn, "coin_transactions", "tx_id")

        if won and payout > 0:
            # Payout includes original stake: odds 2.0 × 1000 = 2000 total returned
            conn.execute(
                "UPDATE users SET coins = coins + ? WHERE user_id = ?", [payout, user_id]
            )
            conn.execute(
                """
                INSERT INTO coin_transactions (tx_id, user_id, amount, type, description, match_id, created_at)
                VALUES (?, ?, ?, 'bet_win', ?, ?, current_timestamp)
                """,
                [tx_id, user_id, payout, f"Won {bet_type} @ {odds} → +{payout} coins", match_id],
            )
        else:
            # Record the loss transaction (coins already deducted at bet placement)
            conn.execute(
                """
                INSERT INTO coin_transactions (tx_id, user_id, amount, type, description, match_id, created_at)
                VALUES (?, ?, 0, 'bet_loss', ?, ?, current_timestamp)
                """,
                [tx_id, user_id, f"Lost {bet_type} @ {odds} → -{amount} coins", match_id],
            )

        settled += 1

    return {"match_id": match_id, "bets_settled": settled, "outcome": outcome}


def cancel_bet(user_id: int, bet_id: int, conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Cancel a pending bet and refund coins. Only works if match hasn't started."""
    bet_row = conn.execute(
        "SELECT user_id, match_id, bet_type, amount, odds, status FROM user_bets WHERE bet_id = ?",
        [bet_id],
    ).fetchone()
    if not bet_row:
        raise ValueError(f"Bet {bet_id} not found")

    owner_id, match_id, bet_type, amount, odds, status = bet_row
    if owner_id != user_id:
        raise ValueError("This bet does not belong to you")
    if status != "pending":
        raise ValueError(f"Cannot cancel bet with status '{status}'")

    # Check match hasn't started and is at least 1 hour away
    match_row = conn.execute(
        "SELECT status, kickoff FROM matches WHERE match_id = ?", [match_id]
    ).fetchone()
    if match_row and match_row[0] not in ("SCHEDULED", "TIMED"):
        raise ValueError("Cannot cancel - match has already started or finished")

    if match_row and match_row[1]:
        kickoff = match_row[1]
        if isinstance(kickoff, str):
            kickoff = datetime.fromisoformat(kickoff.replace("Z", "+00:00").split("+")[0])
        now = datetime.utcnow()
        time_until = (kickoff - now).total_seconds()
        if time_until < 3600:
            raise ValueError("Cannot cancel - less than 1 hour before kickoff")

    # Refund coins
    conn.execute(
        "UPDATE users SET coins = coins + ? WHERE user_id = ?", [amount, user_id]
    )
    conn.execute(
        "UPDATE user_bets SET status = 'cancelled' WHERE bet_id = ?", [bet_id]
    )

    tx_id = _next_id(conn, "coin_transactions", "tx_id")
    conn.execute(
        """INSERT INTO coin_transactions (tx_id, user_id, amount, type, description, match_id, created_at)
           VALUES (?, ?, ?, 'bet_cancel', ?, ?, current_timestamp)""",
        [tx_id, user_id, amount, f"Cancelled {bet_type} @ {odds} → refund +{amount}", match_id],
    )

    new_coins = conn.execute("SELECT coins FROM users WHERE user_id = ?", [user_id]).fetchone()
    return {"bet_id": bet_id, "refunded": amount, "coins": new_coins[0] if new_coins else 0}


def modify_bet(
    user_id: int, bet_id: int, new_bet_type: str, new_amount: int,
    conn: duckdb.DuckDBPyConnection,
) -> dict[str, Any]:
    """Cancel existing bet and place a new one. Must be 1h+ before kickoff."""
    # Cancel the old bet (validates ownership + time)
    cancel_result = cancel_bet(user_id, bet_id, conn)

    # Get match_id from the cancelled bet
    bet_row = conn.execute("SELECT match_id FROM user_bets WHERE bet_id = ?", [bet_id]).fetchone()
    if not bet_row:
        raise ValueError("Original bet not found")

    # Place new bet
    new_bet = place_bet(user_id, bet_row[0], new_bet_type, new_amount, conn)
    return {"cancelled": cancel_result, "new_bet": new_bet}
