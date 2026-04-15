export interface Team {
  id: number;
  name: string;
  short_name: string;
  crest_url: string;
}

export interface Match {
  id: number;
  league: string;
  season: string;
  matchday: number;
  kickoff: string;
  status: 'scheduled' | 'in_play' | 'finished' | 'postponed';
  home_team: Team;
  away_team: Team;
  score: { home: number; away: number } | null;
  xg: { home: number; away: number } | null;
}

export interface TeamForm {
  last_5: ('W' | 'D' | 'L')[];
  xg_for_avg: number;
  xg_against_avg: number;
  goals_scored_avg: number;
  goals_conceded_avg: number;
  clean_sheet_pct: number;
}

export interface MatchDetail {
  match: Match;
  head_to_head: {
    total_matches: number;
    home_wins: number;
    draws: number;
    away_wins: number;
  };
  home_form: TeamForm;
  away_form: TeamForm;
}

export interface Prediction {
  match_id: number;
  model_version: string;
  predicted_at: string;
  probabilities: {
    home_win: number;
    draw: number;
    away_win: number;
  };
  predicted_score: {
    home: number;
    away: number;
  };
  confidence: number;
  key_factors: Array<{
    factor: string;
    value: number;
    impact: number;
  }>;
  score_distribution: Record<string, number>;
}
