import client from './client';
import type { Match, MatchDetail, Prediction } from '@/types/match';

export interface MatchListParams {
  league?: string;
  season?: string;
  matchday?: number;
  status?: string;
  limit?: number;
  offset?: number;
}

export const matchesApi = {
  list: (params?: MatchListParams): Promise<{ matches: Match[]; total: number }> =>
    client.get('/matches', { params }) as Promise<{ matches: Match[]; total: number }>,

  detail: (id: number): Promise<MatchDetail> =>
    client.get(`/matches/${id}`) as Promise<MatchDetail>,

  prediction: (id: number): Promise<Prediction> =>
    client.get(`/predictions/${id}`) as Promise<Prediction>,

  predictBatch: (ids: number[]): Promise<Prediction[]> =>
    client.post('/predictions/batch', { match_ids: ids }) as Promise<Prediction[]>,
};
