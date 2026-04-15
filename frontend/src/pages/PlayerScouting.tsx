import { useState, useMemo, useEffect, useCallback } from 'react';
import { Search, SlidersHorizontal, TrendingUp, AlertCircle } from 'lucide-react';
import clsx from 'clsx';
import DataTable, { type Column } from '@/components/data/DataTable';
import RadarChart from '@/components/charts/RadarChart';
import ScatterPlot from '@/components/charts/ScatterPlot';
import PlayerAvatar from '@/components/common/PlayerAvatar';
import { Skeleton } from '@/components/data/Skeleton';
import client from '@/api/client';
import { useLeague } from '@/contexts/LeagueContext';
import type { PlayerProfile, SimilarityResult, UndervaluedPlayer } from '@/types/scouting';

// ─── Constants ────────────────────────────────────────────────────────────────

const RADAR_STAT_KEYS = ['xg', 'xa', 'shots', 'key_passes', 'progressive_carries', 'tackles', 'interceptions', 'aerials_won'] as const;
const RADAR_LABELS = ['xG', 'xA', 'Shots', 'Key Pass', 'Prog. Carries', 'Tackles', 'Interceptions', 'Aerials'];

const POSITIONS = ['ALL', 'FW', 'MF', 'DF', 'GK'] as const;
type PositionFilter = (typeof POSITIONS)[number];

function formatValue(eur: number): string {
  if (eur >= 1e8) return `€${(eur / 1e8).toFixed(0)}00M`;
  if (eur >= 1e6) return `€${(eur / 1e6).toFixed(0)}M`;
  return `€${(eur / 1e3).toFixed(0)}K`;
}

function toRadarData(profile: PlayerProfile) {
  return RADAR_STAT_KEYS.map((key, i) => ({
    stat: RADAR_LABELS[i],
    value: profile.percentile_ranks[key] ?? 0,
    fullMark: 100,
  }));
}

// ─── Undervalued Scanner columns ─────────────────────────────────────────────

const UNDERVALUED_COLUMNS: Column<UndervaluedPlayer & Record<string, unknown>>[] = [
  {
    key: 'name',
    label: 'Player',
    render: (v, row) => (
      <div className="flex items-center gap-2">
        <PlayerAvatar name={v as string} size="sm" position={row.position as string} />
        <div>
          <p className="text-xs font-medium text-slate-200">{v as string}</p>
          <p className="text-[10px] text-slate-500">{row.team as string} · {row.league as string}</p>
        </div>
      </div>
    ),
  },
  { key: 'position', label: 'Pos', align: 'center', render: (v) => <span className="text-xs text-slate-400">{v as string}</span> },
  { key: 'age', label: 'Age', align: 'center', render: (v) => <span className="font-mono text-xs text-slate-300">{v as number}</span> },
  {
    key: 'market_value_eur',
    label: 'Value',
    align: 'right',
    sortable: true,
    render: (v) => <span className="font-mono text-xs text-slate-300">{formatValue(v as number)}</span>,
  },
  {
    key: 'performance_index',
    label: 'Perf. Index',
    align: 'right',
    sortable: true,
    render: (v) => <span className="font-mono text-sm font-semibold text-emerald-400">{(v as number).toFixed(1)}</span>,
  },
  {
    key: 'value_ratio',
    label: 'Value Ratio',
    align: 'right',
    sortable: true,
    render: (v) => {
      const val = v as number;
      return (
        <span className={clsx('font-mono text-xs font-semibold', val >= 2 ? 'text-emerald-400' : val >= 1.5 ? 'text-amber-400' : 'text-slate-300')}>
          {val.toFixed(2)}x
        </span>
      );
    },
  },
  {
    key: 'overperformance_pct',
    label: 'Overperf.',
    align: 'right',
    sortable: true,
    render: (v) => <span className="font-mono text-xs text-sky-400">+{(v as number).toFixed(1)}%</span>,
  },
  {
    key: 'key_strengths',
    label: 'Strengths',
    render: (v) => (
      <div className="flex flex-wrap gap-1">
        {(v as string[]).slice(0, 3).map((s) => (
          <span key={s} className="text-[9px] bg-slate-700/60 text-slate-300 rounded px-1.5 py-0.5">{s}</span>
        ))}
      </div>
    ),
  },
];

