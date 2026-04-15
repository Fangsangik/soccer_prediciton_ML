import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import clsx from 'clsx';
import { Filter, ChevronRight, AlertCircle, Star, Activity } from 'lucide-react';
import ProbabilityBar from '@/components/charts/ProbabilityBar';
import HeatMap from '@/components/charts/HeatMap';
import Badge from '@/components/data/Badge';
import TeamLogo from '@/components/common/TeamLogo';
import { Skeleton } from '@/components/data/Skeleton';
import { formatKickoff } from '@/utils/format';
import { useLeague } from '@/contexts/LeagueContext';
import { useUser } from '@/contexts/UserContext';
import client from '@/api/client';

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
  home_xg: number | null;
  away_xg: number | null;
  league_code: string;
  league_name: string;
}

interface ApiPrediction {
  match_id: number;
  model_version: string;
  probabilities: { home_win: number; draw: number; away_win: number };
  predicted_score: { home: number; away: number };
  confidence: number;
  key_factors: Array<{ factor: string; value: number; impact: number }>;
  score_distribution: Record<string, number>;
}

interface TeamForm {
  results: string[];
  points: number;
  goals_scored: number;
  goals_conceded: number;
  win_rate: number;
}

interface HeadToHead {
  matches: number;
  team1_wins: number;
  team2_wins: number;
  draws: number;
  team1_goals: number;
  team2_goals: number;
  // legacy fields
  total?: number;
  home_wins?: number;
  away_wins?: number;
}

interface ApiMatchDetail extends ApiMatch {
  home_form?: TeamForm;
  away_form?: TeamForm;
  head_to_head?: HeadToHead;
}

interface MatchEvent {
  elapsed: number;
  extra_time: number | null;
  type: string;
  detail: string | null;
  player_name: string | null;
  assist_name: string | null;
  team_name: string | null;
}

interface MatchStatistics {
  [teamName: string]: { [statType: string]: string };
}

interface KeyPlayer {
  name: string;
  position: string;
  goals: number;
  assists: number;
  xg_per_90: number;
  xa_per_90: number;
}

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

interface MatchRowProps {
  match: ApiMatch;
  prediction: ApiPrediction | null;
  selected: boolean;
  isFavorite: boolean;
  onClick: () => void;
}

function MatchRow({ match, prediction, selected, isFavorite, onClick }: MatchRowProps) {
  const homeShort = getShort(match.home_team);
  const awayShort = getShort(match.away_team);

  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full text-left px-3 py-3 rounded-lg border transition-colors',
        selected
          ? 'bg-slate-700/60 border-emerald-500/40'
          : 'bg-slate-800/30 border-slate-700/40 hover:bg-slate-700/30 hover:border-slate-600/50'
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono text-slate-500">{formatKickoff(match.kickoff)}</span>
        <div className="flex items-center gap-1">
          {isFavorite && <Star className="w-3 h-3 text-amber-400 fill-amber-400" />}
          <Badge variant={match.status === 'IN_PLAY' || match.status === 'PAUSED' || match.status === 'HALFTIME' ? 'in_play' : match.status === 'FINISHED' ? 'finished' : 'scheduled'} size="xs" />
        </div>
      </div>

      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 flex-1">
          <TeamLogo shortName={homeShort} size="xs" />
          <span className="text-xs font-medium text-slate-200 truncate">{homeShort}</span>
        </div>
        {(match.status === 'FINISHED' || match.status === 'IN_PLAY' || match.status === 'PAUSED' || match.status === 'HALFTIME') && match.home_score != null ? (
          <span className={clsx('text-xs font-mono font-bold px-2', match.status === 'IN_PLAY' || match.status === 'PAUSED' || match.status === 'HALFTIME' ? 'text-emerald-400' : 'text-slate-200')}>
            {match.home_score} – {match.away_score}
          </span>
        ) : (
          <span className="text-[10px] font-mono text-slate-500 px-1">vs</span>
        )}
        <div className="flex items-center gap-1.5 flex-1 justify-end">
          <span className="text-xs font-medium text-slate-200 truncate">{awayShort}</span>
          <TeamLogo shortName={awayShort} size="xs" />
        </div>
      </div>

      {prediction && (
        <>
          <ProbabilityBar
            homeProb={prediction.probabilities.home_win}
            drawProb={prediction.probabilities.draw}
            awayProb={prediction.probabilities.away_win}
            homeLabel={homeShort}
            awayLabel={awayShort}
            height="sm"
            showLabels={false}
          />
          <div className="flex justify-between mt-1.5">
            <span className="text-[10px] font-mono text-slate-500">
              Pred: {(prediction.predicted_score.home ?? 0).toFixed(1)}–{(prediction.predicted_score.away ?? 0).toFixed(1)}
            </span>
            <span className="text-[10px] font-mono text-slate-500">
              {((prediction.confidence ?? 0) * 100).toFixed(0)}% conf
            </span>
          </div>
        </>
      )}
    </button>
  );
}

