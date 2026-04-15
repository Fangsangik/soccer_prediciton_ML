import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';
import {
  Calendar,
  TrendingUp,
  Users,
  Target,
  Crown,
  Zap,
  ArrowRight,
  AlertCircle,
  Star,
} from 'lucide-react';
import StatCard from '@/components/data/StatCard';
import ProbabilityBar from '@/components/charts/ProbabilityBar';
import Badge from '@/components/data/Badge';
import TeamLogo from '@/components/common/TeamLogo';
import DataTable, { type Column } from '@/components/data/DataTable';
import { Skeleton, SkeletonCard } from '@/components/data/Skeleton';
import { formatKickoff, formatEV } from '@/utils/format';
import { useLeague } from '@/contexts/LeagueContext';
import { useUser } from '@/contexts/UserContext';
import client from '@/api/client';

// ─── API types ────────────────────────────────────────────────────────────────

interface ApiMatch {
  match_id: number;
  season: string;
  matchday: number;
  kickoff: string;
  status: string;
  home_team_id: number;
  home_team: string;
  away_team_id: number;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  league_code: string;
  league_name: string;
}

interface ApiPrediction {
  match_id: number;
  probabilities: { home_win: number; draw: number; away_win: number };
  predicted_score: { home: number; away: number };
  confidence: number;
}

interface ApiValueBet {
  match_id: number;
  home_team: string;
  away_team: string;
  kickoff: string;
  market: string;
  selection: string;
  best_odds: number;
  bookmaker: string;
  model_prob: number;
  ev_pct: number;
  edge: number;
  confidence: number;
}

interface ApiHealth {
  status: string;
  db_connected: boolean;
  data_freshness?: string;
}

