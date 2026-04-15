import { useState, useMemo, useEffect } from 'react';
import { Search, RefreshCw, ChevronDown, AlertCircle, Lock } from 'lucide-react';
import clsx from 'clsx';
import DataTable, { type Column } from '@/components/data/DataTable';
import StatCard from '@/components/data/StatCard';
import PlayerAvatar from '@/components/common/PlayerAvatar';
import { Skeleton } from '@/components/data/Skeleton';
import client from '@/api/client';
import { useLeague } from '@/contexts/LeagueContext';
import type { FPLPlayer, OptimizeResult } from '@/types/fpl';

// ─── FDR color ────────────────────────────────────────────────────────────────

function fdrColor(d: number): string {
  if (d <= 1) return 'bg-emerald-400 text-emerald-950';
  if (d === 2) return 'bg-emerald-600 text-emerald-100';
  if (d === 3) return 'bg-amber-500 text-amber-950';
  if (d === 4) return 'bg-red-500 text-red-50';
  return 'bg-red-700 text-red-50';
}

// ─── Pitch View ───────────────────────────────────────────────────────────────

interface PitchPlayerProps {
  name: string;
  team: string;
  price: number;
  pts: number;
  isCaptain: boolean;
  isVice: boolean;
}

function PitchPlayerCard({ name, team, price, pts, isCaptain, isVice }: PitchPlayerProps) {
  return (
    <div className="relative flex flex-col items-center gap-0.5">
      {(isCaptain || isVice) && (
        <span
          className={clsx(
            'absolute -top-1.5 -right-1.5 z-10 w-4 h-4 rounded-full text-[9px] font-bold flex items-center justify-center border',
            isCaptain
              ? 'bg-amber-500 text-amber-950 border-amber-300'
              : 'bg-slate-500 text-slate-100 border-slate-400'
          )}
        >
          {isCaptain ? 'C' : 'V'}
        </span>
      )}
      <div className="bg-slate-900/80 border border-slate-700/70 rounded px-2 py-1 text-center min-w-[52px]">
        <p className="text-[10px] font-semibold text-slate-100 leading-none truncate max-w-[52px]">{name.split('. ').pop()}</p>
        <p className="text-[9px] text-slate-500 mt-0.5">{team}</p>
        <p className="font-mono text-[9px] text-emerald-400 mt-0.5">{pts.toFixed(1)}pt</p>
        <p className="font-mono text-[9px] text-slate-600">£{price.toFixed(1)}</p>
      </div>
    </div>
  );
}

interface PitchViewProps {
  result: OptimizeResult;
}

