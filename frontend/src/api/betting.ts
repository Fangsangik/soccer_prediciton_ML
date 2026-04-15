import client from './client';
import type { BettingLine, EVResult, ValueBet } from '@/types/betting';

export interface ValueBetsParams {
  league?: string;
  min_ev?: number;
  min_edge?: number;
  markets?: string[];
  limit?: number;
}

export const bettingApi = {
  calculateEV: (matchId: number, lines: BettingLine[]): Promise<EVResult[]> =>
    client.post('/betting/ev', { match_id: matchId, lines }) as Promise<EVResult[]>,

  valueBets: (params?: ValueBetsParams): Promise<{ bets: ValueBet[]; total: number }> =>
    client.get('/betting/value-bets', { params }) as Promise<{ bets: ValueBet[]; total: number }>,
};
