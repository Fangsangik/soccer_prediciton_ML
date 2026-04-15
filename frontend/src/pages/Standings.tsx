import { useState, useEffect } from 'react';
import clsx from 'clsx';
import { Trophy, AlertCircle } from 'lucide-react';
import TeamLogo from '@/components/common/TeamLogo';
import { Skeleton } from '@/components/data/Skeleton';
import { formatKickoff } from '@/utils/format';
import { useLeague } from '@/contexts/LeagueContext';
import client from '@/api/client';

interface StandingRow {
  position: number;
  team_id: number;
  name: string;
  short_name: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
}

interface KnockoutMatch {
  match_id: number;
  status: string;
  home_team: string;
  home_short: string;
  away_team: string;
  away_short: string;
  home_score: number | null;
  away_score: number | null;
  kickoff: string;
}

interface TournamentData {
  league_stage: StandingRow[];
  knockout: Record<string, KnockoutMatch[]>;
}

interface RankingPlayer {
  name: string;
  team: string;
  position: string;
  stat_value: number;
  minutes: number;
}

type StandingsTab = 'table' | 'goals' | 'assists' | 'clean_sheets';

const EUROPEAN_COMPS = new Set(['CL', 'EL', 'ECL']);

// ─── Rankings Table Component ─────────────────────────────────────────────────

