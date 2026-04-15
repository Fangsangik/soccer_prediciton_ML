import { createContext, useContext, useState, useMemo, type ReactNode } from 'react';

interface LeagueContextValue {
  league: string;
  setLeague: (v: string) => void;
  season: string;
  setSeason: (v: string) => void;
  /** Season in API format: "2025/26" → "2025-26" */
  apiSeason: string;
}

const LeagueContext = createContext<LeagueContextValue>({
  league: 'PL',
  setLeague: () => {},
  season: '2024/25',
  setSeason: () => {},
  apiSeason: '2024-25',
});

export function LeagueProvider({ children }: { children: ReactNode }) {
  const [league, setLeague] = useState('PL');
  const [season, setSeason] = useState('2025/26');

  const apiSeason = useMemo(() => season.replace('/', '-'), [season]);

  return (
    <LeagueContext.Provider value={{ league, setLeague, season, setSeason, apiSeason }}>
      {children}
    </LeagueContext.Provider>
  );
}

export function useLeague() {
  return useContext(LeagueContext);
}
