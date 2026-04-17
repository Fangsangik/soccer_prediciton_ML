import { useState, useEffect } from 'react';
import clsx from 'clsx';
import { Trophy, Crown, TrendingDown, Shield, Loader2, BarChart3, Flame } from 'lucide-react';
import { useLeague } from '@/contexts/LeagueContext';
import client from '@/api/client';

// ─── Types ──────────────────────────────────────────────────────────────────

interface LeagueTeamSim {
  team_id: number;
  name: string;
  short_name: string;
  current_points: number;
  current_gd: number;
  played: number;
  title_probability: number;
  top4_probability: number;
  relegation_probability: number;
  predicted_points: number;
  most_likely_position: number;
}

interface LeagueSimResult {
  league: string;
  season: string;
  simulations: number;
  remaining_matches: number;
  teams: LeagueTeamSim[];
}

interface CLTeamSim {
  team_id: number;
  name: string;
  short_name: string;
  win_probability: number;
  semifinal_probability: number;
  quarterfinal_probability: number;
}

interface CLSimResult {
  league: string;
  season: string;
  simulations: number;
  remaining_knockout_matches: number;
  active_teams: number;
  bracket_generated?: boolean;
  teams: CLTeamSim[];
}

type TabType = 'league' | 'cl' | 'el' | 'ecl';

interface TabConfig {
  key: TabType;
  label: string;
  icon: typeof Trophy;
  activeColor: string;
  accentColor: string;
  endpoint: string;
  noDataMsg: string;
}

const TABS: TabConfig[] = [
  {
    key: 'league',
    label: 'League Title',
    icon: Crown,
    activeColor: 'bg-emerald-600',
    accentColor: 'emerald',
    endpoint: '/title-race/league',
    noDataMsg: 'No league data available for this season.',
  },
  {
    key: 'cl',
    label: 'Champions League',
    icon: Trophy,
    activeColor: 'bg-indigo-600',
    accentColor: 'indigo',
    endpoint: '/title-race/champions-league',
    noDataMsg: 'No Champions League data available for this season.',
  },
  {
    key: 'el',
    label: 'Europa League',
    icon: Shield,
    activeColor: 'bg-orange-600',
    accentColor: 'orange',
    endpoint: '/title-race/europa-league',
    noDataMsg: 'No Europa League data available. API plan upgrade may be required for EL data.',
  },
  {
    key: 'ecl',
    label: 'Conference League',
    icon: Shield,
    activeColor: 'bg-green-600',
    accentColor: 'green',
    endpoint: '/title-race/conference-league',
    noDataMsg: 'No Conference League data available. API plan upgrade may be required for ECL data.',
  },
];

// ─── Probability Bar ────────────────────────────────────────────────────────

