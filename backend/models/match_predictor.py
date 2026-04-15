"""Match prediction model using XGBoost multi-class classification."""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import xgboost as xgb
from scipy.stats import poisson

MODEL_PATH = Path(__file__).parent.parent.parent / "data" / "xgb_match_model.pkl"
MODEL_VERSION = "xgb-v1"

FEATURE_NAMES = [
    "Home form (win rate)",
    "Home goals/game",
    "Home conceded/game",
    "Home points/game",
    "Away form (win rate)",
    "Away goals/game",
    "Away conceded/game",
    "Away points/game",
    "Home PPG (at home)",
    "Home goals (at home)",
    "Home conceded (at home)",
    "Away PPG (away)",
    "Away goals (away)",
    "Away conceded (away)",
    "H2H home win rate",
    "H2H draw rate",
    "Rest day difference",
    "Home advantage",
]


def build_features(
    match_id: int, conn: duckdb.DuckDBPyConnection
) -> np.ndarray | None:
    """Extract feature vector for a match.

    Args:
        match_id: Match to build features for.
        conn: Active DuckDB connection.

    Returns:
        Float32 numpy array of length 18, or None if match not found.
    """
    row = conn.execute(
        "SELECT home_team_id, away_team_id, kickoff FROM matches WHERE match_id = ?",
        [match_id],
    ).fetchone()
    if not row:
        return None
    home_id, away_id, kickoff = row

    from backend.features.match_features import (
        get_head_to_head,
        get_home_away_splits,
        get_rest_days,
        get_team_form,
    )

    home_form = get_team_form(conn, home_id, n=10)
    away_form = get_team_form(conn, away_id, n=10)
    home_splits = get_home_away_splits(conn, home_id)
    away_splits = get_home_away_splits(conn, away_id)
    h2h = get_head_to_head(conn, home_id, away_id, n=10)

    home_rest = get_rest_days(conn, home_id, kickoff) or 7
    away_rest = get_rest_days(conn, away_id, kickoff) or 7

    home_n = max(1, len(home_form["results"]))
    away_n = max(1, len(away_form["results"]))
    home_home_m = max(1, home_splits["home"]["matches"])
    away_away_m = max(1, away_splits["away"]["matches"])
    h2h_m = max(1, h2h["matches"])

    features = [
        home_form["win_rate"],
        home_form["goals_scored"] / home_n,
        home_form["goals_conceded"] / home_n,
        home_form["points"] / home_n,
        away_form["win_rate"],
        away_form["goals_scored"] / away_n,
        away_form["goals_conceded"] / away_n,
        away_form["points"] / away_n,
        home_splits["home"]["points_per_game"],
        home_splits["home"]["goals_scored"] / home_home_m,
        home_splits["home"]["goals_conceded"] / home_home_m,
        away_splits["away"]["points_per_game"],
        away_splits["away"]["goals_scored"] / away_away_m,
        away_splits["away"]["goals_conceded"] / away_away_m,
        h2h["team1_win_rate"],
        h2h["draws"] / h2h_m,
        float(home_rest - away_rest),
        1.0,  # home advantage
    ]
    return np.array(features, dtype=np.float32)


def train_model(conn: duckdb.DuckDBPyConnection) -> xgb.XGBClassifier:
    """Train XGBoost model on all finished matches.

    Args:
        conn: Active DuckDB connection.

    Returns:
        Fitted XGBClassifier (also persisted to MODEL_PATH).
    """
    # fetchall() materialises the result before iterating so nested queries
    # on the same DuckDB connection don't conflict with an open cursor.
    matches: list[tuple[int, int, int]] = conn.execute(
        """
        SELECT match_id, home_score, away_score
        FROM matches
        WHERE status = 'FINISHED' AND home_score IS NOT NULL
        ORDER BY kickoff ASC
        """
    ).fetchall()

    X: list[np.ndarray] = []
    y: list[int] = []

    for match_id, home_score, away_score in matches:
        features = build_features(match_id, conn)
        if features is None:
            continue
        if np.any(np.isnan(features)):
            continue

        # Label: 0=Home Win, 1=Draw, 2=Away Win
        if home_score > away_score:
            label = 0
        elif home_score == away_score:
            label = 1
        else:
            label = 2

        X.append(features)
        y.append(label)

    X_arr = np.array(X)
    y_arr = np.array(y)

    print(f"Training on {len(X_arr)} matches...")
    print(
        f"Class distribution: H={sum(y_arr == 0)}, D={sum(y_arr == 1)}, A={sum(y_arr == 2)}"
    )

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        random_state=42,
    )
    model.fit(X_arr, y_arr)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    print(f"Model saved to {MODEL_PATH}")
    return model


_model: xgb.XGBClassifier | None = None


def _load_model() -> xgb.XGBClassifier | None:
    global _model
    if _model is None and MODEL_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            _model = pickle.load(f)
    return _model


def predict(match_id: int, conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Generate a prediction for a given match using XGBoost.

    Falls back to training the model on first call if no saved model exists.

    Args:
        match_id: The match to predict.
        conn: Active DuckDB connection.

    Returns:
        Prediction dict or error dict if match not found.
    """
    model = _load_model()
    if model is None:
        model = train_model(conn)
        global _model
        _model = model

    row = conn.execute(
        "SELECT home_team_id, away_team_id, status FROM matches WHERE match_id = ?",
        [match_id],
    ).fetchone()
    if not row:
        return {"error": f"Match {match_id} not found"}
    home_id, away_id, status = row

    features = build_features(match_id, conn)
    if features is None:
        return {"error": f"Match {match_id} not found"}

    features = np.nan_to_num(features, nan=0.0)

    probs = model.predict_proba(features.reshape(1, -1))[0]
    home_prob = float(probs[0])
    draw_prob = float(probs[1])
    away_prob = float(probs[2])

    # Score distribution via Poisson using home/away split goal rates
    from backend.features.match_features import get_home_away_splits

    home_splits = get_home_away_splits(conn, home_id)
    away_splits = get_home_away_splits(conn, away_id)

    h_matches = max(1, home_splits["home"]["matches"])
    a_matches = max(1, away_splits["away"]["matches"])
    home_lambda = max(0.5, home_splits["home"]["goals_scored"] / h_matches + 0.15)
    away_lambda = max(0.4, away_splits["away"]["goals_scored"] / a_matches)

    score_dist: dict[str, float] = {}
    for i in range(6):
        for j in range(6):
            p = float(poisson.pmf(i, home_lambda) * poisson.pmf(j, away_lambda))
            score_dist[f"{i}-{j}"] = round(p, 4)

    importances = model.feature_importances_
    top_indices = np.argsort(importances)[::-1][:5]
    key_factors = []
    for idx in top_indices:
        impact = float(features[idx]) * float(importances[idx])
        key_factors.append(
            {
                "factor": FEATURE_NAMES[idx],
                "value": round(float(features[idx]), 3),
                "impact": round(impact, 3),
            }
        )

    return {
        "match_id": match_id,
        "home_team_id": home_id,
        "away_team_id": away_id,
        "status": status,
        "model_version": MODEL_VERSION,
        "probabilities": {
            "home_win": round(home_prob, 4),
            "draw": round(draw_prob, 4),
            "away_win": round(away_prob, 4),
        },
        "predicted_score": {
            "home": round(home_lambda, 2),
            "away": round(away_lambda, 2),
        },
        "confidence": round(max(home_prob, draw_prob, away_prob), 4),
        "key_factors": key_factors,
        "score_distribution": score_dist,
    }
