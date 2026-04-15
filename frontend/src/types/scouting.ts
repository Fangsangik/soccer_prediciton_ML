export interface PlayerProfile {
  player: {
    id: number;
    name: string;
    team: string;
    league: string;
    position: string;
    age: number;
    nationality: string;
    market_value_eur: number;
    contract_until: string;
  };
  stats_per_90: Record<string, number>;
  percentile_ranks: Record<string, number>;
}

export interface SimilarPlayer {
  player_id: number;
  name: string;
  team: string;
  league: string;
  position: string;
  age: number;
  similarity_score: number;
  market_value_eur: number;
  stats_per_90: Record<string, number>;
  percentile_comparison: Record<string, { reference: number; player: number }>;
}

export interface SimilarityResult {
  reference_player: { id: number; name: string };
  similar_players: SimilarPlayer[];
  embedding_2d: Array<{ player_id: number; x: number; y: number; label: string }>;
}

export interface UndervaluedPlayer {
  player_id: number;
  name: string;
  team: string;
  league: string;
  position: string;
  age: number;
  market_value_eur: number;
  performance_index: number;
  value_ratio: number;
  overperformance_pct: number;
  key_strengths: string[];
  key_weaknesses: string[];
}
