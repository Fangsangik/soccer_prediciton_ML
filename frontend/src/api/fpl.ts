import client from './client';
import type { FPLPlayer, OptimizeRequest, OptimizeResult } from '@/types/fpl';

export interface FPLPlayersParams {
  position?: string;
  team?: string;
  min_minutes?: number;
  max_price?: number;
  sort_by?: string;
  limit?: number;
}

export const fplApi = {
  players: (params?: FPLPlayersParams): Promise<{ players: FPLPlayer[]; total: number }> =>
    client.get('/fpl/players', { params }) as Promise<{ players: FPLPlayer[]; total: number }>,

  playerDetail: (id: number): Promise<FPLPlayer> =>
    client.get(`/fpl/players/${id}`) as Promise<FPLPlayer>,

  optimize: (request: OptimizeRequest): Promise<OptimizeResult> =>
    client.post('/fpl/optimize', request) as Promise<OptimizeResult>,

  captainPicks: (params?: { gw?: number }): Promise<FPLPlayer[]> =>
    client.get('/fpl/captain-picks', { params }) as Promise<FPLPlayer[]>,
};
