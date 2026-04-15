"""FPL squad optimizer using MILP (PuLP)."""
from __future__ import annotations

from typing import Any

import pandas as pd

try:
    from pulp import LpProblem, LpMaximize, LpVariable, lpSum, LpStatus, value as lp_value
    PULP_AVAILABLE = True
except ImportError:
    PULP_AVAILABLE = False


POSITION_COUNTS = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
XI_POSITIONS = {"GKP": 1, "DEF": (3, 5), "MID": (2, 5), "FWD": (1, 3)}


def optimize_squad(
    players_df: pd.DataFrame,
    budget: float,
    horizon: int,
    constraints: dict[str, Any],
    existing_squad: list[int] | None = None,
    free_transfers: int = 1,
    transfer_penalty: int = 4,
) -> dict[str, Any]:
    """Optimize an FPL squad using MILP.

    Args:
        players_df: DataFrame with columns: fpl_id, position, team_name, price,
                    projected_points, web_name, injury_status.
        budget: Total budget in FPL millions (e.g. 100.0).
        horizon: Number of gameweeks for projection.
        constraints: Dict of additional constraints (max_team_players, etc.).
        existing_squad: List of fpl_ids in current squad (for transfer calculations).
        free_transfers: Free transfers available.
        transfer_penalty: Points deducted per extra transfer.

    Returns:
        OptimizeResult dict with squad, starting_xi, captain, vice_captain,
        total_cost, projected_points, status.
    """
    if not PULP_AVAILABLE:
        return _greedy_fallback(players_df, budget, constraints)

    # Filter out unavailable players
    available = players_df[players_df["injury_status"] != "Unavailable"].copy()

    prob = LpProblem("FPL_Optimizer", LpMaximize)

    player_ids = available["fpl_id"].tolist()
    x = {pid: LpVariable(f"x_{pid}", cat="Binary") for pid in player_ids}

    # Helper lookups
    def get_val(pid: int, col: str) -> Any:
        rows = available.loc[available["fpl_id"] == pid, col]
        return rows.values[0] if len(rows) else 0

    # Objective: maximize projected points
    prob += lpSum(x[pid] * get_val(pid, "projected_points") for pid in player_ids)

    # Budget constraint
    prob += lpSum(x[pid] * get_val(pid, "price") for pid in player_ids) <= budget

    # Squad size = 15
    prob += lpSum(x[pid] for pid in player_ids) == 15

    # Position constraints
    max_team = constraints.get("max_team_players", 3)
    for pos, count in POSITION_COUNTS.items():
        pos_ids = available[available["position"] == pos]["fpl_id"].tolist()
        prob += lpSum(x[pid] for pid in pos_ids) == count

    # Max 3 per team
    for team in available["team_name"].unique():
        team_ids = available[available["team_name"] == team]["fpl_id"].tolist()
        prob += lpSum(x[pid] for pid in team_ids) <= max_team

    prob.solve()

    if LpStatus[prob.status] != "Optimal":
        return _greedy_fallback(players_df, budget, constraints)

    selected_ids = [pid for pid in player_ids if lp_value(x[pid]) and lp_value(x[pid]) > 0.5]
    selected_df = available[available["fpl_id"].isin(selected_ids)].copy()

    # Pick starting XI
    starting_xi = _pick_starting_xi(selected_df)
    bench = [pid for pid in selected_ids if pid not in starting_xi]

    # Captain = highest projected points in starting XI
    xi_df = selected_df[selected_df["fpl_id"].isin(starting_xi)]
    captain_id = int(xi_df.sort_values("projected_points", ascending=False)["fpl_id"].iloc[0])
    vc_id = int(xi_df.sort_values("projected_points", ascending=False)["fpl_id"].iloc[1]) if len(xi_df) > 1 else captain_id

    total_cost = float(selected_df["price"].sum())
    # Captain points doubled
    cap_pts = float(selected_df[selected_df["fpl_id"] == captain_id]["projected_points"].values[0])
    total_pts = float(selected_df[selected_df["fpl_id"].isin(starting_xi)]["projected_points"].sum()) + cap_pts

    squad_list = _format_squad(selected_df, starting_xi, captain_id, vc_id)

    return {
        "status": "optimal",
        "squad": squad_list,
        "starting_xi": starting_xi,
        "bench": bench,
        "captain": captain_id,
        "vice_captain": vc_id,
        "total_cost": round(total_cost, 1),
        "budget_remaining": round(budget - total_cost, 1),
        "projected_points": round(total_pts, 2),
        "horizon": horizon,
    }