// ─── Main component ───────────────────────────────────────────────────────────

export default function PlayerScouting() {
  const { league, apiSeason } = useLeague();

  const [search, setSearch] = useState('');
  const [posFilter, setPosFilter] = useState<PositionFilter>('ALL');
  const [scanPos, setScanPos] = useState<PositionFilter>('ALL');

  // Undervalued players (loaded on mount + league change)
  const [undervalued, setUndervalued] = useState<UndervaluedPlayer[]>([]);
  const [undervaluedLoading, setUndervaluedLoading] = useState(true);

  // Selected player profile
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);

  // Similar players / scatter
  const [similarResult, setSimilarResult] = useState<SimilarityResult | null>(null);
  const [similarLoading, setSimilarLoading] = useState(false);

  // Search results from API
  const [searchResults, setSearchResults] = useState<UndervaluedPlayer[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  // Fetch undervalued on mount + league/season change
  useEffect(() => {
    setUndervaluedLoading(true);
    setUndervalued([]);
    setSelectedId(null);
    setProfile(null);
    setSimilarResult(null);
    setSearch('');
    setSearchResults([]);

    (client.get('/scouting/undervalued', { params: { top_n: 30, season: apiSeason, league } }) as Promise<
      { undervalued_players: UndervaluedPlayer[]; count: number } | UndervaluedPlayer[]
    >)
      .then((res) => {
        const list = Array.isArray(res)
          ? res
          : (res as { undervalued_players?: UndervaluedPlayer[] }).undervalued_players ?? [];
        setUndervalued(list);
        if (list.length > 0) setSelectedId(list[0].player_id);
      })
      .catch(() => setUndervalued([]))
      .finally(() => setUndervaluedLoading(false));
  }, [league, apiSeason]);

  // Search players from API when search text changes
  useEffect(() => {
    if (search.length < 2) {
      setSearchResults([]);
      return;
    }
    setSearchLoading(true);
    const timer = setTimeout(() => {
      (client.get('/scouting/search', { params: { q: search, league, limit: 20 } }) as Promise<{ players: Array<{ player_id: number; name: string; position: string; team: string; league: string; goals: number; assists: number; xg_per_90: number; xa_per_90: number; minutes: number }> }>)
        .then((res) => {
          const mapped: UndervaluedPlayer[] = (res.players ?? []).map((p) => ({
            player_id: p.player_id,
            name: p.name,
            team: p.team,
            league: p.league,
            position: p.position,
            age: null as unknown as number,
            market_value_eur: 0,
            performance_index: p.xg_per_90 + p.xa_per_90,
            value_ratio: p.goals + p.assists,
            overperformance_pct: p.xg_per_90 + p.xa_per_90,
            key_strengths: [p.goals > 5 ? 'Goals' : '', p.assists > 3 ? 'Assists' : ''].filter(Boolean),
            key_weaknesses: [],
          }));
          setSearchResults(mapped);
        })
        .catch(() => setSearchResults([]))
        .finally(() => setSearchLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [search, league]);

  // Fetch profile when selectedId or season changes
  useEffect(() => {
    if (!selectedId) return;
    setProfileLoading(true);
    setProfile(null);
    setSimilarResult(null);

    (client.get(`/scouting/players/${selectedId}`, { params: { season: apiSeason } }) as Promise<PlayerProfile>)
      .then((res) => setProfile(res))
      .catch(() => setProfile(null))
      .finally(() => setProfileLoading(false));
  }, [selectedId, apiSeason]);

  const handleFindSimilar = useCallback(() => {
    if (!selectedId) return;
    setSimilarLoading(true);

    (client.post('/scouting/similar', {
      player_id: selectedId,
      position_filter: posFilter !== 'ALL' ? posFilter : undefined,
      top_n: 5,
      features: RADAR_STAT_KEYS,
    }) as Promise<SimilarityResult>)
      .then((res) => setSimilarResult(res))
      .catch(() => setSimilarResult(null))
      .finally(() => setSimilarLoading(false));
  }, [selectedId, posFilter]);

  // Use search results when searching, otherwise filter undervalued
  const filteredUndervalued = useMemo(() => {
    const source = search.length >= 2 ? searchResults : undervalued;
    return source.filter((p) => {
      const matchPos = scanPos === 'ALL' || (p.position && p.position.includes(scanPos));
      return matchPos;
    });
  }, [undervalued, searchResults, search, scanPos]);

  // Scatter data from similarity result
  const scatterData = useMemo(() => {
    if (!similarResult) return [];
    return similarResult.embedding_2d.map((d) => ({
      ...d,
      highlighted: d.player_id === selectedId,
    }));
  }, [similarResult, selectedId]);

  const radarData = profile ? toRadarData(profile) : [];

  return (
    <div className="space-y-5 max-w-7xl">
      {/* Search & Filters */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search players or teams..."
            className="w-full pl-8 pr-3 py-1.5 bg-slate-700 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-slate-500"
          />
        </div>
        {/* Position chips */}
        <div className="flex gap-1">
          {POSITIONS.map((pos) => (
            <button
              key={pos}
              onClick={() => setPosFilter(pos)}
              className={clsx(
                'px-2.5 py-1 text-xs font-medium rounded transition-colors',
                posFilter === pos
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'bg-slate-700/50 text-slate-400 border border-slate-700 hover:text-slate-200'
              )}
            >
              {pos}
            </button>
          ))}
        </div>
        <span className="text-xs text-slate-500 font-mono">
          {searchLoading ? 'Searching...' : `${filteredUndervalued.length} players`}
        </span>
      </div>

      {/* Player profile + similarity */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {/* Left: Profile */}
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg overflow-hidden">
          {profileLoading ? (
            <div className="p-4 space-y-3">
              <Skeleton className="h-16 rounded" />
              <Skeleton className="h-48 rounded" />
              <Skeleton className="h-32 rounded" />
            </div>
          ) : profile ? (
            <>
              {/* Header */}
              <div className="p-4 border-b border-slate-700/50 flex items-center gap-3">
                <PlayerAvatar name={profile.player.name} size="lg" position={profile.player.position} />
                <div className="flex-1 min-w-0">
                  <h2 className="text-base font-semibold text-slate-100 truncate">{profile.player.name}</h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {profile.player.team} · {profile.player.league} · {profile.player.position}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Age {profile.player.age} · {profile.player.nationality}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-xs text-slate-500">Market Value</p>
                  <p className="font-mono text-sm font-semibold text-amber-400">
                    {formatValue(profile.player.market_value_eur)}
                  </p>
                </div>
              </div>

              {/* Radar */}
              <div className="p-4">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Attribute Profile (percentile)</p>
                <RadarChart data={radarData} playerName={profile.player.name} />
              </div>

              {/* Stats grid */}
              <div className="px-4 pb-4">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Per 90 Stats</p>
                <div className="space-y-1.5">
                  {RADAR_STAT_KEYS.map((key, i) => {
                    const val = profile.stats_per_90[key] ?? 0;
                    const pct = profile.percentile_ranks[key] ?? 0;
                    return (
                      <div key={key} className="flex items-center gap-2">
                        <span className="text-[10px] text-slate-500 w-24 shrink-0">{RADAR_LABELS[i]}</span>
                        <div className="flex-1 h-1 bg-slate-700 rounded-full overflow-hidden">
                          <div
                            className={clsx('h-full rounded-full', pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-sky-500' : 'bg-slate-500')}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="font-mono text-[10px] text-slate-300 w-8 text-right">{val.toFixed(2)}</span>
                        <span className="font-mono text-[10px] text-slate-500 w-6 text-right">{pct}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Find Similar button */}
              <div className="px-4 pb-4">
                <button
                  onClick={handleFindSimilar}
                  disabled={similarLoading}
                  className="w-full flex items-center justify-center gap-2 py-1.5 rounded text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 transition-colors disabled:opacity-50"
                >
                  <SlidersHorizontal className="w-3.5 h-3.5" />
                  {similarLoading ? 'Finding similar…' : 'Find Similar Players'}
                </button>
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-slate-500">
              <AlertCircle className="w-8 h-8 mb-2 text-slate-600" />
              <p className="text-xs">Select a player to view profile</p>
            </div>
          )}
        </div>

        {/* Right: Similarity / UMAP */}
        <div className="space-y-4">
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-200">Player Space (UMAP 2D)</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {scatterData.length > 0
                    ? 'Emerald = selected player. Click to select.'
                    : 'Click "Find Similar Players" to generate map.'}
                </p>
              </div>
              <SlidersHorizontal className="w-3.5 h-3.5 text-slate-500" />
            </div>
            {similarLoading ? (
              <Skeleton className="h-48 rounded" />
            ) : scatterData.length > 0 ? (
              <ScatterPlot
                data={scatterData}
                onPlayerClick={(id) => setSelectedId(id)}
              />
            ) : (
              <div className="h-48 flex items-center justify-center text-slate-600 text-xs border border-dashed border-slate-700 rounded">
                No similarity data yet
              </div>
            )}
          </div>

          {/* Similar players list */}
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Similar Players</h3>
            {similarLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 rounded" />)}
              </div>
            ) : similarResult && similarResult.similar_players.length > 0 ? (
              <div className="space-y-2">
                {similarResult.similar_players.slice(0, 5).map((p) => (
                  <button
                    key={p.player_id}
                    onClick={() => setSelectedId(p.player_id)}
                    className="w-full flex items-center gap-3 p-2 rounded hover:bg-slate-700/40 transition-colors text-left"
                  >
                    <PlayerAvatar name={p.name} size="sm" position={p.position} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-slate-200 truncate">{p.name}</p>
                      <p className="text-[10px] text-slate-500">{p.team} · {p.position}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-mono text-xs text-emerald-400">{(p.similarity_score * 100).toFixed(0)}%</p>
                      <p className="text-[10px] text-slate-600">similar</p>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-600 text-center py-4">
                Click "Find Similar Players" to discover matches
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Undervalued Scanner */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-semibold text-slate-200">Undervalued Scanner</h2>
          </div>
          {/* Position filter for scanner */}
          <div className="flex gap-1">
            {POSITIONS.map((pos) => (
              <button
                key={pos}
                onClick={() => setScanPos(pos)}
                className={clsx(
                  'px-2 py-0.5 text-xs rounded transition-colors',
                  scanPos === pos
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'text-slate-500 hover:text-slate-300'
                )}
              >
                {pos}
              </button>
            ))}
          </div>
        </div>

        {undervaluedLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 rounded" />)}
          </div>
        ) : filteredUndervalued.length === 0 ? (
          <div className="flex items-center gap-2 justify-center py-8 text-slate-500">
            <AlertCircle className="w-4 h-4" />
            <span className="text-xs">No undervalued players found</span>
          </div>
        ) : (
          <DataTable
            columns={UNDERVALUED_COLUMNS}
            data={filteredUndervalued as unknown as (UndervaluedPlayer & Record<string, unknown>)[]}
            rowKey={(r) => (r as unknown as UndervaluedPlayer).player_id}
            onRowClick={(r) => setSelectedId((r as unknown as UndervaluedPlayer).player_id)}
            compact
          />
        )}
      </div>
    </div>
  );
}