function FormBadges({ results }: { results: string[] }) {
  return (
    <div className="flex gap-1">
      {results.map((r, i) => (
        <span
          key={i}
          className={clsx(
            'w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold',
            r === 'W' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' :
            r === 'D' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' :
            'bg-red-500/20 text-red-400 border border-red-500/40'
          )}
        >
          {r}
        </span>
      ))}
    </div>
  );
}

function KeyPlayerRow({ player, star }: { player: KeyPlayer; star: boolean }) {
  return (
    <div className="flex items-center gap-1.5 text-xs">
      {star ? <span className="text-amber-400">⭐</span> : <span className="w-4" />}
      <span className="text-slate-200 font-medium">{player.name}</span>
      <span className="font-mono text-slate-500">
        ({player.goals ?? 0}G {player.assists ?? 0}A)
      </span>
    </div>
  );
}

function getEventIcon(type: string, detail: string | null): string {
  if (type === 'Goal') return '\u26BD';
  if (type === 'Card') {
    if (detail?.toLowerCase().includes('red')) return '\uD83D\uDFE5';
    return '\uD83D\uDFE8';
  }
  if (type === 'subst') return '\uD83D\uDD04';
  return '\u25CF';
}

function EventTimeline({ events }: { events: MatchEvent[] }) {
  if (events.length === 0) return <p className="text-xs text-slate-600">No events recorded yet.</p>;
  return (
    <div className="space-y-1.5">
      {events.map((e, i) => {
        const icon = getEventIcon(e.type, e.detail);
        const time = e.extra_time ? `${e.elapsed}+${e.extra_time}'` : `${e.elapsed}'`;
        return (
          <div key={i} className="flex items-start gap-2 text-xs">
            <span className="font-mono text-slate-500 w-10 text-right shrink-0">{time}</span>
            <span className="shrink-0">{icon}</span>
            <div className="flex-1 min-w-0">
              <span className="text-slate-200 font-medium">{e.player_name ?? 'Unknown'}</span>
              {e.type === 'subst' && e.assist_name && (
                <span className="text-slate-500"> for {e.assist_name}</span>
              )}
              {e.type === 'Goal' && e.assist_name && (
                <span className="text-slate-500"> (assist: {e.assist_name})</span>
              )}
              {e.team_name && (
                <span className="text-slate-600"> — {e.team_name}</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function StatBar({ label, homeVal, awayVal }: { label: string; homeVal: string; awayVal: string }) {
  const hNum = parseFloat(homeVal.replace('%', '')) || 0;
  const aNum = parseFloat(awayVal.replace('%', '')) || 0;
  const total = hNum + aNum || 1;
  const hPct = (hNum / total) * 100;
  const aPct = (aNum / total) * 100;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-mono text-slate-300 w-16 text-right">{homeVal}</span>
        <span className="text-slate-500 text-[10px] text-center flex-1 px-2">{label}</span>
        <span className="font-mono text-slate-300 w-16">{awayVal}</span>
      </div>
      <div className="flex h-1.5 gap-0.5">
        <div className="flex-1 bg-slate-700 rounded-full overflow-hidden flex justify-end">
          <div className="bg-emerald-500/60 rounded-full" style={{ width: `${hPct}%` }} />
        </div>
        <div className="flex-1 bg-slate-700 rounded-full overflow-hidden">
          <div className="bg-red-500/60 rounded-full" style={{ width: `${aPct}%` }} />
        </div>
      </div>
    </div>
  );
}

function MatchStats({ statistics, homeTeam, awayTeam }: { statistics: MatchStatistics; homeTeam: string; awayTeam: string }) {
  const teamNames = Object.keys(statistics);
  if (teamNames.length < 2) return <p className="text-xs text-slate-600">No statistics available.</p>;

  // Try to match team names
  const home = teamNames.find((t) => homeTeam.includes(t) || t.includes(homeTeam)) ?? teamNames[0];
  const away = teamNames.find((t) => t !== home) ?? teamNames[1];
  const homeStats = statistics[home] ?? {};
  const awayStats = statistics[away] ?? {};

  const statTypes = Array.from(new Set([...Object.keys(homeStats), ...Object.keys(awayStats)]));
  const priorityStats = ['Ball Possession', 'Shots on Goal', 'Total Shots', 'Corner Kicks', 'Fouls', 'Offsides', 'Pass Accuracy', 'Total passes'];
  const ordered = [...priorityStats.filter((s) => statTypes.includes(s)), ...statTypes.filter((s) => !priorityStats.includes(s))];

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
        <span className="font-medium">{home}</span>
        <span className="font-medium">{away}</span>
      </div>
      {ordered.map((stat) => (
        <StatBar key={stat} label={stat} homeVal={homeStats[stat] ?? '0'} awayVal={awayStats[stat] ?? '0'} />
      ))}
    </div>
  );
}

export default function MatchPrediction() {
  const { league, apiSeason } = useLeague();
  const { user } = useUser();
  const [searchParams, setSearchParams] = useSearchParams();
  const [matches, setMatches] = useState<ApiMatch[]>([]);
  const [predictions, setPredictions] = useState<Record<number, ApiPrediction>>({});
  const [selectedId, setSelectedId] = useState<number | null>(() => {
    const matchParam = searchParams.get('match');
    return matchParam ? Number(matchParam) : null;
  });
  const [detail, setDetail] = useState<ApiMatchDetail | null>(null);
  const [selectedPred, setSelectedPred] = useState<ApiPrediction | null>(null);
  const [loading, setLoading] = useState(true);
  const [homeKeyPlayers, setHomeKeyPlayers] = useState<KeyPlayer[]>([]);
  const [awayKeyPlayers, setAwayKeyPlayers] = useState<KeyPlayer[]>([]);
  const [matchEvents, setMatchEvents] = useState<MatchEvent[]>([]);
  const [matchStats, setMatchStats] = useState<MatchStatistics>({});
  const [detailTab, setDetailTab] = useState<'analysis' | 'events' | 'stats'>('analysis');
  const refreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch matches when league or season changes
  useEffect(() => {
    setLoading(true);
    setMatches([]);
    setPredictions({});
    setSelectedId(null);
    setDetail(null);
    setSelectedPred(null);

    client.get('/matches', { params: { league, season: apiSeason, page_size: 20 } })
      .then(async (res) => {
        const data = res as unknown as { matches?: ApiMatch[] };
        const matchList: ApiMatch[] = data.matches ?? [];
        setMatches(matchList);

        if (matchList.length > 0) {
          const urlMatchId = searchParams.get('match') ? Number(searchParams.get('match')) : null;
          const restoredId = urlMatchId && matchList.some((m) => m.match_id === urlMatchId)
            ? urlMatchId
            : matchList[0].match_id;
          setSelectedId(restoredId);

          const predMap: Record<number, ApiPrediction> = {};
          await Promise.all(
            matchList.map(async (m) => {
              try {
                const pr = await client.get(`/predictions/${m.match_id}`);
                predMap[m.match_id] = pr as unknown as ApiPrediction;
              } catch { /* no prediction available */ }
            })
          );
          setPredictions(predMap);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [league, apiSeason]);

  // Fetch events and stats for a match
  const fetchEventsAndStats = (matchId: number) => {
    client.get(`/matches/${matchId}/events`)
      .then((res) => {
        const d = res as unknown as { events: MatchEvent[] };
        setMatchEvents(d.events ?? []);
      })
      .catch(() => setMatchEvents([]));

    client.get(`/matches/${matchId}/statistics`)
      .then((res) => {
        const d = res as unknown as { statistics: MatchStatistics };
        setMatchStats(d.statistics ?? {});
      })
      .catch(() => setMatchStats({}));
  };

  // Fetch detail + key players when selected match changes
  useEffect(() => {
    if (!selectedId) return;

    setHomeKeyPlayers([]);
    setAwayKeyPlayers([]);
    setMatchEvents([]);
    setMatchStats({});

    client.get(`/matches/${selectedId}`)
      .then((res) => {
        const d = res as unknown as ApiMatchDetail;
        setDetail(d);

        // Fetch key players for both teams
        const homeTeam = d.home_team;
        const awayTeam = d.away_team;
        if (homeTeam) {
          client.get(`/scouting/team-key-players/${encodeURIComponent(homeTeam)}`, { params: { season: apiSeason } })
            .then((r) => {
              const kp = r as unknown as { key_players: KeyPlayer[] };
              setHomeKeyPlayers(kp.key_players ?? []);
            })
            .catch(() => setHomeKeyPlayers([]));
        }
        if (awayTeam) {
          client.get(`/scouting/team-key-players/${encodeURIComponent(awayTeam)}`, { params: { season: apiSeason } })
            .then((r) => {
              const kp = r as unknown as { key_players: KeyPlayer[] };
              setAwayKeyPlayers(kp.key_players ?? []);
            })
            .catch(() => setAwayKeyPlayers([]));
        }

        // Fetch events/stats for live or finished matches
        if (d.status === 'IN_PLAY' || d.status === 'PAUSED' || d.status === 'HALFTIME' || d.status === 'FINISHED') {
          fetchEventsAndStats(selectedId);
          // Auto-switch to events tab for live matches
          if (d.status === 'IN_PLAY' || d.status === 'PAUSED' || d.status === 'HALFTIME') {
            setDetailTab('events');
          }
        }
      })
      .catch(() => setDetail(null));

    if (predictions[selectedId]) {
      setSelectedPred(predictions[selectedId]);
    } else {
      client.get(`/predictions/${selectedId}`)
        .then((res) => setSelectedPred(res as unknown as ApiPrediction))
        .catch(() => setSelectedPred(null));
    }
  }, [selectedId, predictions, apiSeason]);

  // Auto-refresh for live matches every 30 seconds
  useEffect(() => {
    if (refreshRef.current) {
      clearInterval(refreshRef.current);
      refreshRef.current = null;
    }

    const isLive = selected && (selected.status === 'IN_PLAY' || selected.status === 'PAUSED' || selected.status === 'HALFTIME');
    if (isLive && selectedId) {
      const matchId = selectedId;
      refreshRef.current = setInterval(() => {
        fetchEventsAndStats(matchId);
        // Also refresh match detail for score updates
        client.get(`/matches/${matchId}`)
          .then((res) => setDetail(res as unknown as ApiMatchDetail))
          .catch(() => {});
      }, 30000);
    }

    return () => {
      if (refreshRef.current) {
        clearInterval(refreshRef.current);
        refreshRef.current = null;
      }
    };
  }, [selectedId, matches]);

  const selected = matches.find((m) => m.match_id === selectedId);

  // Sort: favorite team's matches first, then upcoming before finished
  const sortedMatches = user?.favorite_team_id
    ? [...matches].sort((a, b) => {
        const aFav = a.home_team_id === user.favorite_team_id || a.away_team_id === user.favorite_team_id;
        const bFav = b.home_team_id === user.favorite_team_id || b.away_team_id === user.favorite_team_id;
        if (aFav && !bFav) return -1;
        if (!aFav && bFav) return 1;
        return 0;
      })
    : matches;

  if (loading) {
    return (
      <div className="flex gap-4 h-[calc(100vh-88px)] max-w-7xl">
        <div className="w-64 shrink-0 space-y-2">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-lg" />)}
        </div>
        <div className="flex-1">
          <Skeleton className="h-64 rounded-lg" />
        </div>
      </div>
    );
  }

  if (matches.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-88px)] text-slate-500">
        <AlertCircle className="w-12 h-12 mb-3 text-slate-600" />
        <p className="text-sm">No matches found for {league}</p>
        <p className="text-xs mt-1 text-slate-600">Try selecting Premier League (PL) which has mock data</p>
      </div>
    );
  }

  const h2h = detail?.head_to_head;
  const h2hMatches = h2h?.matches ?? h2h?.total ?? 0;
  const h2hTeam1Wins = h2h?.team1_wins ?? h2h?.home_wins ?? 0;
  const h2hTeam2Wins = h2h?.team2_wins ?? h2h?.away_wins ?? 0;
  const h2hDraws = h2h?.draws ?? 0;

  return (
    <div className="flex gap-4 h-[calc(100vh-88px)] max-w-7xl">
      {/* Left panel: match list */}
      <div className="w-64 shrink-0 flex flex-col gap-2">
        <div className="flex items-center gap-2 pb-1">
          <Filter className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
            {league} · {matches.length} matches
          </span>
        </div>
        <div className="space-y-2 overflow-y-auto flex-1 pr-1">
          {sortedMatches.map((m) => (
            <MatchRow
              key={m.match_id}
              match={m}
              prediction={predictions[m.match_id] ?? null}
              selected={selectedId === m.match_id}
              isFavorite={!!(user?.favorite_team_id && (m.home_team_id === user.favorite_team_id || m.away_team_id === user.favorite_team_id))}
              onClick={() => { setSelectedId(m.match_id); setSearchParams({ match: String(m.match_id) }); }}
            />
          ))}
        </div>
      </div>

      {/* Right panel: match detail */}
      <div className="flex-1 overflow-y-auto space-y-4">
        {selected && (
          <>
            {/* Match header */}
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-5">
              <div className="flex items-center gap-3 mb-1 text-xs text-slate-500">
                <span>{detail?.league_name ?? league}</span>
                <ChevronRight className="w-3 h-3" />
                <span>GW{selected.matchday}</span>
                <ChevronRight className="w-3 h-3" />
                <span>{formatKickoff(selected.kickoff)}</span>
                {(selected.status === 'IN_PLAY' || selected.status === 'PAUSED' || selected.status === 'HALFTIME') && (
                  <span className="flex items-center gap-1 ml-2 text-emerald-400 font-medium">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    LIVE
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between mt-4">
                {/* Home team */}
                <div className="flex flex-col items-center gap-2 flex-1">
                  <TeamLogo shortName={getShort(selected.home_team)} size="lg" />
                  <span className="text-base font-semibold text-slate-100">{selected.home_team}</span>
                  {detail?.home_form?.results && detail.home_form.results.length > 0 && (
                    <FormBadges results={detail.home_form.results} />
                  )}
                  {/* Key players */}
                  {homeKeyPlayers.length > 0 && (
                    <div className="space-y-0.5 mt-1">
                      {homeKeyPlayers.map((p, i) => (
                        <KeyPlayerRow key={p.name} player={p} star={i === 0} />
                      ))}
                    </div>
                  )}
                </div>

                {/* Score / prediction */}
                <div className="flex flex-col items-center gap-2 px-6">
                  {selectedPred ? (
                    <>
                      <span className="text-3xl font-mono font-bold text-slate-100">
                        {(selectedPred.predicted_score.home ?? 0).toFixed(1)} – {(selectedPred.predicted_score.away ?? 0).toFixed(1)}
                      </span>
                      <span className="text-xs text-slate-500">Predicted score</span>
                      <span className="text-xs font-mono font-medium text-emerald-400">
                        {((selectedPred.confidence ?? 0) * 100).toFixed(0)}% confidence
                      </span>
                    </>
                  ) : selected.status === 'FINISHED' ? (
                    <>
                      <span className="text-3xl font-mono font-bold text-slate-100">
                        {selected.home_score} – {selected.away_score}
                      </span>
                      <span className="text-xs text-slate-500">Final score</span>
                    </>
                  ) : (
                    <span className="text-lg font-mono text-slate-500">vs</span>
                  )}
                </div>

                {/* Away team */}
                <div className="flex flex-col items-center gap-2 flex-1">
                  <TeamLogo shortName={getShort(selected.away_team)} size="lg" />
                  <span className="text-base font-semibold text-slate-100">{selected.away_team}</span>
                  {detail?.away_form?.results && detail.away_form.results.length > 0 && (
                    <FormBadges results={detail.away_form.results} />
                  )}
                  {/* Key players */}
                  {awayKeyPlayers.length > 0 && (
                    <div className="space-y-0.5 mt-1">
                      {awayKeyPlayers.map((p, i) => (
                        <KeyPlayerRow key={p.name} player={p} star={i === 0} />
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {selectedPred && (
                <div className="mt-5">
                  <p className="text-xs text-slate-500 mb-1.5">Win probability</p>
                  <ProbabilityBar
                    homeProb={selectedPred.probabilities.home_win}
                    drawProb={selectedPred.probabilities.draw}
                    awayProb={selectedPred.probabilities.away_win}
                    homeLabel={selected.home_team}
                    awayLabel={selected.away_team}
                    height="lg"
                  />
                </div>
              )}
            </div>

            {/* Tab navigation for live/finished matches */}
            {(selected.status === 'IN_PLAY' || selected.status === 'PAUSED' || selected.status === 'HALFTIME' || selected.status === 'FINISHED') && (
              <>
                <div className="flex gap-1 bg-slate-800/30 border border-slate-700/50 rounded-lg p-1">
                  {(['analysis', 'events', 'stats'] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setDetailTab(tab)}
                      className={clsx(
                        'flex-1 py-1.5 rounded text-xs font-medium transition-colors',
                        detailTab === tab
                          ? 'bg-slate-700 text-slate-100'
                          : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/50'
                      )}
                    >
                      {tab === 'analysis' ? 'Analysis' : tab === 'events' ? 'Events' : 'Statistics'}
                      {tab === 'events' && (selected.status === 'IN_PLAY' || selected.status === 'PAUSED' || selected.status === 'HALFTIME') && (
                        <span className="ml-1.5 w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block" />
                      )}
                    </button>
                  ))}
                </div>

                {/* Events tab */}
                {detailTab === 'events' && (
                  <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                        Match Events
                      </p>
                      {(selected.status === 'IN_PLAY' || selected.status === 'PAUSED' || selected.status === 'HALFTIME') && (
                        <span className="text-[10px] text-slate-600 flex items-center gap-1">
                          <Activity className="w-3 h-3" />
                          Auto-refreshing every 30s
                        </span>
                      )}
                    </div>
                    <EventTimeline events={matchEvents} />
                  </div>
                )}

                {/* Statistics tab */}
                {detailTab === 'stats' && (
                  <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                        Match Statistics
                      </p>
                      {(selected.status === 'IN_PLAY' || selected.status === 'PAUSED' || selected.status === 'HALFTIME') && (
                        <span className="text-[10px] text-slate-600 flex items-center gap-1">
                          <Activity className="w-3 h-3" />
                          Auto-refreshing every 30s
                        </span>
                      )}
                    </div>
                    <MatchStats
                      statistics={matchStats}
                      homeTeam={selected.home_team}
                      awayTeam={selected.away_team}
                    />
                  </div>
                )}
              </>
            )}

            {/* Form + H2H (shown in analysis tab or for scheduled matches) */}
            {(detailTab === 'analysis' || selected.status === 'SCHEDULED') && (
            <div className="grid grid-cols-2 gap-4">
              {/* Team form */}
              <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
                  Form (Last 5)
                </p>
                {detail?.home_form && detail?.away_form ? (
                  <div className="space-y-4">
                    {[
                      { label: selected.home_team, form: detail.home_form },
                      { label: selected.away_team, form: detail.away_form },
                    ].map(({ label, form }) => {
                      const wins = (form.results ?? []).filter((r) => r === 'W').length;
                      const total = (form.results ?? []).length;
                      const winRate = total > 0 ? Math.round((wins / total) * 100) : 0;
                      return (
                        <div key={label}>
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-xs text-slate-400 truncate">{label}</span>
                            <span className="text-[10px] font-mono text-slate-500">{winRate}% win</span>
                          </div>
                          <FormBadges results={form.results ?? []} />
                          <div className="flex gap-3 mt-1.5 text-[10px] font-mono text-slate-500">
                            <span>{form.goals_scored ?? 0}F</span>
                            <span>{form.goals_conceded ?? 0}A</span>
                            <span>{form.points ?? 0}pts</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-xs text-slate-600">Loading form data...</p>
                )}
              </div>

              {/* Head to Head */}
              <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
                  Head to Head
                </p>
                {h2h ? (
                  <>
                    <div className="flex justify-around text-center">
                      {[
                        { label: getShort(selected.home_team), value: h2hTeam1Wins, color: 'text-emerald-400' },
                        { label: 'Draw', value: h2hDraws, color: 'text-amber-400' },
                        { label: getShort(selected.away_team), value: h2hTeam2Wins, color: 'text-red-400' },
                      ].map(({ label, value, color }) => (
                        <div key={label}>
                          <p className={clsx('font-mono text-2xl font-bold', color)}>{value}</p>
                          <p className="text-xs text-slate-500 mt-1">{label}</p>
                        </div>
                      ))}
                    </div>
                    <p className="text-[10px] text-slate-600 text-center mt-3">
                      Last {h2hMatches} meetings
                    </p>
                    {/* 5-year H2H aggregate */}
                    {(h2h.team1_goals != null || h2h.team2_goals != null) && (
                      <div className="mt-3 pt-3 border-t border-slate-700/50 grid grid-cols-3 gap-1 text-center">
                        <div>
                          <p className="font-mono text-sm font-bold text-slate-300">{h2h.team1_goals ?? 0}</p>
                          <p className="text-[10px] text-slate-600">Home goals</p>
                        </div>
                        <div>
                          <p className="font-mono text-sm font-bold text-slate-300">{h2hMatches}</p>
                          <p className="text-[10px] text-slate-600">Meetings</p>
                        </div>
                        <div>
                          <p className="font-mono text-sm font-bold text-slate-300">{h2h.team2_goals ?? 0}</p>
                          <p className="text-[10px] text-slate-600">Away goals</p>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="text-xs text-slate-600">Loading H2H data...</p>
                )}
              </div>
            </div>
            )}

            {/* Score distribution heatmap */}
            {selectedPred?.score_distribution && (
              <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-4">
                  Score Distribution
                </p>
                <HeatMap
                  data={selectedPred.score_distribution}
                  homeTeam={getShort(selected.home_team)}
                  awayTeam={getShort(selected.away_team)}
                />
              </div>
            )}

            {/* Key prediction factors */}
            {selectedPred?.key_factors && selectedPred.key_factors.length > 0 && (
              <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
                  Key Prediction Factors
                </p>
                <div className="space-y-2">
                  {selectedPred.key_factors.map(({ factor, impact }) => (
                    <div key={factor} className="flex items-center gap-3">
                      <div className="flex-1">
                        <p className="text-xs text-slate-300">{factor}</p>
                      </div>
                      <div className="w-24 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className={clsx(
                            'h-full rounded-full',
                            (impact ?? 0) > 0 ? 'bg-emerald-500' : 'bg-red-500'
                          )}
                          style={{ width: `${Math.min(Math.abs(impact ?? 0) * 100, 100)}%`, marginLeft: (impact ?? 0) < 0 ? 'auto' : 0 }}
                        />
                      </div>
                      <span className={clsx('text-xs font-mono font-medium w-12 text-right', (impact ?? 0) > 0 ? 'text-emerald-400' : 'text-red-400')}>
                        {(impact ?? 0) > 0 ? '+' : ''}{((impact ?? 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
