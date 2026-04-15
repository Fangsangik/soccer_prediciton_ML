"""Model calibration metrics: Brier score, accuracy."""
from __future__ import annotations

from typing import Any


def brier_score(predictions: list[dict[str, Any]], actuals: list[str]) -> float:
    """Calculate Brier score for match outcome predictions.

    Lower is better. A perfect model scores 0, random ~0.67 for 3 outcomes.

    Args:
        predictions: List of dicts each with keys home_win, draw, away_win (probabilities).
        actuals: List of outcome strings: "home_win" | "draw" | "away_win".

    Returns:
        Mean Brier score as a float.
    """
    if not predictions or len(predictions) != len(actuals):
        return float("nan")

    total = 0.0
    for pred, actual in zip(predictions, actuals):
        p_home = pred.get("home_win", pred.get("probabilities", {}).get("home_win", 0))
        p_draw = pred.get("draw", pred.get("probabilities", {}).get("draw", 0))
        p_away = pred.get("away_win", pred.get("probabilities", {}).get("away_win", 0))

        o_home = 1.0 if actual == "home_win" else 0.0
        o_draw = 1.0 if actual == "draw" else 0.0
        o_away = 1.0 if actual == "away_win" else 0.0

        total += (p_home - o_home) ** 2 + (p_draw - o_draw) ** 2 + (p_away - o_away) ** 2

    return round(total / len(predictions), 6)


def accuracy(predictions: list[dict[str, Any]], actuals: list[str]) -> float:
    """Calculate prediction accuracy (fraction of correct top-1 predictions).

    Args:
        predictions: List of prediction dicts.
        actuals: List of actual outcome strings.

    Returns:
        Accuracy as a float (0-1).
    """
    if not predictions or len(predictions) != len(actuals):
        return float("nan")

    correct = 0
    for pred, actual in zip(predictions, actuals):
        probs = pred.get("probabilities", pred)
        p_home = probs.get("home_win", 0)
        p_draw = probs.get("draw", 0)
        p_away = probs.get("away_win", 0)

        predicted = max(
            [("home_win", p_home), ("draw", p_draw), ("away_win", p_away)],
            key=lambda x: x[1],
        )[0]

        if predicted == actual:
            correct += 1

    return round(correct / len(predictions), 6)


def log_loss(predictions: list[dict[str, Any]], actuals: list[str]) -> float:
    """Calculate mean log loss for outcome predictions.

    Args:
        predictions: List of prediction dicts.
        actuals: List of actual outcome strings.

    Returns:
        Mean log loss as a float.
    """
    import math

    if not predictions or len(predictions) != len(actuals):
        return float("nan")

    eps = 1e-15
    total = 0.0
    for pred, actual in zip(predictions, actuals):
        probs = pred.get("probabilities", pred)
        p = probs.get(actual, eps)
        p = max(eps, min(1 - eps, p))
        total += -math.log(p)

    return round(total / len(predictions), 6)
