export interface FPLPlayer {
  id: number;
  name: string;
  team: string;
  team_short: string;
  position: 'GKP' | 'DEF' | 'MID' | 'FWD';
  price: number;
  total_points: number;
  form: number;
  points_per_game: number;
  points_projected_gw: number;
  points_projected_5gw: number;
  fixture_difficulty: number[];
  ownership_pct: number;
  value_score: number;
  xg_per_90: number;
  xa_per_90: number;
  minutes_pct: number;
  injury_status: string | null;
  injury_note: string | null;
}

export interface OptimizeRequest {
  budget: number;
  horizon: number;
  existing_squad: number[];
  free_transfers: number;
  transfer_penalty: number;
  captain_pick: 'model' | number;
  chip: null | 'wildcard' | 'freehit' | 'bench_boost' | 'triple_captain';
  constraints: {
    must_include: number[];
    must_exclude: number[];
    max_team_players: number;
    formation: string | null;
  };
}

export interface OptimizeResult {
  squad: {
    starting_xi: Array<{
      player_id: number;
      name: string;
      team: string;
      position: string;
      price: number;
      projected_points: number;
      is_captain: boolean;
      is_vice_captain: boolean;
    }>;
    bench: Array<{
      player_id: number;
      name: string;
      team: string;
      position: string;
      price: number;
      projected_points: number;
      bench_order: number;
    }>;
    formation: string;
  };
  transfers: {
    out: Array<{ player_id: number; name: string; sell_price: number }>;
    in: Array<{ player_id: number; name: string; buy_price: number }>;
    cost: number;
    free_transfers_used: number;
  };
  projected_points: {
    gw_next: number;
    horizon_total: number;
    captain_points: number;
  };
  budget_remaining: number;
  solve_time_ms: number;
  solver_status: string;
}
