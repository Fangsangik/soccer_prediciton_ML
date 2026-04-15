"""Player-level feature extraction functions."""
from __future__ import annotations

from typing import Any

import duckdb
import numpy as np

# Default feature columns used for the similarity vector
DEFAULT_FEATURES = [
    "xg_per_90",
    "xa_per_90",
    "shots_per_90",
    "key_passes_per_90",
    "progressive_carries_per_90",
    "progressive_passes_per_90",
    "tackles_per_90",
    "interceptions_per_90",
    "aerials_won_per_90",
    "dribbles_per_90",
    "pass_completion_pct",
]


def get_player_per90(
    conn: duckdb.DuckDBPyConnection,
    player_id: int,
    season: str = "2024-25",
) -> dict[str, Any] | None:
    """Return per-90 normalised stats for a player in a given season.

    Args:
        conn: Active DuckDB connection.
        player_id: Target player.
        season: Season string, e.g. ``"2024-25"``.

    Returns:
        Dict of stat name → value, or ``None`` if no record found.
    """
    row = conn.execute(
        """
        SELECT
            player_id, season, league_code,
            minutes_played, matches_played,
            goals, assists, xg, xa,
            xg_per_90, xa_per_90,
            shots_per_90, key_passes_per_90,
            progressive_carries_per_90, progressive_passes_per_90,
            tackles_per_90, interceptions_per_90,
            aerials_won_per_90, dribbles_per_90,
            pass_completion_pct
        FROM player_season_stats
        WHERE player_id = ? AND season = ?
        """,
        [player_id, season],
    ).fetchone()

    if not row:
        return None

    cols = [
        "player_id", "season", "league_code",
        "minutes_played", "matches_played",
        "goals", "assists", "xg", "xa",
        "xg_per_90", "xa_per_90",
        "shots_per_90", "key_passes_per_90",
        "progressive_carries_per_90", "progressive_passes_per_90",
        "tackles_per_90", "interceptions_per_90",
        "aerials_won_per_90", "dribbles_per_90",
        "pass_completion_pct",
    ]
    return dict(zip(cols, row))


def get_percentile_ranks(
    conn: duckdb.DuckDBPyConnection,
    player_id: int,
    season: str = "2024-25",
    position: str | None = None,
) -> dict[str, float] | None:
    """Return percentile ranks (0–100) for each per-90 stat versus peers.

    Peers are players in the same ``position`` with ≥ 450 minutes played.
    If *position* is ``None`` the player's own position is fetched automatically.

    Args:
        conn: Active DuckDB connection.
        player_id: Target player.
        season: Season string.
        position: Optional position filter (``"GK"``, ``"DEF"``, ``"MID"``, ``"FWD"``).

    Returns:
        Dict mapping stat name → percentile float (0–100), or ``None`` if not found.
    """
    if position is None:
        row = conn.execute(
            "SELECT position FROM players WHERE player_id = ?", [player_id]
        ).fetchone()
        if not row:
            return None
        position = row[0]

    stat_cols = [
        "xg_per_90", "xa_per_90", "shots_per_90", "key_passes_per_90",
        "progressive_carries_per_90", "progressive_passes_per_90",
        "tackles_per_90", "interceptions_per_90",
        "aerials_won_per_90", "dribbles_per_90", "pass_completion_pct",
    ]

    # Fetch all peers
    peers = conn.execute(
        f"""
        SELECT pss.player_id, {', '.join('pss.' + c for c in stat_cols)}
        FROM player_season_stats pss
        JOIN players pl ON pl.player_id = pss.player_id
        WHERE pss.season = ?
          AND pl.position = ?
          AND pss.minutes_played >= 450
        """,
        [season, position],
    ).fetchall()

    if not peers:
        return None

    # Build numpy arrays per column
    peer_ids = [r[0] for r in peers]
    data = np.array([[r[i + 1] or 0.0 for i in range(len(stat_cols))] for r in peers])

    if player_id not in peer_ids:
        return None

    idx = peer_ids.index(player_id)
    player_vals = data[idx]

    percentiles: dict[str, float] = {}
    for col_i, col in enumerate(stat_cols):
        col_data = data[:, col_i]
        val = player_vals[col_i]
        pct = float(np.sum(col_data <= val) / len(col_data) * 100)
        percentiles[col] = round(pct, 1)

    return percentiles


def get_player_feature_vector(
    conn: duckdb.DuckDBPyConnection,
    player_id: int,
    season: str = "2024-25",
    features: list[str] | None = None,
) -> np.ndarray | None:
    """Return a numpy feature vector for player similarity calculations.

    Missing stat values are filled with 0.  The vector is z-score normalised
    relative to all players in the same season who have ≥ 450 minutes.

    Args:
        conn: Active DuckDB connection.
        player_id: Target player.
        season: Season string.
        features: Optional list of column names to include.
                  Defaults to :data:`DEFAULT_FEATURES`.

    Returns:
        1-D ``np.ndarray`` of length ``len(features)``, or ``None`` if the
        player has no stats record.
    """
    features = features or DEFAULT_FEATURES

    col_expr = ", ".join(f"COALESCE({c}, 0.0)" for c in features)
    rows = conn.execute(
        f"""
        SELECT player_id, {col_expr}
        FROM player_season_stats
        WHERE season = ? AND minutes_played >= 450
        """,
        [season],
    ).fetchall()

    if not rows:
        return None

    ids = [r[0] for r in rows]
    if player_id not in ids:
        return None

    matrix = np.array([[r[i + 1] for i in range(len(features))] for r in rows], dtype=float)

    # Z-score normalise across all players
    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0)
    std[std == 0] = 1.0  # avoid division by zero
    normed = (matrix - mean) / std

    idx = ids.index(player_id)
    return normed[idx]