function ProbBar({ value, color, max = 1 }: { value: number; color: string; max?: number }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="w-full h-2 bg-slate-700/50 rounded-full overflow-hidden">
      <div
        className={clsx('h-full rounded-full transition-all duration-700', color)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function PctLabel({ value }: { value: number }) {
  const pct = (value * 100);
  if (pct < 0.1) return <span className="text-slate-600 font-mono text-xs">&lt;0.1%</span>;
  return (
    <span className={clsx(
      'font-mono text-xs font-bold',
      pct >= 50 ? 'text-emerald-400' : pct >= 20 ? 'text-amber-400' : 'text-slate-400',
    )}>
      {pct.toFixed(1)}%
    </span>
  );
}

// ─── League Title Race Table ────────────────────────────────────────────────

function LeagueTitleTable({ data }: { data: LeagueSimResult }) {
  const maxTitle = Math.max(...data.teams.map(t => t.title_probability), 0.01);

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Simulations</div>
          <div className="text-lg font-bold text-slate-200 font-mono">{data.simulations.toLocaleString()}</div>
        </div>
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Remaining</div>
          <div className="text-lg font-bold text-slate-200 font-mono">{data.remaining_matches}</div>
          <div className="text-[10px] text-slate-500">matches left</div>
        </div>
        <div className="bg-slate-800/50 border border-emerald-700/30 rounded-lg p-3">
          <div className="text-[10px] uppercase tracking-wider text-emerald-500 mb-1">Favourite</div>
          <div className="text-lg font-bold text-emerald-400">{data.teams[0]?.name ?? '—'}</div>
          <div className="text-[10px] text-emerald-500/70">{((data.teams[0]?.title_probability ?? 0) * 100).toFixed(1)}%</div>
        </div>
        <div className="bg-slate-800/50 border border-red-700/30 rounded-lg p-3">
          <div className="text-[10px] uppercase tracking-wider text-red-500 mb-1">Most at Risk</div>
          <div className="text-lg font-bold text-red-400">
            {data.teams.filter(t => t.relegation_probability > 0).sort((a, b) => b.relegation_probability - a.relegation_probability)[0]?.name ?? '—'}
          </div>
          <div className="text-[10px] text-red-500/70">
            {((data.teams.filter(t => t.relegation_probability > 0).sort((a, b) => b.relegation_probability - a.relegation_probability)[0]?.relegation_probability ?? 0) * 100).toFixed(1)}% relegation
          </div>
        </div>
      </div>

      {/* Main table */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-slate-800 border-b border-slate-700">
              <th className="w-8 px-3 py-2.5 text-left text-slate-500 font-medium">#</th>
              <th className="px-3 py-2.5 text-left text-slate-500 font-medium">Team</th>
              <th className="w-12 px-2 py-2.5 text-center text-slate-500 font-medium">Pts</th>
              <th className="w-12 px-2 py-2.5 text-center text-slate-500 font-medium">GD</th>
              <th className="w-12 px-2 py-2.5 text-center text-slate-500 font-medium">P</th>
              <th className="w-20 px-2 py-2.5 text-center text-slate-500 font-medium">
                <div className="flex items-center justify-center gap-1">
                  <Crown className="w-3 h-3 text-amber-400" /> Title
                </div>
              </th>
              <th className="hidden md:table-cell w-28 px-2 py-2.5 text-center text-slate-500 font-medium">Title Prob</th>
              <th className="w-20 px-2 py-2.5 text-center text-slate-500 font-medium">
                <div className="flex items-center justify-center gap-1">
                  <Shield className="w-3 h-3 text-blue-400" /> Top 4
                </div>
              </th>
              <th className="w-20 px-2 py-2.5 text-center text-slate-500 font-medium">
                <div className="flex items-center justify-center gap-1">
                  <TrendingDown className="w-3 h-3 text-red-400" /> Rel.
                </div>
              </th>
              <th className="hidden md:table-cell w-16 px-2 py-2.5 text-center text-slate-500 font-medium">Pred Pts</th>
            </tr>
          </thead>
          <tbody>
            {data.teams.map((team, i) => {
              const isLeader = i === 0;
              const isRelegation = team.relegation_probability > 0.3;
              return (
                <tr
                  key={team.team_id}
                  className={clsx(
                    'border-b border-slate-700/30 hover:bg-slate-700/20 transition-colors',
                    isLeader && 'bg-amber-500/5',
                    isRelegation && 'bg-red-500/5',
                  )}
                >
                  <td className={clsx(
                    'px-3 py-2.5 font-mono font-bold',
                    isLeader ? 'text-amber-400' : 'text-slate-500',
                  )}>
                    {team.most_likely_position}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      {isLeader && <Flame className="w-3.5 h-3.5 text-amber-400" />}
                      <span className={clsx('font-medium', isLeader ? 'text-amber-200' : 'text-slate-200')}>
                        {team.name}
                      </span>
                      <span className="text-slate-600 text-[10px]">{team.short_name}</span>
                    </div>
                  </td>
                  <td className="text-center px-2 py-2.5 font-mono font-bold text-slate-200">{team.current_points}</td>
                  <td className={clsx(
                    'text-center px-2 py-2.5 font-mono text-xs',
                    team.current_gd > 0 ? 'text-emerald-400' : team.current_gd < 0 ? 'text-red-400' : 'text-slate-500',
                  )}>
                    {team.current_gd > 0 ? '+' : ''}{team.current_gd}
                  </td>
                  <td className="text-center px-2 py-2.5 font-mono text-slate-500">{team.played}</td>
                  <td className="text-center px-2 py-2.5"><PctLabel value={team.title_probability} /></td>
                  <td className="hidden md:table-cell px-2 py-2.5">
                    <ProbBar value={team.title_probability} max={maxTitle} color="bg-amber-500" />
                  </td>
                  <td className="text-center px-2 py-2.5"><PctLabel value={team.top4_probability} /></td>
                  <td className="text-center px-2 py-2.5">
                    {team.relegation_probability > 0 ? (
                      <span className={clsx(
                        'font-mono text-xs font-bold',
                        team.relegation_probability >= 0.5 ? 'text-red-400' : team.relegation_probability >= 0.2 ? 'text-orange-400' : 'text-slate-500',
                      )}>
                        {(team.relegation_probability * 100).toFixed(1)}%
                      </span>
                    ) : (
                      <span className="text-slate-700 text-xs">—</span>
                    )}
                  </td>
                  <td className="hidden md:table-cell text-center px-2 py-2.5 font-mono text-slate-400">{team.predicted_points}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── European Competition Table (CL / EL / ECL) ────────────────────────────

function EuropeanCompTable({ data, config }: { data: CLSimResult; config: TabConfig }) {
  const maxWin = Math.max(...data.teams.map(t => t.win_probability), 0.01);
  const accentMap: Record<string, { border: string; text: string; textLight: string; bar: string }> = {
    indigo: { border: 'border-indigo-700/30', text: 'text-indigo-400', textLight: 'text-indigo-300', bar: 'bg-indigo-500' },
    orange: { border: 'border-orange-700/30', text: 'text-orange-400', textLight: 'text-orange-300', bar: 'bg-orange-500' },
    green: { border: 'border-green-700/30', text: 'text-green-400', textLight: 'text-green-300', bar: 'bg-green-500' },
  };
  const accent = accentMap[config.accentColor] ?? accentMap.indigo;

  const visibleTeams = data.teams.filter(
    t => t.win_probability > 0 || t.semifinal_probability > 0 || t.quarterfinal_probability > 0
  );

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Active Teams</div>
          <div className="text-lg font-bold text-slate-200 font-mono">{data.active_teams}</div>
        </div>
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
            {data.bracket_generated ? 'Bracket' : 'Remaining KO'}
          </div>
          <div className="text-lg font-bold text-slate-200 font-mono">
            {data.bracket_generated ? 'Generated' : data.remaining_knockout_matches}
          </div>
          <div className="text-[10px] text-slate-500">
            {data.bracket_generated ? 'from league stage' : 'matches'}
          </div>
        </div>
        <div className={clsx('bg-slate-800/50 rounded-lg p-3 col-span-2 md:col-span-1 border', accent.border)}>
          <div className={clsx('text-[10px] uppercase tracking-wider mb-1', accent.text)}>Favourite</div>
          <div className={clsx('text-lg font-bold', accent.textLight)}>{data.teams[0]?.name ?? '—'}</div>
          <div className={clsx('text-[10px] opacity-70', accent.text)}>
            {((data.teams[0]?.win_probability ?? 0) * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Table */}
      {visibleTeams.length > 0 ? (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-800 border-b border-slate-700">
                <th className="w-8 px-3 py-2.5 text-left text-slate-500 font-medium">#</th>
                <th className="px-3 py-2.5 text-left text-slate-500 font-medium">Team</th>
                <th className="w-20 px-2 py-2.5 text-center text-slate-500 font-medium">
                  <div className="flex items-center justify-center gap-1">
                    <Trophy className="w-3 h-3 text-amber-400" /> Winner
                  </div>
                </th>
                <th className="hidden md:table-cell w-32 px-2 py-2.5 text-center text-slate-500 font-medium">Win Prob</th>
                <th className="w-20 px-2 py-2.5 text-center text-slate-500 font-medium">Semi</th>
                <th className="w-20 px-2 py-2.5 text-center text-slate-500 font-medium">Quarter</th>
              </tr>
            </thead>
            <tbody>
              {visibleTeams.map((team, i) => (
                <tr
                  key={team.team_id}
                  className={clsx(
                    'border-b border-slate-700/30 hover:bg-slate-700/20 transition-colors',
                    i === 0 && `${config.accentColor === 'indigo' ? 'bg-indigo-500/5' : config.accentColor === 'orange' ? 'bg-orange-500/5' : 'bg-green-500/5'}`,
                  )}
                >
                  <td className={clsx('px-3 py-2.5 font-mono font-bold', i === 0 ? accent.text : 'text-slate-500')}>
                    {i + 1}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      {i === 0 && <Trophy className="w-3.5 h-3.5 text-amber-400" />}
                      <span className={clsx('font-medium', i === 0 ? accent.textLight : 'text-slate-200')}>
                        {team.name}
                      </span>
                    </div>
                  </td>
                  <td className="text-center px-2 py-2.5"><PctLabel value={team.win_probability} /></td>
                  <td className="hidden md:table-cell px-3 py-2.5">
                    <ProbBar value={team.win_probability} max={maxWin} color={accent.bar} />
                  </td>
                  <td className="text-center px-2 py-2.5"><PctLabel value={team.semifinal_probability} /></td>
                  <td className="text-center px-2 py-2.5"><PctLabel value={team.quarterfinal_probability} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-12 text-slate-500 text-sm">
          {config.noDataMsg}
        </div>
      )}
    </div>
  );
}

// ─── Loading Skeleton ───────────────────────────────────────────────────────

function TableSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3 h-20 animate-pulse" />
        ))}
      </div>
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4 space-y-3">
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="h-8 bg-slate-700/30 rounded animate-pulse" />
        ))}
      </div>
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────

export default function TitleRace() {
  const { league, apiSeason } = useLeague();
  const [tab, setTab] = useState<TabType>('league');
  const [leagueData, setLeagueData] = useState<LeagueSimResult | null>(null);
  const [clData, setClData] = useState<CLSimResult | null>(null);
  const [elData, setElData] = useState<CLSimResult | null>(null);
  const [eclData, setEclData] = useState<CLSimResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const activeTab = TABS.find(t => t.key === tab)!;

  useEffect(() => {
    setLoading(true);
    setError(null);

    const fetchData = async () => {
      if (tab === 'league') {
        const res = await client.get('/title-race/league', {
          params: { league, season: apiSeason, simulations: 5000 },
        });
        setLeagueData(res as unknown as LeagueSimResult);
      } else if (tab === 'cl') {
        const res = await client.get('/title-race/champions-league', {
          params: { season: apiSeason, simulations: 5000 },
        });
        setClData(res as unknown as CLSimResult);
      } else if (tab === 'el') {
        const res = await client.get('/title-race/europa-league', {
          params: { season: apiSeason, simulations: 5000 },
        });
        setElData(res as unknown as CLSimResult);
      } else if (tab === 'ecl') {
        const res = await client.get('/title-race/conference-league', {
          params: { season: apiSeason, simulations: 5000 },
        });
        setEclData(res as unknown as CLSimResult);
      }
      setLoading(false);
    };

    fetchData().catch((err) => {
      setError(err.message || 'Failed to load simulation data');
      setLoading(false);
    });
  }, [league, apiSeason, tab]);

  const getCompData = (): CLSimResult | null => {
    if (tab === 'cl') return clData;
    if (tab === 'el') return elData;
    if (tab === 'ecl') return eclData;
    return null;
  };

  return (
    <div className="space-y-5 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-emerald-400" />
            Title Race Predictions
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">Monte Carlo simulation · 5,000 season simulations · Poisson goals + Elo ratings</p>
        </div>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 bg-slate-800/50 border border-slate-700/50 rounded-lg p-1 w-fit flex-wrap">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={clsx(
                'px-3 py-1.5 rounded-md text-xs font-medium transition-all',
                tab === t.key
                  ? `${t.activeColor} text-white shadow-sm`
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50',
              )}
            >
              <div className="flex items-center gap-1.5">
                <Icon className="w-3.5 h-3.5" />
                {t.label}
              </div>
            </button>
          );
        })}
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Running Monte Carlo simulation...
          </div>
          <TableSkeleton />
        </div>
      ) : error ? (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">
          {error}
        </div>
      ) : tab === 'league' && leagueData ? (
        <LeagueTitleTable data={leagueData} />
      ) : (tab === 'cl' || tab === 'el' || tab === 'ecl') && getCompData() ? (
        <EuropeanCompTable data={getCompData()!} config={activeTab} />
      ) : (
        <div className="text-center py-12 text-slate-500 text-sm">
          {activeTab.noDataMsg}
        </div>
      )}
    </div>
  );
}