function RankingsTable({ players, category }: { players: RankingPlayer[]; category: string }) {
  const statLabel = category === 'goals' ? 'Goals' : category === 'assists' ? 'Assists' : 'Clean Sheets';

  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-slate-800 border-b border-slate-700">
            <th className="w-8 px-3 py-2.5 text-left text-slate-500 font-medium">#</th>
            <th className="px-3 py-2.5 text-left text-slate-500 font-medium">Player</th>
            <th className="px-3 py-2.5 text-left text-slate-500 font-medium">Team</th>
            <th className="w-12 px-2 py-2.5 text-center text-slate-500 font-medium">{statLabel}</th>
            <th className="w-16 px-2 py-2.5 text-center text-slate-500 font-medium">Mins</th>
          </tr>
        </thead>
        <tbody>
          {players.map((p, i) => (
            <tr
              key={`${p.name}-${i}`}
              className={clsx(
                'border-b border-slate-700/30 hover:bg-slate-700/20 transition-colors',
                i === 0 && 'bg-amber-500/5',
              )}
            >
              <td className={clsx('px-3 py-2 font-mono font-bold', i === 0 ? 'text-amber-400' : 'text-slate-500')}>
                {i + 1}
              </td>
              <td className="px-3 py-2">
                <div className="flex items-center gap-1.5">
                  {i === 0 && <span className="text-amber-400 text-[10px]">★</span>}
                  <span className={clsx('font-medium', i === 0 ? 'text-amber-200' : 'text-slate-200')}>{p.name}</span>
                  <span className="text-slate-600 text-[10px]">{p.position}</span>
                </div>
              </td>
              <td className="px-3 py-2 text-slate-400">{p.team}</td>
              <td className={clsx('text-center px-2 py-2 font-mono font-bold', i === 0 ? 'text-amber-400' : 'text-emerald-400')}>
                {(p.stat_value ?? 0)}
              </td>
              <td className="text-center px-2 py-2 font-mono text-slate-500">{(p.minutes ?? 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── League Table Component ──────────────────────────────────────────────────

const LEAGUE_SPOTS: Record<string, { cl: number; el: number; relStart: number }> = {
  PL:  { cl: 5, el: 7,  relStart: 18 },
  PD:  { cl: 4, el: 6,  relStart: 18 },
  BL1: { cl: 4, el: 6,  relStart: 16 },
  SA:  { cl: 4, el: 6,  relStart: 18 },
  FL1: { cl: 3, el: 5,  relStart: 16 },
};

function LeagueTable({ standings, league }: { standings: StandingRow[]; league: string }) {
  const total = standings.length;
  const spots = LEAGUE_SPOTS[league] ?? { cl: 4, el: 6, relStart: total - 2 };
  const getStyle = (pos: number) => {
    if (pos <= spots.cl) return 'border-l-2 border-l-emerald-500';
    if (pos <= spots.el) return 'border-l-2 border-l-amber-500';
    if (pos >= spots.relStart) return 'border-l-2 border-l-red-500';
    return '';
  };

  return (
    <>
      <div className="flex items-center gap-4 text-[10px] text-slate-500 mb-3">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Champions League</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Europa League</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Relegation</span>
      </div>
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-slate-800 border-b border-slate-700">
              {['#', 'Team', 'P', 'W', 'D', 'L', 'GF', 'GA', 'GD', 'Pts'].map((h) => (
                <th key={h} className={clsx('px-2 py-2.5 text-slate-500 font-medium', h === 'Team' ? 'text-left px-3' : 'text-center', h === '#' && 'w-8 text-left px-3', ['P','W','D','L'].includes(h) && 'w-8', ['GF','GA','GD','Pts'].includes(h) && 'w-10')}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {standings.map((r) => (
              <tr key={r.team_id} className={clsx('border-b border-slate-700/30 hover:bg-slate-700/20 transition-colors', getStyle(r.position))}>
                <td className="px-3 py-2 font-mono text-slate-400">{r.position}</td>
                <td className="px-3 py-2"><div className="flex items-center gap-2"><TeamLogo shortName={r.short_name} size="xs" /><span className="font-medium text-slate-200">{r.name}</span></div></td>
                <td className="text-center px-2 py-2 font-mono text-slate-400">{r.played}</td>
                <td className="text-center px-2 py-2 font-mono text-slate-300">{r.wins}</td>
                <td className="text-center px-2 py-2 font-mono text-slate-400">{r.draws}</td>
                <td className="text-center px-2 py-2 font-mono text-slate-400">{r.losses}</td>
                <td className="text-center px-2 py-2 font-mono text-slate-400">{r.goals_for}</td>
                <td className="text-center px-2 py-2 font-mono text-slate-400">{r.goals_against}</td>
                <td className={clsx('text-center px-2 py-2 font-mono', r.goal_difference > 0 ? 'text-emerald-400' : r.goal_difference < 0 ? 'text-red-400' : 'text-slate-500')}>{r.goal_difference > 0 ? '+' : ''}{r.goal_difference}</td>
                <td className="text-center px-3 py-2 font-mono font-bold text-emerald-400">{r.points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ─── Tournament View Component ───────────────────────────────────────────────

function TournamentView({ data }: { data: TournamentData }) {
  const [tab, setTab] = useState<'league' | 'knockout'>('league');

  const knockoutStages = Object.entries(data.knockout);
  const stageOrder = ['Round of 16', 'Quarter-Finals', 'Semi-Finals', 'Final'];
  knockoutStages.sort((a, b) => {
    const ai = stageOrder.indexOf(a[0]);
    const bi = stageOrder.indexOf(b[0]);
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
  });

  return (
    <div className="space-y-4">
      {/* Tabs */}
      <div className="flex gap-1 bg-slate-800/50 border border-slate-700/50 rounded-lg p-1 w-fit">
        <button onClick={() => setTab('league')} className={clsx('px-4 py-1.5 text-xs font-medium rounded transition-colors', tab === 'league' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'text-slate-400 hover:text-slate-200')}>
          League Stage
        </button>
        <button onClick={() => setTab('knockout')} className={clsx('px-4 py-1.5 text-xs font-medium rounded transition-colors', tab === 'knockout' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'text-slate-400 hover:text-slate-200')}>
          Knockout ({knockoutStages.reduce((s, [, m]) => s + m.length, 0)} matches)
        </button>
      </div>

      {tab === 'league' ? (
        data.league_stage.length > 0 ? (
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-800 border-b border-slate-700">
                  {['#', 'Team', 'P', 'W', 'D', 'L', 'GF', 'GA', 'GD', 'Pts'].map((h) => (
                    <th key={h} className={clsx('px-2 py-2.5 text-slate-500 font-medium', h === 'Team' ? 'text-left px-3' : 'text-center', h === '#' && 'w-8 text-left px-3')}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.league_stage.map((r) => {
                  const qualify = r.position <= 8;
                  const playoff = r.position > 8 && r.position <= 24;
                  return (
                    <tr key={r.team_id} className={clsx('border-b border-slate-700/30 hover:bg-slate-700/20 transition-colors', qualify ? 'border-l-2 border-l-emerald-500' : playoff ? 'border-l-2 border-l-amber-500' : 'border-l-2 border-l-red-500')}>
                      <td className="px-3 py-2 font-mono text-slate-400">{r.position}</td>
                      <td className="px-3 py-2"><div className="flex items-center gap-2"><TeamLogo shortName={r.short_name} size="xs" /><span className="font-medium text-slate-200">{r.name}</span></div></td>
                      <td className="text-center px-2 py-2 font-mono text-slate-400">{r.played}</td>
                      <td className="text-center px-2 py-2 font-mono text-slate-300">{r.wins}</td>
                      <td className="text-center px-2 py-2 font-mono text-slate-400">{r.draws}</td>
                      <td className="text-center px-2 py-2 font-mono text-slate-400">{r.losses}</td>
                      <td className="text-center px-2 py-2 font-mono text-slate-400">{r.goals_for}</td>
                      <td className="text-center px-2 py-2 font-mono text-slate-400">{r.goals_against}</td>
                      <td className={clsx('text-center px-2 py-2 font-mono', r.goal_difference > 0 ? 'text-emerald-400' : r.goal_difference < 0 ? 'text-red-400' : 'text-slate-500')}>{r.goal_difference > 0 ? '+' : ''}{r.goal_difference}</td>
                      <td className="text-center px-3 py-2 font-mono font-bold text-emerald-400">{r.points}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="flex items-center gap-4 text-[10px] text-slate-500 px-3 py-2 border-t border-slate-700/30">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Direct R16 (1-8)</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Playoff (9-24)</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Eliminated</span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-500 text-center py-8">No league stage data</p>
        )
      ) : (
        <div className="space-y-5">
          {knockoutStages.length === 0 ? (
            <p className="text-xs text-slate-500 text-center py-8">No knockout matches yet</p>
          ) : (
            knockoutStages.map(([stage, matches]) => (
              <div key={stage}>
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">{stage}</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {matches.map((m) => (
                    <div key={m.match_id} className="bg-slate-800/50 border border-slate-700/50 rounded-lg px-4 py-3 flex items-center justify-between">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <TeamLogo shortName={m.home_short} size="xs" />
                        <span className="text-xs font-medium text-slate-200 truncate">{m.home_team}</span>
                      </div>
                      <div className="px-3 text-center shrink-0">
                        {m.status === 'FINISHED' ? (
                          <span className="font-mono text-sm font-bold text-slate-100">
                            {m.home_score ?? 0} - {m.away_score ?? 0}
                          </span>
                        ) : (
                          <span className="text-[10px] font-mono text-slate-500">{formatKickoff(m.kickoff)}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 flex-1 min-w-0 justify-end">
                        <span className="text-xs font-medium text-slate-200 truncate">{m.away_team}</span>
                        <TeamLogo shortName={m.away_short} size="xs" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function Standings() {
  const { league, apiSeason } = useLeague();
  const isEuropean = EUROPEAN_COMPS.has(league);

  const [activeTab, setActiveTab] = useState<StandingsTab>('table');
  const [standings, setStandings] = useState<StandingRow[]>([]);
  const [tournament, setTournament] = useState<TournamentData | null>(null);
  const [rankings, setRankings] = useState<RankingPlayer[]>([]);
  const [rankingsLoading, setRankingsLoading] = useState(false);
  const [loading, setLoading] = useState(true);

  // Reset tab when league changes
  useEffect(() => {
    setActiveTab('table');
  }, [league]);

  useEffect(() => {
    setLoading(true);
    setStandings([]);
    setTournament(null);

    if (isEuropean) {
      client.get('/standings/tournament', { params: { league, season: apiSeason } })
        .then((res) => {
          const data = res as unknown as TournamentData;
          setTournament(data);
        })
        .catch(() => setTournament(null))
        .finally(() => setLoading(false));
    } else {
      client.get('/standings', { params: { league, season: apiSeason } })
        .then((res) => {
          const data = res as unknown as { standings?: StandingRow[] };
          setStandings(data.standings ?? []);
        })
        .catch(() => setStandings([]))
        .finally(() => setLoading(false));
    }
  }, [league, apiSeason, isEuropean]);

  // Fetch rankings when ranking tab is selected
  useEffect(() => {
    if (activeTab === 'table') return;
    const category = activeTab; // 'goals' | 'assists' | 'clean_sheets'
    setRankingsLoading(true);
    setRankings([]);
    client.get('/scouting/rankings', { params: { league, season: apiSeason, category, limit: 20 } })
      .then((res) => {
        const data = res as unknown as { players?: RankingPlayer[] };
        setRankings(data.players ?? []);
      })
      .catch(() => setRankings([]))
      .finally(() => setRankingsLoading(false));
  }, [activeTab, league, apiSeason]);

  const rankingTabs: { key: StandingsTab; label: string }[] = [
    { key: 'table', label: isEuropean ? 'Tournament' : 'Table' },
    { key: 'goals', label: 'Top Scorers' },
    { key: 'assists', label: 'Top Assists' },
    { key: 'clean_sheets', label: 'Clean Sheets' },
  ];

  return (
    <div className="max-w-5xl space-y-4">
      <div className="flex items-center gap-2">
        <Trophy className="w-4 h-4 text-amber-400" />
        <h2 className="text-sm font-semibold text-slate-200">
          {isEuropean ? 'Tournament' : 'League'} Standings
        </h2>
        <span className="text-xs text-slate-500">{apiSeason}</span>
      </div>

      {/* Top-level tabs */}
      <div className="flex gap-1 bg-slate-800/50 border border-slate-700/50 rounded-lg p-1 w-fit">
        {rankingTabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={clsx(
              'px-4 py-1.5 text-xs font-medium rounded transition-colors',
              activeTab === key
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : 'text-slate-400 hover:text-slate-200',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'table' ? (
        loading ? (
          <div className="space-y-1">
            {Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="h-9 rounded" />)}
          </div>
        ) : isEuropean && tournament ? (
          <TournamentView data={tournament} />
        ) : !isEuropean && standings.length > 0 ? (
          <LeagueTable standings={standings} league={league} />
        ) : (
          <div className="flex flex-col items-center justify-center py-16 text-slate-500">
            <AlertCircle className="w-8 h-8 mb-2 text-slate-600" />
            <p className="text-xs">No standings data available</p>
          </div>
        )
      ) : rankingsLoading ? (
        <div className="space-y-1">
          {Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="h-9 rounded" />)}
        </div>
      ) : rankings.length > 0 ? (
        <RankingsTable players={rankings} category={activeTab} />
      ) : (
        <div className="flex flex-col items-center justify-center py-16 text-slate-500">
          <AlertCircle className="w-8 h-8 mb-2 text-slate-600" />
          <p className="text-xs">No rankings data available</p>
        </div>
      )}
    </div>
  );
}