function PitchView({ result }: PitchViewProps) {
  const { starting_xi, bench } = result.squad;

  const gk = starting_xi.filter((p) => p.position === 'GKP');
  const defs = starting_xi.filter((p) => p.position === 'DEF');
  const mids = starting_xi.filter((p) => p.position === 'MID');
  const fwds = starting_xi.filter((p) => p.position === 'FWD');

  const rows = [
    { label: 'GK', players: gk },
    { label: 'DEF', players: defs },
    { label: 'MID', players: mids },
    { label: 'FWD', players: fwds },
  ];

  return (
    <div className="relative rounded-lg overflow-hidden bg-emerald-950/20 border border-emerald-900/30"
      style={{ minHeight: 380 }}>
      {/* Pitch markings */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute left-0 right-0 top-1/2 border-t border-white/10" />
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-20 h-20 rounded-full border border-white/10" />
        <div className="absolute left-1/4 right-1/4 top-0 h-12 border-b border-x border-white/10" />
        <div className="absolute left-1/4 right-1/4 bottom-0 h-12 border-t border-x border-white/10" />
      </div>

      {/* Players */}
      <div className="relative z-10 p-4 flex flex-col gap-4 h-full">
        {rows.map(({ label, players }) => (
          <div key={label} className="flex items-center justify-center gap-3 flex-wrap">
            {players.map((p) => (
              <PitchPlayerCard
                key={p.player_id}
                name={p.name}
                team={p.team}
                price={p.price}
                pts={p.projected_points}
                isCaptain={p.is_captain}
                isVice={p.is_vice_captain}
              />
            ))}
          </div>
        ))}
      </div>

      {/* Bench */}
      <div className="relative z-10 border-t border-slate-700/50 bg-slate-900/50 p-3">
        <p className="text-[9px] font-semibold text-slate-500 uppercase tracking-wide mb-2">Bench</p>
        <div className="flex gap-2">
          {bench.map((p) => (
            <div key={p.player_id} className="bg-slate-800/60 border border-slate-700/50 rounded px-2 py-1 text-center min-w-[48px]">
              <p className="text-[10px] font-medium text-slate-300 truncate max-w-[48px]">{p.name.split('. ').pop()}</p>
              <p className="text-[9px] text-slate-500">{p.team}</p>
              <p className="font-mono text-[9px] text-slate-400">{p.projected_points.toFixed(1)}pt</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Result Summary ───────────────────────────────────────────────────────────

interface ResultSummaryProps {
  result: OptimizeResult;
}

function ResultSummary({ result }: ResultSummaryProps) {
  const { projected_points, budget_remaining, solver_status, transfers, squad } = result;
  const captain = squad.starting_xi.find((p) => p.is_captain);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <StatCard label="Next GW Proj." value={projected_points.gw_next.toFixed(1)} variant="positive" sub="pts" />
        <StatCard label="Horizon Total" value={projected_points.horizon_total.toFixed(1)} variant="default" sub="pts total" />
        <StatCard label="Captain Pts" value={projected_points.captain_points.toFixed(1)} variant="warning" sub={captain?.name ?? 'Captain'} />
        <StatCard label="Budget Left" value={`£${budget_remaining.toFixed(1)}m`} variant="default" sub="remaining" />
      </div>

      {/* Transfer summary */}
      {transfers.out.length > 0 && (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Transfers</p>
          <div className="space-y-1.5">
            {transfers.out.map((outP, i) => {
              const inP = transfers.in[i];
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="text-red-400 font-medium truncate">{outP.name}</span>
                  <span className="text-slate-600">→</span>
                  <span className="text-emerald-400 font-medium truncate">{inP?.name ?? '?'}</span>
                  {transfers.cost > 0 && i === 0 && (
                    <span className="text-amber-400 font-mono ml-auto shrink-0">-{transfers.cost}pt</span>
                  )}
                  {transfers.cost === 0 && (
                    <span className="text-slate-500 font-mono ml-auto shrink-0 text-[10px]">free</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Formation + status */}
      <div className="flex items-center justify-between bg-slate-800/30 border border-slate-700/40 rounded px-3 py-2">
        <div>
          <p className="text-xs text-slate-500">Formation</p>
          <p className="font-mono text-sm font-semibold text-slate-200">{squad.formation}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-500">Solver</p>
          <span className="text-xs font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded px-2 py-0.5">
            {solver_status.toUpperCase()}
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── Player Browser ───────────────────────────────────────────────────────────

type PositionTab = 'ALL' | 'GKP' | 'DEF' | 'MID' | 'FWD';
const POSITION_TABS: PositionTab[] = ['ALL', 'GKP', 'DEF', 'MID', 'FWD'];

const CHIP_OPTIONS = [
  { value: '', label: 'No chip' },
  { value: 'wildcard', label: 'Wildcard' },
  { value: 'freehit', label: 'Free Hit' },
  { value: 'bench_boost', label: 'Bench Boost' },
  { value: 'triple_captain', label: 'Triple Captain' },
];

function FDRStrip({ difficulties }: { difficulties: number[] }) {
  return (
    <div className="flex gap-0.5">
      {difficulties.map((d, i) => (
        <span
          key={i}
          className={clsx('w-3.5 h-3.5 rounded-sm text-[8px] font-bold flex items-center justify-center', fdrColor(d))}
        >
          {d}
        </span>
      ))}
    </div>
  );
}

const PLAYER_COLUMNS: Column<FPLPlayer & Record<string, unknown>>[] = [
  {
    key: 'name',
    label: 'Player',
    render: (v, row: FPLPlayer & Record<string, unknown>) => (
      <div className="flex items-center gap-2">
        <PlayerAvatar name={v as string} size="sm" position={row.position as string} />
        <div>
          <p className="text-xs font-medium text-slate-200">{v as string}</p>
          <p className="text-[10px] text-slate-500">{row.team_short as string}</p>
        </div>
        {(row.injury_status as string | null) && (
          <span className={clsx('text-[9px] px-1.5 py-0.5 rounded font-medium',
            row.injury_status === 'out' ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400'
          )}>
            {row.injury_status as string}
          </span>
        )}
      </div>
    ),
  },
  {
    key: 'price',
    label: 'Price',
    align: 'right',
    sortable: true,
    render: (v) => <span className="font-mono text-xs text-slate-300">£{(v as number).toFixed(1)}</span>,
  },
  {
    key: 'form',
    label: 'Form',
    align: 'right',
    sortable: true,
    render: (v) => {
      const val = v as number;
      return (
        <span className={clsx('font-mono text-xs', val >= 7 ? 'text-emerald-400' : val >= 5 ? 'text-amber-400' : 'text-slate-400')}>
          {val.toFixed(1)}
        </span>
      );
    },
  },
  {
    key: 'points_projected_gw',
    label: 'Proj. GW',
    align: 'right',
    sortable: true,
    render: (v) => <span className="font-mono text-xs text-slate-200">{(v as number).toFixed(1)}</span>,
  },
  {
    key: 'fixture_difficulty',
    label: 'FDR (5GW)',
    render: (v) => <FDRStrip difficulties={v as number[]} />,
  },
  {
    key: 'value_score',
    label: 'Value',
    align: 'right',
    sortable: true,
    render: (v) => {
      const val = v as number;
      return (
        <span className={clsx('font-mono text-xs', val >= 1.4 ? 'text-emerald-400' : val >= 1.1 ? 'text-amber-400' : 'text-slate-500')}>
          {val.toFixed(2)}
        </span>
      );
    },
  },
  {
    key: 'ownership_pct',
    label: 'Own%',
    align: 'right',
    sortable: true,
    render: (v) => <span className="font-mono text-xs text-slate-400">{(v as number).toFixed(1)}%</span>,
  },
];

// ─── Main component ───────────────────────────────────────────────────────────

export default function FPLOptimizer() {
  const { league } = useLeague();
  const isPL = league === 'PL';

  const [budget, setBudget] = useState('100.0');
  const [horizon, setHorizon] = useState(5);
  const [freeTransfers, setFreeTransfers] = useState(1);
  const [chip, setChip] = useState('');
  const [optimizing, setOptimizing] = useState(false);
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResult | null>(null);
  const [optimizeError, setOptimizeError] = useState<string | null>(null);

  const [posTab, setPosTab] = useState<PositionTab>('ALL');
  const [search, setSearch] = useState('');
  const [browserOpen, setBrowserOpen] = useState(true);

  const [players, setPlayers] = useState<FPLPlayer[]>([]);
  const [playersLoading, setPlayersLoading] = useState(true);
  const [gameweek, setGameweek] = useState<number>(29);

  // Only fetch FPL data when PL is selected
  useEffect(() => {
    if (!isPL) {
      setPlayers([]);
      setPlayersLoading(false);
      return;
    }
    setPlayersLoading(true);

    interface RawFPLPlayer {
      fpl_id?: number;
      id?: number;
      web_name?: string;
      name?: string;
      position: string;
      team_name?: string;
      team?: string;
      team_short?: string;
      price: number;
      total_points?: number;
      form?: number | string;
      points_per_game?: number | string;
      selected_by_pct?: number | string;
      injury_status?: string | null;
      injury_note?: string | null;
      // computed fields (may be absent)
      points_projected_gw?: number;
      points_projected_5gw?: number;
      fixture_difficulty?: number[];
      value_score?: number;
      xg_per_90?: number;
      xa_per_90?: number;
      minutes_pct?: number;
      ownership_pct?: number;
    }

    (client.get('/fpl/players', { params: { limit: 50 } }) as Promise<{ players: RawFPLPlayer[]; gameweek?: number; count?: number }>)
      .then((res) => {
        const mapped: FPLPlayer[] = (res.players ?? []).map((p) => ({
          id: p.fpl_id ?? p.id ?? 0,
          name: p.web_name ?? p.name ?? '',
          team: p.team_name ?? p.team ?? '',
          team_short: p.team_short ?? (p.team_name ?? p.team ?? '').slice(0, 3).toUpperCase(),
          position: (p.position ?? 'MID') as FPLPlayer['position'],
          price: p.price ?? 0,
          total_points: p.total_points ?? 0,
          form: typeof p.form === 'string' ? parseFloat(p.form) || 0 : (p.form ?? 0),
          points_per_game: typeof p.points_per_game === 'string' ? parseFloat(p.points_per_game) || 0 : (p.points_per_game ?? 0),
          points_projected_gw: p.points_projected_gw ?? (p.total_points ? p.total_points / 38 : 0),
          points_projected_5gw: p.points_projected_5gw ?? 0,
          fixture_difficulty: p.fixture_difficulty ?? [],
          ownership_pct: typeof p.selected_by_pct === 'string' ? parseFloat(p.selected_by_pct) || 0 : (p.selected_by_pct ?? p.ownership_pct ?? 0),
          value_score: p.value_score ?? (p.price > 0 ? (p.total_points ?? 0) / p.price : 0),
          xg_per_90: p.xg_per_90 ?? 0,
          xa_per_90: p.xa_per_90 ?? 0,
          minutes_pct: p.minutes_pct ?? 0,
          injury_status: p.injury_status ?? null,
          injury_note: p.injury_note ?? null,
        }));
        setPlayers(mapped);
        if (res.gameweek) setGameweek(res.gameweek);
      })
      .catch(() => setPlayers([]))
      .finally(() => setPlayersLoading(false));
  }, [isPL]);

  const filteredPlayers = useMemo(() => {
    return players.filter((p) => {
      const matchPos = posTab === 'ALL' || p.position === posTab;
      const matchSearch = p.name.toLowerCase().includes(search.toLowerCase()) ||
        p.team.toLowerCase().includes(search.toLowerCase());
      return matchPos && matchSearch;
    });
  }, [players, posTab, search]);

  const handleOptimize = () => {
    setOptimizing(true);
    setOptimizeError(null);

    const chipValue = chip === '' ? null : chip as 'wildcard' | 'freehit' | 'bench_boost' | 'triple_captain';

    (client.post('/fpl/optimize', {
      budget: parseFloat(budget),
      horizon,
      existing_squad: [],
      free_transfers: freeTransfers,
      transfer_penalty: 4,
      captain_pick: 'model',
      chip: chipValue,
      constraints: {
        must_include: [],
        must_exclude: [],
        max_team_players: 3,
        formation: null,
      },
    }) as Promise<OptimizeResult>)
      .then((res) => setOptimizeResult(res))
      .catch((err: Error) => setOptimizeError(err.message))
      .finally(() => setOptimizing(false));
  };

  if (!isPL) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-slate-500">
        <Lock className="w-12 h-12 mb-4 text-slate-600" />
        <p className="text-base font-semibold text-slate-300 mb-1">FPL Optimizer — Premier League Only</p>
        <p className="text-sm text-slate-500">Switch to Premier League (PL) to use the FPL Optimizer.</p>
      </div>
    );
  }

  return (
    <div className="space-y-5 max-w-7xl">
      {/* Optimizer Controls */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400 shrink-0">Budget</label>
          <div className="relative">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-500">£</span>
            <input
              type="number"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              step="0.1"
              min="80"
              max="110"
              className="pl-6 pr-2 py-1.5 w-20 bg-slate-700 border border-slate-600 rounded text-xs font-mono text-slate-200 focus:outline-none focus:border-slate-500"
            />
          </div>
          <span className="text-xs text-slate-600">m</span>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400 shrink-0">Horizon</label>
          <input
            type="range"
            min={1}
            max={10}
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="w-24 accent-emerald-500"
          />
          <span className="font-mono text-xs text-slate-300 w-6">{horizon}GW</span>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400 shrink-0">FTs</label>
          <input
            type="number"
            value={freeTransfers}
            onChange={(e) => setFreeTransfers(Number(e.target.value))}
            min={0}
            max={5}
            className="w-12 px-2 py-1.5 bg-slate-700 border border-slate-600 rounded text-xs font-mono text-slate-200 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400 shrink-0">Chip</label>
          <select
            value={chip}
            onChange={(e) => setChip(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded text-xs text-slate-300 px-2.5 py-1.5 focus:outline-none"
          >
            {CHIP_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <button
          onClick={handleOptimize}
          disabled={optimizing}
          className={clsx(
            'ml-auto flex items-center gap-2 px-4 py-1.5 rounded text-xs font-semibold transition-colors',
            optimizing
              ? 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 cursor-not-allowed'
              : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30'
          )}
        >
          <RefreshCw className={clsx('w-3.5 h-3.5', optimizing && 'animate-spin')} />
          {optimizing ? 'Optimizing…' : 'Optimize'}
        </button>
      </div>

      {/* Optimize error */}
      {optimizeError && (
        <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <p className="text-xs text-red-400">{optimizeError}</p>
        </div>
      )}

      {/* Main: pitch + summary */}
      {optimizing && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          <div className="xl:col-span-2">
            <Skeleton className="h-[440px] rounded-lg" />
          </div>
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16 rounded-lg" />)}
          </div>
        </div>
      )}

      {!optimizing && optimizeResult && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          {/* Pitch View */}
          <div className="xl:col-span-2">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
                Optimized Squad · GW{gameweek}
              </h2>
              <span className="text-xs text-slate-500 font-mono">{optimizeResult.squad.formation}</span>
            </div>
            <PitchView result={optimizeResult} />
          </div>

          {/* Result summary */}
          <div>
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-2">Summary</h2>
            <ResultSummary result={optimizeResult} />
          </div>
        </div>
      )}

      {!optimizing && !optimizeResult && (
        <div className="flex flex-col items-center justify-center py-12 text-slate-500 bg-slate-800/30 border border-slate-700/40 rounded-lg">
          <RefreshCw className="w-8 h-8 mb-3 text-slate-600" />
          <p className="text-sm">Configure your settings and click Optimize</p>
          <p className="text-xs mt-1 text-slate-600">The solver will find the optimal squad for your horizon</p>
        </div>
      )}

      {/* Player Browser */}
      <div>
        <button
          onClick={() => setBrowserOpen((o) => !o)}
          className="flex items-center gap-2 mb-3 group"
        >
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">Player Browser</h2>
          <ChevronDown
            className={clsx('w-3.5 h-3.5 text-slate-500 transition-transform', browserOpen ? '' : '-rotate-90')}
          />
        </button>

        {browserOpen && (
          <div className="space-y-3">
            {/* Browser controls */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex gap-1">
                {POSITION_TABS.map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setPosTab(tab)}
                    className={clsx(
                      'px-2.5 py-1 text-xs font-medium rounded transition-colors',
                      posTab === tab
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'bg-slate-700/50 text-slate-400 border border-slate-700 hover:text-slate-200'
                    )}
                  >
                    {tab}
                  </button>
                ))}
              </div>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search..."
                  className="pl-7 pr-3 py-1.5 w-48 bg-slate-700 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
                />
              </div>
              <span className="text-xs text-slate-500 font-mono">{filteredPlayers.length} players</span>
            </div>

            {playersLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10 rounded" />)}
              </div>
            ) : players.length === 0 ? (
              <div className="flex items-center gap-2 py-8 justify-center text-slate-500">
                <AlertCircle className="w-4 h-4" />
                <span className="text-xs">No player data available</span>
              </div>
            ) : (
              <DataTable
                columns={PLAYER_COLUMNS}
                data={filteredPlayers as unknown as (FPLPlayer & Record<string, unknown>)[]}
                rowKey={(r) => (r as unknown as FPLPlayer).id}
                compact
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
