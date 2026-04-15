export interface BettingLine {
  market: '1X2' | 'over_under' | 'btts' | 'asian_handicap';
  selection: string;
  odds: number;
  bookmaker: string;
}

export interface EVResult {
  market: string;
  selection: string;
  odds: number;
  bookmaker: string;
  model_prob: number;
  implied_prob: number;
  ev: number;
  ev_pct: number;
  edge: number;
  kelly_fraction: number;
  verdict: 'strong_value' | 'value' | 'marginal' | 'no_value';
}

export interface ValueBet {
  match_id: number;
  home_team: string;
  away_team: string;
  kickoff: string;
  market: string;
  selection: string;
  best_odds: number;
  bookmaker: string;
  model_prob: number;
  ev_pct: number;
  edge: number;
  confidence: number;
}