def _pick_starting_xi(squad_df: pd.DataFrame) -> list[int]:
    """Select best starting XI from squad (1 GKP, 3-5 DEF, 2-5 MID, 1-3 FWD)."""
    xi: list[int] = []

    # Always 1 GK
    gk = squad_df[squad_df["position"] == "GKP"].sort_values(
        "projected_points", ascending=False
    )
    xi.append(int(gk.iloc[0]["fpl_id"]))

    # Remaining outfield: best 10 respecting position limits
    outfield = squad_df[squad_df["position"] != "GKP"].sort_values(
        "projected_points", ascending=False
    )

    pos_limits = {"DEF": 5, "MID": 5, "FWD": 3}
    pos_mins = {"DEF": 3, "MID": 2, "FWD": 1}
    pos_counts: dict[str, int] = {"DEF": 0, "MID": 0, "FWD": 0}

    # First pass: fill minimums
    for _, row in outfield.iterrows():
        pos = row["position"]
        if pos_counts[pos] < pos_mins[pos] and len(xi) < 11:
            xi.append(int(row["fpl_id"]))
            pos_counts[pos] += 1

    # Second pass: fill to 11 greedily
    for _, row in outfield.iterrows():
        if len(xi) >= 11:
            break
        pid = int(row["fpl_id"])
        if pid in xi:
            continue
        pos = row["position"]
        if pos_counts[pos] < pos_limits[pos]:
            xi.append(pid)
            pos_counts[pos] += 1

    return xi


def _format_squad(
    df: pd.DataFrame,
    starting_xi: list[int],
    captain_id: int,
    vc_id: int,
) -> list[dict[str, Any]]:
    result = []
    for _, row in df.iterrows():
        pid = int(row["fpl_id"])
        result.append(
            {
                "fpl_id": pid,
                "web_name": row.get("web_name", ""),
                "position": row["position"],
                "team_name": row.get("team_name", ""),
                "price": float(row["price"]),
                "projected_points": float(row["projected_points"]),
                "is_starting": pid in starting_xi,
                "is_captain": pid == captain_id,
                "is_vice_captain": pid == vc_id,
            }
        )
    return result


def _greedy_fallback(
    players_df: pd.DataFrame,
    budget: float,
    constraints: dict[str, Any],
) -> dict[str, Any]:
    """Simple greedy fallback when PuLP is unavailable."""
    available = players_df[players_df["injury_status"] != "Unavailable"].copy()
    available = available.sort_values("projected_points", ascending=False)

    max_team = constraints.get("max_team_players", 3)
    squad: list[int] = []
    pos_counts = dict(POSITION_COUNTS)
    team_counts: dict[str, int] = {}
    cost = 0.0

    remaining = dict(POSITION_COUNTS)

    for _, row in available.iterrows():
        if sum(remaining.values()) == 0:
            break
        pid = int(row["fpl_id"])
        pos = row["position"]
        team = row["team_name"]
        price = float(row["price"])

        if remaining.get(pos, 0) == 0:
            continue
        if team_counts.get(team, 0) >= max_team:
            continue
        if cost + price > budget:
            continue

        squad.append(pid)
        remaining[pos] -= 1
        team_counts[team] = team_counts.get(team, 0) + 1
        cost += price

    selected_df = available[available["fpl_id"].isin(squad)]
    starting_xi = _pick_starting_xi(selected_df)
    captain_id = int(
        selected_df[selected_df["fpl_id"].isin(starting_xi)]
        .sort_values("projected_points", ascending=False)["fpl_id"]
        .iloc[0]
    ) if len(starting_xi) > 0 else squad[0]
    vc_id = captain_id

    return {
        "status": "greedy",
        "squad": _format_squad(selected_df, starting_xi, captain_id, vc_id),
        "starting_xi": starting_xi,
        "bench": [p for p in squad if p not in starting_xi],
        "captain": captain_id,
        "vice_captain": vc_id,
        "total_cost": round(cost, 1),
        "budget_remaining": round(budget - cost, 1),
        "projected_points": round(
            float(selected_df[selected_df["fpl_id"].isin(starting_xi)]["projected_points"].sum()), 2
        ),
        "horizon": 1,
    }