interface ApiFplPlayer {
  player_id?: number;
  web_name: string;
  team: string;
  projected_points?: number;
  ownership?: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const SHORT_NAMES: Record<string, string> = {
  'Arsenal': 'ARS', 'Manchester City': 'MCI', 'Liverpool': 'LIV', 'Chelsea': 'CHE',
  'Manchester United': 'MUN', 'Tottenham Hotspur': 'TOT', 'Newcastle United': 'NEW',
  'Aston Villa': 'AVL', 'Brighton': 'BHA', 'West Ham United': 'WHU',
  'Crystal Palace': 'CRY', 'Brentford': 'BRE', 'Fulham': 'FUL',
  'Wolverhampton': 'WOL', 'Bournemouth': 'BOU', 'Nottingham Forest': 'NFO',
  'Everton': 'EVE', 'Luton Town': 'LUT', 'Burnley': 'BUR', 'Sheffield United': 'SHU',
};

function getShort(name: string): string {
  return SHORT_NAMES[name] ?? name.substring(0, 3).toUpperCase();
}

// ─── Recent predictions table row type ───────────────────────────────────────

interface RecentPredictionRow {
  id: number;
  match: string;
  predicted: string;
  actual: string | null;
  confidence: number;
  result: 'W' | 'D' | 'L' | null;
  date: string;
}

const PREDICTION_COLUMNS: Column<RecentPredictionRow & Record<string, unknown>>[] = [
  {
    key: 'match',
    label: 'Match',
    render: (v) => <span className="font-medium text-slate-200">{v as string}</span>,
  },
  {
    key: 'predicted',
    label: 'Predicted',
    align: 'center',
    render: (v) => <span className="font-mono text-slate-400">{v as string}</span>,
  },
  {
    key: 'actual',
    label: 'Actual',
    align: 'center',
    render: (v) => (
      <span className="font-mono text-slate-300">{v !== null ? (v as string) : '—'}</span>
    ),
  },
  {
    key: 'confidence',
    label: 'Confidence',
    align: 'right',
    sortable: true,
    render: (v) => (
      <span className="font-mono text-slate-400">{((v as number) * 100).toFixed(0)}%</span>
    ),
  },
  {
    key: 'result',
    label: 'Result',
    align: 'center',
    render: (v) =>
      v ? <Badge variant={v as 'W' | 'D' | 'L'} size="xs" /> : <span className="text-slate-600">—</span>,
  },
  {
    key: 'date',
    label: 'Date',
    align: 'right',
    render: (v) => <span className="font-mono text-xs text-slate-500">{v as string}</span>,
  },
];

const QUICK_LINKS = [
  {
    to: '/matches',
    icon: Calendar,
    title: 'Match Predictions',
    desc: 'View all upcoming matches',
    color: 'text-sky-400',
    bg: 'bg-sky-500/10 border-sky-500/20',
  },
  {
    to: '/betting',
    icon: TrendingUp,
    title: 'Betting EV Scanner',
    desc: 'Find value bets with positive EV',
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10 border-emerald-500/20',
  },
  {
    to: '/fpl',
    icon: Users,
    title: 'FPL Optimizer',
    desc: 'Optimize your FPL squad',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10 border-amber-500/20',
  },
];

// ─── Main component ───────────────────────────────────────────────────────────

export default function Dashboard() {
  const { league, apiSeason } = useLeague();
  const { user } = useUser();

  const [upcomingMatches, setUpcomingMatches] = useState<ApiMatch[]>([]);
  const [predictions, setPredictions] = useState<Record<number, ApiPrediction>>({});
  const [finishedMatches, setFinishedMatches] = useState<ApiMatch[]>([]);
  const [finishedPredictions, setFinishedPredictions] = useState<Record<number, ApiPrediction>>({});
  const [valueBets, setValueBets] = useState<ApiValueBet[]>([]);
  const [valueBetsCount, setValueBetsCount] = useState<number>(0);
  const [fplPlayer, setFplPlayer] = useState<ApiFplPlayer | null>(null);
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [favTeamMatches, setFavTeamMatches] = useState<ApiMatch[]>([]);

  useEffect(() => {
    setLoading(true);
    setUpcomingMatches([]);
    setFinishedMatches([]);
    setPredictions({});
    setFinishedPredictions({});
    setValueBets([]);
    setValueBetsCount(0);

    const fetchAll = async () => {
      // Fetch upcoming and finished matches separately with status filter
      const [upcomingRes, finishedRes, valueBetsRes, topPlayerRes, healthRes] = await Promise.allSettled([
        client.get('/matches', { params: { league, season: apiSeason, status: 'SCHEDULED', page_size: 10 } }),
        client.get('/matches', { params: { league, season: apiSeason, status: 'FINISHED', page_size: 8 } }),
        client.get('/betting/value-bets', { params: { league, min_ev: 0.01, limit: 5 } }),
        client.get('/scouting/top-player', { params: { league, season: apiSeason } }),
        client.get('/health'),
      ]);

      // Health
      if (healthRes.status === 'fulfilled' && healthRes.value !== null) {
        setHealth(healthRes.value as unknown as ApiHealth);
      }

      // Top player for this league
      if (topPlayerRes.status === 'fulfilled' && topPlayerRes.value !== null) {
        const tpData = topPlayerRes.value as unknown as { player?: { name: string; team: string; position: string; xg_per_90: number; xa_per_90: number } };
        if (tpData?.player) {
          setFplPlayer({ web_name: tpData.player.name, team: tpData.player.team, position: tpData.player.position, total_points: 0, price: 0, form: tpData.player.xg_per_90 + tpData.player.xa_per_90 } as ApiFplPlayer);
        }
      }

      // Value bets
      if (valueBetsRes.status === 'fulfilled') {
        const vbData = valueBetsRes.value as unknown as { value_bets?: ApiValueBet[]; count?: number } | ApiValueBet[];
        const bets = Array.isArray(vbData) ? vbData : (vbData as { value_bets?: ApiValueBet[] }).value_bets ?? [];
        const count = Array.isArray(vbData) ? bets.length : (vbData as { count?: number }).count ?? bets.length;
        setValueBets(bets);
        setValueBetsCount(count);
      }

      // Upcoming matches
      if (upcomingRes.status === 'fulfilled') {
        const upData = upcomingRes.value as unknown as { matches?: ApiMatch[] } | ApiMatch[];
        const upcoming: ApiMatch[] = Array.isArray(upData)
          ? upData
          : (upData as { matches?: ApiMatch[] }).matches ?? [];
        setUpcomingMatches(upcoming.slice(0, 5));

        if (upcoming.length > 0) {
          const predMap: Record<number, ApiPrediction> = {};
          await Promise.all(
            upcoming.slice(0, 5).map(async (m) => {
              try {
                const pr = await client.get(`/predictions/${m.match_id}`);
                predMap[m.match_id] = pr as unknown as ApiPrediction;
              } catch { /* no prediction */ }
            })
          );
          setPredictions(predMap);
        }
      }

      // Finished matches
      if (finishedRes.status === 'fulfilled') {
        const finData = finishedRes.value as unknown as { matches?: ApiMatch[] } | ApiMatch[];
        const finished: ApiMatch[] = Array.isArray(finData)
          ? finData
          : (finData as { matches?: ApiMatch[] }).matches ?? [];
        setFinishedMatches(finished.slice(0, 8));

        if (finished.length > 0) {
          const finPredMap: Record<number, ApiPrediction> = {};
          await Promise.all(
            finished.slice(0, 8).map(async (m) => {
              try {
                const pr = await client.get(`/predictions/${m.match_id}`);
                finPredMap[m.match_id] = pr as unknown as ApiPrediction;
              } catch { /* no prediction */ }
            })
          );
          setFinishedPredictions(finPredMap);
        }
      }

      setLoading(false);
    };

    fetchAll().catch(() => setLoading(false));
  }, [league, apiSeason]);

  // Fetch favorite team's upcoming matches
  useEffect(() => {
    if (!user?.favorite_team_id) {
      setFavTeamMatches([]);
      return;
    }
    client.get('/matches', {
      params: { status: 'SCHEDULED', page_size: 5 },
    })
      .then((res) => {
        const data = res as unknown as { matches?: ApiMatch[] };
        const all: ApiMatch[] = data.matches ?? [];
        const favMatches = all.filter(
          (m) => m.home_team_id === user.favorite_team_id || m.away_team_id === user.favorite_team_id
        );
        setFavTeamMatches(favMatches.slice(0, 3));
      })
      .catch(() => setFavTeamMatches([]));
  }, [user?.favorite_team_id]);

  // Build recent predictions rows from finished matches
  const recentPredRows: RecentPredictionRow[] = finishedMatches.map((m) => {
    const pred = finishedPredictions[m.match_id];
    const homeShort = getShort(m.home_team);
    const awayShort = getShort(m.away_team);
    const predictedScore = pred
      ? `${pred.predicted_score.home.toFixed(0)}-${pred.predicted_score.away.toFixed(0)}`
      : '—';
    const actualScore =
      m.home_score != null && m.away_score != null
        ? `${m.home_score}-${m.away_score}`
        : null;

    let result: 'W' | 'D' | 'L' | null = null;
    if (pred && m.home_score != null && m.away_score != null) {
      const predHome = Math.round(pred.predicted_score.home);
      const predAway = Math.round(pred.predicted_score.away);
      const predOutcome = predHome > predAway ? 'H' : predHome < predAway ? 'A' : 'D';
      const actualOutcome = m.home_score > m.away_score ? 'H' : m.home_score < m.away_score ? 'A' : 'D';
      result = predOutcome === actualOutcome ? 'W' : actualOutcome === 'D' ? 'D' : 'L';
    }

    return {
      id: m.match_id,
      match: `${homeShort} vs ${awayShort}`,
      predicted: predictedScore,
      actual: actualScore,
      confidence: pred?.confidence ?? 0,
      result,
      date: m.kickoff ? m.kickoff.split('T')[0] : '',
    };
  });

  const correctCount = recentPredRows.filter((r) => r.result === 'W').length;
  const resolvedCount = recentPredRows.filter((r) => r.result !== null).length;
  const accuracy = resolvedCount > 0 ? correctCount / resolvedCount : 0;

  const bestValueBet = valueBets[0];
  const totalUpcoming = upcomingMatches.length;

  // Data freshness from health
  const freshness = health?.data_freshness ?? (health?.db_connected ? 'Live' : 'Unknown');

  return (
    <div className="space-y-6 max-w-7xl">
      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          <>
            <StatCard
              label="Upcoming Matches"
              value={totalUpcoming}
              sub={`Next fixtures · ${league}`}
              icon={<Calendar className="w-3.5 h-3.5" />}
            />
            <StatCard
              label="Value Bets"
              value={valueBetsCount}
              sub="EV > 1% found"
              variant={valueBetsCount > 0 ? 'positive' : 'default'}
              icon={<TrendingUp className="w-3.5 h-3.5" />}
            />
            <StatCard
              label="Top Player"
              value={fplPlayer?.web_name ?? '—'}
              sub={fplPlayer ? `${fplPlayer.team} · xG+xA ${fplPlayer.form?.toFixed(2) ?? ''}` : 'No data'}
              icon={<Users className="w-3.5 h-3.5" />}
            />
            <StatCard
              label="Model Accuracy"
              value={resolvedCount > 0 ? `${(accuracy * 100).toFixed(0)}%` : '—'}
              sub={`Last ${resolvedCount} predictions`}
              variant={accuracy >= 0.6 ? 'positive' : 'default'}
              icon={<Target className="w-3.5 h-3.5" />}
            />
            <StatCard
              label="Data Freshness"
              value={health?.db_connected ? 'Live' : 'Offline'}
              sub={typeof freshness === 'string' ? freshness : 'Checking...'}
              variant={health?.db_connected ? 'positive' : 'negative'}
              icon={<Crown className="w-3.5 h-3.5" />}
            />
            <StatCard
              label="Best EV Bet"
              value={bestValueBet ? `+${bestValueBet.ev_pct.toFixed(1)}%` : '—'}
              sub={
                bestValueBet
                  ? `${getShort(bestValueBet.home_team)} · ${bestValueBet.bookmaker}`
                  : 'No value bets'
              }
              variant={bestValueBet ? 'positive' : 'default'}
              icon={<Zap className="w-3.5 h-3.5" />}
            />
          </>
        )}
      </div>

