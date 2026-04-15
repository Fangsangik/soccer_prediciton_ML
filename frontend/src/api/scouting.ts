import client from './client';
import type { PlayerProfile, SimilarityResult, UndervaluedPlayer } from '@/types/scouting';

export interface ScoutingSearchParams {
  q?: string;
  league?: string;
  position?: string;
  min_age?: number;
  max_age?: number;
  max_value?: number;
  limit?: number;
}

export const scoutingApi = {
  search: (params: ScoutingSearchParams): Promise<{ players: PlayerProfile[]; total: number }> =>
    client.get('/scouting/search', { params }) as Promise<{ players: PlayerProfile[]; total: number }>,

  profile: (id: number): Promise<PlayerProfile> =>
    client.get(`/scouting/players/${id}`) as Promise<PlayerProfile>,

  similar: (id: number, params?: { n?: number; position_lock?: boolean }): Promise<SimilarityResult> =>
    client.get(`/scouting/players/${id}/similar`, { params }) as Promise<SimilarityResult>,

  undervalued: (params?: { position?: string; league?: string; limit?: number }): Promise<UndervaluedPlayer[]> =>
    client.get('/scouting/undervalued', { params }) as Promise<UndervaluedPlayer[]>,
};
