"""Player similarity model using cosine similarity on feature vectors."""
from __future__ import annotations

from typing import Any

import numpy as np
import duckdb
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity

from backend.features.player_features import DEFAULT_FEATURES


def get_similar_players(
    player_id: int,
    filters: dict[str, Any],
    conn: duckdb.DuckDBPyConnection,
    season: str = "2024-25",
    top_n: int = 10,
) -> dict[str, Any]:
    """Find players most similar to the given player using cosine similarity.

    Args:
        player_id: Target player ID.
        filters: Dict of optional filters (position, min_minutes).
        conn: Active DuckDB connection.
        season: Season string.
        top_n: Number of similar players to return.

    Returns:
        Dict with similar_players list and embedding coordinates.
    """
    position_filter = filters.get("position")
    min_minutes = filters.get("min_minutes", 450)

    # Build query
    wheres = ["pss.season = ?", "pss.minutes_played >= ?"]
    params: list[Any] = [season, min_minutes]

    if position_filter:
        wheres.append("pl.position = ?")
        params.append(position_filter)

    col_expr = ", ".join(f"COALESCE(pss.{c}, 0.0)" for c in DEFAULT_FEATURES)

    rows = conn.execute(
        f"""
        SELECT pss.player_id, pl.name, pl.position, pl.team_id,
               t.name AS team_name, pss.minutes_played,
               {col_expr}
        FROM player_season_stats pss
        JOIN players pl ON pl.player_id = pss.player_id
        LEFT JOIN teams t ON t.team_id = pl.team_id
        WHERE {' AND '.join(wheres)}
        """,
        params,
    ).fetchall()

    if not rows:
        return {"error": "No players found matching filters", "similar_players": [], "embeddings": []}

    n_meta = 6  # player_id, name, position, team_id, team_name, minutes_played
    ids = [r[0] for r in rows]
    names = [r[1] for r in rows]
    positions = [r[2] for r in rows]
    team_names = [r[4] for r in rows]

    matrix = np.array([[r[n_meta + i] for i in range(len(DEFAULT_FEATURES))] for r in rows], dtype=float)

    if player_id not in ids:
        return {"error": f"Player {player_id} not found or has insufficient minutes", "similar_players": [], "embeddings": []}

    # Normalize
    scaler = StandardScaler()
    normed = scaler.fit_transform(matrix)

    target_idx = ids.index(player_id)
    target_vec = normed[target_idx].reshape(1, -1)

    # Cosine similarity
    sims = cosine_similarity(target_vec, normed)[0]

    # Get top_n excluding the player itself
    ranked = sorted(
        [(i, float(sims[i])) for i in range(len(ids)) if ids[i] != player_id],
        key=lambda x: x[1],
        reverse=True,
    )[:top_n]

    similar_players = [
        {
            "player_id": ids[i],
            "name": names[i],
            "position": positions[i],
            "team_name": team_names[i],
            "similarity": round(sim, 4),
        }
        for i, sim in ranked
    ]

    # 2D embedding via PCA (fallback for UMAP)
    n_components = min(2, len(rows) - 1, normed.shape[1])
    embeddings: list[dict[str, Any]] = []
    if n_components >= 2:
        try:
            pca = PCA(n_components=2, random_state=42)
            coords = pca.fit_transform(normed)

            # Include target + similar players in embedding
            include_ids = {player_id} | {ids[i] for i, _ in ranked}
            for idx, pid in enumerate(ids):
                if pid in include_ids:
                    embeddings.append(
                        {
                            "player_id": pid,
                            "name": names[idx],
                            "position": positions[idx],
                            "x": round(float(coords[idx, 0]), 4),
                            "y": round(float(coords[idx, 1]), 4),
                            "is_target": pid == player_id,
                        }
                    )
        except Exception:
            pass

    return {
        "target_player_id": player_id,
        "similar_players": similar_players,
        "embeddings": embeddings,
    }