      {/* My Team section */}
      {user?.favorite_team_id && favTeamMatches.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide flex items-center gap-2">
              <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
              My Team
            </h2>
            <Link
              to="/matches"
              className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1 transition-colors"
            >
              View all <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-1">
            {favTeamMatches.map((m) => {
              const homeShort = getShort(m.home_team);
              const awayShort = getShort(m.away_team);
              const pred = predictions[m.match_id];
              return (
                <Link
                  key={m.match_id}
                  to="/matches"
                  className="shrink-0 w-56 bg-amber-500/5 border border-amber-500/20 rounded-lg p-3 hover:border-amber-500/40 transition-colors"
                >
                  <div className="flex items-center gap-1 mb-2">
                    <Star className="w-2.5 h-2.5 text-amber-400 fill-amber-400" />
                    <span className="text-[10px] text-amber-400 font-medium">My Team</span>
                  </div>
                  <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center gap-1.5">
                      <TeamLogo shortName={homeShort} size="xs" />
                      <span className={clsx('text-xs font-medium', m.home_team_id === user.favorite_team_id ? 'text-amber-300' : 'text-slate-300')}>{homeShort}</span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-500 px-1.5 py-0.5 bg-slate-700/50 rounded">vs</span>
                    <div className="flex items-center gap-1.5">
                      <span className={clsx('text-xs font-medium', m.away_team_id === user.favorite_team_id ? 'text-amber-300' : 'text-slate-300')}>{awayShort}</span>
                      <TeamLogo shortName={awayShort} size="xs" />
                    </div>
                  </div>
                  {pred ? (
                    <ProbabilityBar
                      homeProb={pred.probabilities.home_win}
                      drawProb={pred.probabilities.draw}
                      awayProb={pred.probabilities.away_win}
                      homeLabel={homeShort}
                      awayLabel={awayShort}
                      height="sm"
                    />
                  ) : (
                    <div className="h-4 bg-slate-700/40 rounded" />
                  )}
                  <div className="flex justify-between mt-2">
                    <span className="text-[10px] text-slate-500 font-mono">{formatKickoff(m.kickoff)}</span>
                    {pred && (
                      <span className="text-[10px] font-mono font-medium text-slate-400">
                        {pred.predicted_score.home.toFixed(0)}-{pred.predicted_score.away.toFixed(0)}
                      </span>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        </section>
      )}

      {/* Upcoming matches strip */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
            Upcoming Fixtures
          </h2>
          <Link
            to="/matches"
            className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1 transition-colors"
          >
            View all <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {loading ? (
          <div className="flex gap-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="shrink-0 w-56 h-28 rounded-lg" />
            ))}
          </div>
        ) : upcomingMatches.length === 0 ? (
          <div className="flex items-center gap-2 text-slate-500 text-sm py-4">
            <AlertCircle className="w-4 h-4" />
            <span>No upcoming matches found for {league}</span>
          </div>
        ) : (
          <div className="flex gap-3 overflow-x-auto pb-1">
            {upcomingMatches.map((m) => {
              const homeShort = getShort(m.home_team);
              const awayShort = getShort(m.away_team);
              const pred = predictions[m.match_id];
              return (
                <Link
                  key={m.match_id}
                  to="/matches"
                  className="shrink-0 w-56 bg-slate-800/50 border border-slate-700/50 rounded-lg p-3 hover:border-slate-600/70 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center gap-1.5">
                      <TeamLogo shortName={homeShort} size="xs" />
                      <span className="text-xs font-medium text-slate-300">{homeShort}</span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-500 px-1.5 py-0.5 bg-slate-700/50 rounded">
                      vs
                    </span>
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-medium text-slate-300">{awayShort}</span>
                      <TeamLogo shortName={awayShort} size="xs" />
                    </div>
                  </div>

                  {pred ? (
                    <ProbabilityBar
                      homeProb={pred.probabilities.home_win}
                      drawProb={pred.probabilities.draw}
                      awayProb={pred.probabilities.away_win}
                      homeLabel={homeShort}
                      awayLabel={awayShort}
                      height="sm"
                    />
                  ) : (
                    <Skeleton className="h-4 w-full rounded" />
                  )}

                  <div className="flex justify-between mt-2">
                    <span className="text-[10px] text-slate-500 font-mono">
                      {formatKickoff(m.kickoff)}
                    </span>
                    {pred && (
                      <span className="text-[10px] font-mono font-medium text-slate-400">
                        {pred.predicted_score.home.toFixed(0)}-{pred.predicted_score.away.toFixed(0)}
                      </span>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      {/* Bottom: recent predictions + quick links */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Recent Predictions Table */}
        <div className="xl:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
              Recent Predictions
            </h2>
            <span className="text-xs text-slate-500">
              {resolvedCount > 0 ? `${correctCount}/${resolvedCount} correct` : 'No resolved predictions'}
            </span>
          </div>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 rounded" />
              ))}
            </div>
          ) : (
            <DataTable
              columns={PREDICTION_COLUMNS}
              data={recentPredRows as unknown as (RecentPredictionRow & Record<string, unknown>)[]}
              rowKey={(r) => r.id}
              compact
              emptyMessage={`No finished matches found for ${league}`}
            />
          )}
        </div>

        {/* Quick Links */}
        <div>
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-3">
            Quick Access
          </h2>
          <div className="space-y-2.5">
            {QUICK_LINKS.map(({ to, icon: Icon, title, desc, color, bg }) => (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-3 p-3.5 rounded-lg border transition-colors hover:brightness-110 ${bg}`}
              >
                <div className={`p-2 rounded ${bg}`}>
                  <Icon className={`w-4 h-4 ${color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200">{title}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />
              </Link>
            ))}

            {/* Model status card */}
            <div className="p-3.5 rounded-lg border border-slate-700/50 bg-slate-800/30">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
                Model Status
              </p>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">API Health</span>
                  <span className={`text-xs font-medium ${health?.status === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}>
                    {loading ? '...' : health?.status === 'ok' ? 'Healthy' : 'Degraded'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">Database</span>
                  <span className={`text-xs font-medium ${health?.db_connected ? 'text-emerald-400' : 'text-red-400'}`}>
                    {loading ? '...' : health?.db_connected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">Data freshness</span>
                  <span className="text-xs font-medium text-emerald-400">
                    {loading ? '...' : typeof freshness === 'string' ? freshness : 'Live'}
                  </span>
                </div>
              </div>
            </div>

            {/* Value bets summary */}
            {!loading && valueBets.length > 0 && (
              <div className="p-3.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
                  Today&apos;s Best Value
                </p>
                <div className="space-y-1.5">
                  {valueBets.slice(0, 3).map((bet) => (
                    <div key={`${bet.match_id}-${bet.market}-${bet.selection}`} className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-slate-300">
                          {getShort(bet.home_team)} vs {getShort(bet.away_team)}
                        </p>
                        <p className="text-[10px] text-slate-500">
                          {bet.selection} @ {bet.best_odds.toFixed(2)}
                        </p>
                      </div>
                      <span className="text-xs font-mono font-semibold text-emerald-400">
                        {formatEV(bet.ev_pct / 100)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
