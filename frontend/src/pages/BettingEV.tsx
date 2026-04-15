import { useState, useEffect, useCallback } from 'react';
import clsx from 'clsx';
import { Calculator, RefreshCw, AlertTriangle, AlertCircle, Coins, TrendingUp } from 'lucide-react';
import DataTable, { type Column } from '@/components/data/DataTable';
import Badge from '@/components/data/Badge';
import TeamLogo from '@/components/common/TeamLogo';
import { Skeleton } from '@/components/data/Skeleton';
import { formatKickoff, formatEV } from '@/utils/format';
import type { EVResult, ValueBet } from '@/types/betting';
import { useLeague } from '@/contexts/LeagueContext';
import { useUser } from '@/contexts/UserContext';
import client from '@/api/client';

// ─── API types ────────────────────────────────────────────────────────────────

interface ApiMatch {
  match_id: number;
  home_team: string;
  away_team: string;
  home_team_id?: number;
  away_team_id?: number;
  kickoff: string;
  status: string;
  matchday: number;
}

// API response shape from /predictions/{match_id}
interface ApiPredictionResponse {
  match_id?: number;
  probabilities?: {
    home_win: number;
    draw: number;
    away_win: number;
  };
  predicted_score?: {
    home: number;
    away: number;
  };
  key_factors?: Array<string | { factor: string; value: number; impact: number }>;
  // Legacy flat shape (fallback)
  prob_home_win?: number;
  prob_draw?: number;
  prob_away_win?: number;
  confidence?: number;
  prediction?: ApiPredictionResponse;
}

// Normalized prediction used internally
interface Prediction {
  match_id: number;
  prob_home_win: number;
  prob_draw: number;
  prob_away_win: number;
  confidence?: number;
  key_factors?: Array<string | { factor: string; value: number; impact: number }>;
}

// Match detail from /matches/{match_id}
interface FormRecord {
  results: string[];
  win_rate: number;
}

interface H2HRecord {
  matches: number;
  team1_wins: number;
  team2_wins: number;
  draws: number;
}

interface MatchDetail {
  home_form?: FormRecord;
  away_form?: FormRecord;
  head_to_head?: H2HRecord;
}

interface OddsRow {
  id: number;
  market: string;
  selection: string;
  odds: string;
  bookmaker: string;
}

const MARKET_OPTIONS = [
  '1X2 Home', '1X2 Draw', '1X2 Away',
  'Over 2.5', 'Under 2.5',
  'BTTS Yes', 'BTTS No',
  'AH -0.5', 'AH +0.5',
];

// ─── Prediction normalization ─────────────────────────────────────────────────

function normalizePrediction(raw: ApiPredictionResponse): Prediction | null {
  // Unwrap nested .prediction field if present
  const src: ApiPredictionResponse = raw.prediction ?? raw;

  let prob_home_win: number | undefined;
  let prob_draw: number | undefined;
  let prob_away_win: number | undefined;

  if (src.probabilities) {
    prob_home_win = src.probabilities.home_win;
    prob_draw = src.probabilities.draw;
    prob_away_win = src.probabilities.away_win;
  } else {
    prob_home_win = src.prob_home_win;
    prob_draw = src.prob_draw;
    prob_away_win = src.prob_away_win;
  }

  if (prob_home_win == null || prob_draw == null || prob_away_win == null) {
    return null;
  }

  return {
    match_id: src.match_id ?? 0,
    prob_home_win,
    prob_draw,
    prob_away_win,
    confidence: src.confidence,
    key_factors: src.key_factors,
  };
}

// ─── Value bets table columns ─────────────────────────────────────────────────

const VALUE_BET_COLUMNS: Column<ValueBet & Record<string, unknown>>[] = [
  {
    key: 'home_team',
    label: 'Match',
    render: (_v, row) => (
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1">
          <TeamLogo shortName={(row.home_team as string).slice(0, 3).toUpperCase()} size="xs" />
          <span className="text-xs text-slate-300">{row.home_team as string}</span>
        </div>
        <span className="text-[10px] text-slate-600">vs</span>
        <div className="flex items-center gap-1">
          <TeamLogo shortName={(row.away_team as string).slice(0, 3).toUpperCase()} size="xs" />
          <span className="text-xs text-slate-300">{row.away_team as string}</span>
        </div>
      </div>
    ),
  },
  {
    key: 'kickoff',
    label: 'Kickoff',
    render: (v) => <span className="font-mono text-xs text-slate-400">{formatKickoff(v as string)}</span>,
  },
  {
    key: 'market',
    label: 'Market',
    render: (v) => <span className="text-xs text-slate-400">{v as string}</span>,
  },
  {
    key: 'selection',
    label: 'Selection',
    render: (v) => <span className="text-xs font-medium text-slate-200">{v as string}</span>,
  },
  {
    key: 'best_odds',
    label: 'Best Odds',
    align: 'center',
    sortable: true,
    render: (v, row) => (
      <div className="text-center">
        <p className="font-mono text-sm font-semibold text-slate-100">{(v as number).toFixed(2)}</p>
        <p className="text-[10px] text-slate-500">{row.bookmaker as string}</p>
      </div>
    ),
  },
  {
    key: 'model_prob',
    label: 'Model P',
    align: 'center',
    render: (v) => <span className="font-mono text-xs text-slate-300">{((v as number) * 100).toFixed(0)}%</span>,
  },
  {
    key: 'ev_pct',
    label: 'EV',
    align: 'right',
    sortable: true,
    render: (v) => (
      <span className={clsx('font-mono text-sm font-semibold', (v as number) >= 0 ? 'text-emerald-400' : 'text-red-400')}>
        {(v as number) >= 0 ? '+' : ''}{(v as number).toFixed(1)}%
      </span>
    ),
  },
  {
    key: 'confidence',
    label: 'Conf',
    align: 'right',
    sortable: true,
    render: (v) => <span className="font-mono text-xs text-slate-400">{((v as number) * 100).toFixed(0)}%</span>,
  },
];

// ─── Probability bar ──────────────────────────────────────────────────────────

function ProbabilityBar({ home, draw, away }: { home: number; draw: number; away: number }) {
  return (
    <div className="flex h-2 rounded overflow-hidden gap-px">
      <div className="bg-emerald-500/70 transition-all" style={{ width: `${home * 100}%` }} />
      <div className="bg-slate-500/70 transition-all" style={{ width: `${draw * 100}%` }} />
      <div className="bg-red-500/70 transition-all" style={{ width: `${away * 100}%` }} />
    </div>
  );
}

// ─── Form badges ─────────────────────────────────────────────────────────────

function FormBadges({ results }: { results: string[] }) {
  return (
    <div className="flex gap-0.5">
      {results.slice(0, 5).map((r, i) => (
        <span
          key={i}
          className={clsx(
            'text-[9px] font-bold w-4 h-4 flex items-center justify-center rounded-sm',
            r === 'W' && 'bg-emerald-500/30 text-emerald-400',
            r === 'D' && 'bg-amber-500/30 text-amber-400',
            r === 'L' && 'bg-red-500/30 text-red-400',
          )}
        >
          {r}
        </span>
      ))}
    </div>
  );
}

// ─── Match bet card ───────────────────────────────────────────────────────────

interface KeyPlayer {
  name: string;
  position: string;
  goals: number;
  assists: number;
}

interface MatchCardProps {
  match: ApiMatch;
  prediction: Prediction | null;
  predLoading: boolean;
  matchDetail: MatchDetail | null;
  detailLoading: boolean;
  userCoins: number;
  isLoggedIn: boolean;
  apiSeason: string;
  onBet: (matchId: number, betType: string, amount: number, odds: number) => Promise<void>;
}

const BET_AMOUNTS = [100, 500, 1000, 5000];

function MatchCard({
  match,
  prediction,
  predLoading,
  matchDetail,
  detailLoading,
  userCoins,
  isLoggedIn,
  apiSeason,
  onBet,
}: MatchCardProps) {
  const [selectedAmount, setSelectedAmount] = useState(500);
  const [homeKeyPlayers, setHomeKeyPlayers] = useState<KeyPlayer[]>([]);
  const [awayKeyPlayers, setAwayKeyPlayers] = useState<KeyPlayer[]>([]);

  useEffect(() => {
    const fetchKeyPlayers = async (teamName: string, setter: (p: KeyPlayer[]) => void) => {
      try {
        const res = await client.get(`/scouting/team-key-players/${encodeURIComponent(teamName)}`, {
          params: { season: apiSeason },
        });
        const data = res as unknown as { key_players?: KeyPlayer[] };
        setter(data.key_players ?? []);
      } catch {
        setter([]);
      }
    };
    fetchKeyPlayers(match.home_team, setHomeKeyPlayers);
    fetchKeyPlayers(match.away_team, setAwayKeyPlayers);
  }, [match.home_team, match.away_team, apiSeason]);
  const [selectedBetType, setSelectedBetType] = useState<string | null>(null);
  const [betting, setBetting] = useState<string | null>(null);
  const [betMsg, setBetMsg] = useState('');
  const [betSuccess, setBetSuccess] = useState(false);

  const calcOdds = (prob: number) => prob > 0 ? Math.round((1 / prob) * 0.95 * 100) / 100 : 0;

  const handleBet = async (betType: string, prob: number) => {
    if (!isLoggedIn || !prob) return;
    const odds = calcOdds(prob);
    setBetting(betType);
    setBetMsg('');
    setBetSuccess(false);
    try {
      await onBet(match.match_id, betType, selectedAmount, odds);
      setBetSuccess(true);
      setBetMsg(`Bet placed! ${selectedAmount.toLocaleString()} coins @ ${odds}`);
      setSelectedBetType(null);
      setTimeout(() => { setBetMsg(''); setBetSuccess(false); }, 3000);
    } catch (err: unknown) {
      setBetSuccess(false);
      setBetMsg(err instanceof Error ? err.message : 'Bet failed');
      setTimeout(() => setBetMsg(''), 3000);
    } finally {
      setBetting(null);
    }
  };

  const bets = [
    { type: 'home_win', label: match.home_team.split(' ').slice(-1)[0], prob: prediction?.prob_home_win ?? 0 },
    { type: 'draw', label: 'Draw', prob: prediction?.prob_draw ?? 0 },
    { type: 'away_win', label: match.away_team.split(' ').slice(-1)[0], prob: prediction?.prob_away_win ?? 0 },
  ];

  const selectedBet = bets.find((b) => b.type === selectedBetType);
  const potentialPayout = selectedBet && selectedBet.prob > 0
    ? Math.round(selectedAmount * calcOdds(selectedBet.prob))
    : null;

  const h2h = matchDetail?.head_to_head;

  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4 space-y-3">
      {/* Match header with form badges */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <div className="flex items-center gap-1.5 min-w-0">
              <TeamLogo shortName={match.home_team.slice(0, 3).toUpperCase()} size="sm" />
              <span className="text-xs font-medium text-slate-200 truncate">{match.home_team}</span>
            </div>
            <span className="text-[10px] text-slate-600 shrink-0">vs</span>
            <div className="flex items-center gap-1.5 min-w-0">
              <TeamLogo shortName={match.away_team.slice(0, 3).toUpperCase()} size="sm" />
              <span className="text-xs font-medium text-slate-200 truncate">{match.away_team}</span>
            </div>
          </div>
          <span className="text-[10px] font-mono text-slate-500 shrink-0 ml-2">{formatKickoff(match.kickoff)}</span>
        </div>

        {/* Form badges row */}
        {detailLoading ? (
          <Skeleton className="h-4 w-40 rounded" />
        ) : matchDetail && (matchDetail.home_form || matchDetail.away_form) ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {matchDetail.home_form?.results && (
                <FormBadges results={matchDetail.home_form.results} />
              )}
            </div>
            <div className="flex items-center gap-1.5">
              {matchDetail.away_form?.results && (
                <FormBadges results={matchDetail.away_form.results} />
              )}
            </div>
          </div>
        ) : null}

        {/* Key players row */}
        {(homeKeyPlayers.length > 0 || awayKeyPlayers.length > 0) && (
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-1 min-w-0 flex-1">
              <span className="text-[10px] shrink-0">⚽</span>
              <span className="text-[10px] text-slate-400 truncate">
                {homeKeyPlayers.map((p) => `${p.name.split(' ').slice(-1)[0]} (${p.goals}G ${p.assists}A)`).join(' · ')}
              </span>
            </div>
            <div className="flex items-center gap-1 min-w-0 flex-1 justify-end">
              <span className="text-[10px] text-slate-400 truncate text-right">
                {awayKeyPlayers.map((p) => `${p.name.split(' ').slice(-1)[0]} (${p.goals}G ${p.assists}A)`).join(' · ')}
              </span>
              <span className="text-[10px] shrink-0">⚽</span>
            </div>
          </div>
        )}

        {/* H2H record */}
        {!detailLoading && h2h && h2h.matches > 0 && (
          <div className="text-[10px] font-mono text-slate-500 text-center">
            H2H: {h2h.team1_wins}W {h2h.draws}D {h2h.team2_wins}L
          </div>
        )}
      </div>

      {/* Probability bar */}
      {predLoading ? (
        <Skeleton className="h-2 rounded w-full" />
      ) : prediction ? (
        <div className="space-y-1">
          <ProbabilityBar
            home={prediction.prob_home_win}
            draw={prediction.prob_draw}
            away={prediction.prob_away_win}
          />
          <div className="flex justify-between text-[10px] font-mono text-slate-500">
            <span>{(prediction.prob_home_win * 100).toFixed(0)}%</span>
            <span>{(prediction.prob_draw * 100).toFixed(0)}%</span>
            <span>{(prediction.prob_away_win * 100).toFixed(0)}%</span>
          </div>
        </div>
      ) : (
        <div className="h-2 bg-slate-700/40 rounded" />
      )}

      {/* Key factors */}
      {prediction?.key_factors && prediction.key_factors.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {prediction.key_factors.slice(0, 3).map((factor, i) => (
            <span
              key={i}
              className="text-[9px] bg-slate-700/50 border border-slate-600/40 text-slate-400 rounded px-1.5 py-0.5"
            >
              {typeof factor === 'string' ? factor : factor.factor}
            </span>
          ))}
        </div>
      )}

      {/* Bet buttons */}
      {!isLoggedIn ? (
        <p className="text-xs text-slate-500 text-center py-1">Login to bet on this match</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            {bets.map(({ type, label, prob }) => {
              const odds = calcOdds(prob);
              const ev = prob > 0 ? (prob * odds - 1) : -1;
              const isPositiveEV = ev >= 0;
              const isSelected = selectedBetType === type;
              return (
                <button
                  key={type}
                  onClick={() => setSelectedBetType(isSelected ? null : type)}
                  disabled={!!betting || !prediction}
                  className={clsx(
                    'flex flex-col items-center py-2 px-1 rounded border transition-colors text-center',
                    'disabled:opacity-40 disabled:cursor-not-allowed',
                    isSelected
                      ? 'bg-amber-500/20 border-amber-500/50 ring-1 ring-amber-500/40'
                      : isPositiveEV
                        ? 'bg-emerald-500/10 border-emerald-500/30 hover:bg-emerald-500/20'
                        : 'bg-slate-700/40 border-slate-600/40 hover:bg-slate-700/60',
                    betting === type && 'opacity-60'
                  )}
                >
                  <span className="text-[10px] text-slate-400 truncate w-full text-center">{label}</span>
                  <span className={clsx(
                    'font-mono text-sm font-bold',
                    isSelected ? 'text-amber-400' : isPositiveEV ? 'text-emerald-400' : 'text-slate-300'
                  )}>
                    {odds > 0 ? odds.toFixed(2) : '—'}
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">
                    {prob > 0 ? `${(prob * 100).toFixed(0)}%` : '—'}
                  </span>
                  {prob > 0 && (
                    <span className={clsx('text-[9px] font-mono mt-0.5', isPositiveEV ? 'text-emerald-400' : 'text-red-400')}>
                      {isPositiveEV ? '+' : ''}{(ev * 100).toFixed(1)}% EV
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Amount selector + potential payout */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Coins className="w-3 h-3 text-amber-400 shrink-0" />
              <span className="text-[10px] text-slate-500 font-mono">{userCoins.toLocaleString()}</span>
              <div className="flex items-center gap-1 ml-auto">
                {BET_AMOUNTS.map((amt) => (
                  <button
                    key={amt}
                    onClick={() => setSelectedAmount(amt)}
                    className={clsx(
                      'text-[10px] font-mono px-1.5 py-0.5 rounded transition-colors',
                      selectedAmount === amt
                        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                        : 'text-slate-500 border border-slate-700 hover:text-slate-300'
                    )}
                  >
                    {amt >= 1000 ? `${amt / 1000}K` : amt}
                  </button>
                ))}
                <input
                  type="number"
                  min={100}
                  max={userCoins}
                  value={selectedAmount}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v) && v >= 0) setSelectedAmount(v);
                  }}
                  className="w-16 text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-700 border border-slate-600 text-amber-400 text-center focus:outline-none focus:border-amber-500/50"
                  placeholder="Custom"
                />
              </div>
            </div>

            {potentialPayout != null && (
              <p className="text-[10px] font-mono text-amber-400/80 text-right">
                Potential win: {potentialPayout.toLocaleString()} coins
              </p>
            )}
          </div>

          {/* Place bet button — shown when a bet type is selected */}
          {selectedBetType && selectedBet && (
            <button
              onClick={() => handleBet(selectedBet.type, selectedBet.prob)}
              disabled={!!betting || userCoins < selectedAmount}
              className={clsx(
                'w-full text-xs font-semibold py-2 rounded border transition-colors',
                'bg-amber-500/20 border-amber-500/40 text-amber-300 hover:bg-amber-500/30',
                'disabled:opacity-40 disabled:cursor-not-allowed',
                betting && 'opacity-60'
              )}
            >
              {betting ? 'Placing…' : `Place bet — ${selectedAmount.toLocaleString()} on ${selectedBet.label}`}
            </button>
          )}

          {betMsg && (
            <p className={clsx(
              'text-[10px] font-mono text-center',
              betSuccess ? 'text-emerald-400' : 'text-red-400'
            )}>
              {betMsg}
            </p>
          )}
        </>
      )}
    </div>
  );
}

// ─── EV Calculator subcomponent ───────────────────────────────────────────────

interface EVCalculatorProps {
  matches: ApiMatch[];
  matchesLoading: boolean;
}

function EVCalculator({ matches, matchesLoading }: EVCalculatorProps) {
  const [selectedMatchId, setSelectedMatchId] = useState<number | ''>('');
  const [rows, setRows] = useState<OddsRow[]>([
    { id: 1, market: '1X2 Home', selection: 'Home Win', odds: '', bookmaker: '' },
  ]);
  const [results, setResults] = useState<EVResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (matches.length > 0 && selectedMatchId === '') {
      setSelectedMatchId(matches[0].match_id);
    }
  }, [matches, selectedMatchId]);

  const addRow = () => {
    setRows((r) => [...r, { id: Date.now(), market: '1X2 Home', selection: 'Home Win', odds: '', bookmaker: '' }]);
  };

  const removeRow = (id: number) => {
    setRows((r) => r.filter((row) => row.id !== id));
  };

  const handleCalc = async () => {
    if (!selectedMatchId) { setError('Please select a match first.'); return; }
    const validRows = rows.filter((r) => r.odds && parseFloat(r.odds) > 1);
    if (validRows.length === 0) { setError('Add at least one betting line with valid odds (> 1.0).'); return; }

    setLoading(true); setError(null); setResults(null);
    try {
      const lines = validRows.map((r) => ({
        market: r.market, selection: r.selection,
        odds: parseFloat(r.odds), bookmaker: r.bookmaker || 'Unknown',
      }));
      const res = await client.post('/betting/ev', { match_id: selectedMatchId, lines });
      const data = res as unknown as { results?: EVResult[] } | { predictions?: EVResult[] } | EVResult[];
      const evResults: EVResult[] = Array.isArray(data)
        ? data
        : (data as { results?: EVResult[] }).results ?? (data as { predictions?: EVResult[] }).predictions ?? [];
      setResults(evResults);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to calculate EV');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Calculator className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-semibold text-slate-200">EV Calculator</h2>
        </div>
        <div className="flex items-center gap-2">
          {matchesLoading ? (
            <Skeleton className="h-7 w-48 rounded" />
          ) : (
            <select
              value={selectedMatchId}
              onChange={(e) => { setSelectedMatchId(e.target.value ? Number(e.target.value) : ''); setResults(null); setError(null); }}
              className="bg-slate-700 border border-slate-600 rounded text-xs text-slate-300 px-2.5 py-1.5 focus:outline-none"
            >
              <option value="">Select a match…</option>
              {matches.map((m) => (
                <option key={m.match_id} value={m.match_id}>{m.home_team} vs {m.away_team}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-700/50">
              {['Market', 'Selection', 'Odds', 'Bookmaker', ''].map((h) => (
                <th key={h} className="text-left px-2 py-2 text-slate-500 font-medium uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-slate-700/30">
                <td className="px-2 py-1.5">
                  <select
                    value={row.market}
                    onChange={(e) => setRows((r) => r.map((x) => x.id === row.id ? { ...x, market: e.target.value, selection: e.target.value } : x))}
                    className="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-300 focus:outline-none w-32"
                  >
                    {MARKET_OPTIONS.map((m) => <option key={m}>{m}</option>)}
                  </select>
                </td>
                <td className="px-2 py-1.5">
                  <input value={row.selection} onChange={(e) => setRows((r) => r.map((x) => x.id === row.id ? { ...x, selection: e.target.value } : x))}
                    className="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-300 focus:outline-none w-28" placeholder="Selection" />
                </td>
                <td className="px-2 py-1.5">
                  <input value={row.odds} onChange={(e) => setRows((r) => r.map((x) => x.id === row.id ? { ...x, odds: e.target.value } : x))}
                    className="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-300 focus:outline-none w-20 font-mono"
                    placeholder="2.00" type="number" step="0.01" min="1" />
                </td>
                <td className="px-2 py-1.5">
                  <input value={row.bookmaker} onChange={(e) => setRows((r) => r.map((x) => x.id === row.id ? { ...x, bookmaker: e.target.value } : x))}
                    className="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-300 focus:outline-none w-28" placeholder="Bookmaker" />
                </td>
                <td className="px-2 py-1.5">
                  <button onClick={() => removeRow(row.id)} className="text-slate-600 hover:text-red-400 transition-colors text-base leading-none">×</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-2">
        <button onClick={addRow} className="text-xs text-slate-400 hover:text-slate-200 transition-colors border border-slate-600 rounded px-3 py-1.5">
          + Add row
        </button>
        <button onClick={handleCalc} disabled={loading}
          className="text-xs font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 rounded px-4 py-1.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
          {loading ? 'Calculating…' : 'Calculate EV'}
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded px-3 py-2">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />{error}
        </div>
      )}

      {results && results.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-slate-700/50">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Results</p>
          {results.map((r, i) => (
            <div key={i} className={clsx('flex items-center justify-between p-2.5 rounded border',
              r.verdict === 'strong_value' && 'bg-emerald-500/10 border-emerald-500/30',
              r.verdict === 'value' && 'bg-emerald-500/5 border-emerald-500/20',
              r.verdict === 'marginal' && 'bg-amber-500/5 border-amber-500/20',
              r.verdict === 'no_value' && 'bg-slate-700/20 border-slate-700/40',
            )}>
              <div className="flex items-center gap-3">
                <Badge variant={r.verdict} size="xs" />
                <div>
                  <p className="text-xs font-medium text-slate-200">{r.selection}</p>
                  <p className="text-[10px] text-slate-500">{r.market} · {r.bookmaker} · {r.odds}</p>
                </div>
              </div>
              <div className="text-right">
                <p className={clsx('text-sm font-mono font-semibold', r.ev >= 0 ? 'text-emerald-400' : 'text-red-400')}>{formatEV(r.ev)}</p>
                <p className="text-[10px] text-slate-500">Model: {(r.model_prob * 100).toFixed(0)}% / Impl: {(r.implied_prob * 100).toFixed(0)}%</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {results && results.length === 0 && (
        <div className="text-xs text-slate-500 pt-2 border-t border-slate-700/50">No EV results returned. Check the match and odds inputs.</div>
      )}

      {results && results.filter((r) => r.kelly_fraction > 0).length > 0 && (
        <div className="pt-2 border-t border-slate-700/50">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Kelly Criterion — Stake Sizing</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {results.filter((r) => r.kelly_fraction > 0).map((r) => (
              <div key={r.selection} className="bg-slate-800/60 border border-slate-700/50 rounded p-3">
                <p className="text-xs font-medium text-slate-300 mb-1">{r.selection}</p>
                <p className="text-xs text-slate-500">{r.bookmaker} @ {r.odds}</p>
                <div className="mt-2 flex items-baseline gap-1">
                  <span className="font-mono text-lg font-bold text-emerald-400">{(r.kelly_fraction * 100 / 4).toFixed(1)}%</span>
                  <span className="text-[10px] text-slate-600">of bankroll</span>
                </div>
                <p className="text-[10px] text-slate-600 mt-0.5">¼ Kelly (conservative)</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Matchday tab type ───────────────────────────────────────────────────────

type MatchdayTab = number | 'all';

// ─── Main component ───────────────────────────────────────────────────────────

export default function BettingEV() {
  const { league, apiSeason } = useLeague();
  const { user, refreshBalance } = useUser();

  const [upcomingMatches, setUpcomingMatches] = useState<ApiMatch[]>([]);
  const [upcomingLoading, setUpcomingLoading] = useState(true);
  const [predictions, setPredictions] = useState<Record<number, Prediction>>({});
  const [predLoadingIds, setPredLoadingIds] = useState<Set<number>>(new Set());
  const [matchDetails, setMatchDetails] = useState<Record<number, MatchDetail>>({});
  const [detailLoadingIds, setDetailLoadingIds] = useState<Set<number>>(new Set());

  const [matchdayTab, setMatchdayTab] = useState<MatchdayTab>('all');

  const [matches, setMatches] = useState<ApiMatch[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(true);

  const [valueBets, setValueBets] = useState<ValueBet[]>([]);
  const [valueBetsLoading, setValueBetsLoading] = useState(true);
  const [valueBetsError, setValueBetsError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'strong' | 'value'>('all');
  const [minEv, setMinEv] = useState<string>('0.01');

  // Fetch upcoming scheduled matches (next 14 days)
  useEffect(() => {
    setUpcomingLoading(true);
    setUpcomingMatches([]);
    setPredictions({});
    setMatchDetails({});
    client.get('/matches', { params: { league, season: apiSeason, status: 'SCHEDULED', page_size: 50 } })
      .then((res) => {
        const data = res as unknown as { matches?: ApiMatch[] } | ApiMatch[];
        const list: ApiMatch[] = Array.isArray(data) ? data : (data as { matches?: ApiMatch[] }).matches ?? [];
        // Sort by kickoff ascending
        const sorted = [...list].sort((a, b) => new Date(a.kickoff).getTime() - new Date(b.kickoff).getTime());
        setUpcomingMatches(sorted);

        // Fetch predictions and match details for each match
        sorted.forEach((m) => {
          // Prediction
          setPredLoadingIds((s) => new Set(s).add(m.match_id));
          client.get(`/predictions/${m.match_id}`)
            .then((pres) => {
              const raw = pres as unknown as ApiPredictionResponse;
              const p = normalizePrediction(raw);
              if (p) {
                setPredictions((prev) => ({ ...prev, [m.match_id]: { ...p, match_id: m.match_id } }));
              }
            })
            .catch(() => {})
            .finally(() => {
              setPredLoadingIds((s) => { const ns = new Set(s); ns.delete(m.match_id); return ns; });
            });

          // Match detail (form + H2H)
          setDetailLoadingIds((s) => new Set(s).add(m.match_id));
          client.get(`/matches/${m.match_id}`)
            .then((dres) => {
              const detail = dres as unknown as MatchDetail;
              if (detail) {
                setMatchDetails((prev) => ({ ...prev, [m.match_id]: detail }));
              }
            })
            .catch(() => {})
            .finally(() => {
              setDetailLoadingIds((s) => { const ns = new Set(s); ns.delete(m.match_id); return ns; });
            });
        });
      })
      .catch(() => setUpcomingMatches([]))
      .finally(() => setUpcomingLoading(false));
  }, [league, apiSeason]);

  // Fetch all matches (for EV calculator)
  useEffect(() => {
    setMatchesLoading(true);
    setMatches([]);
    client.get('/matches', { params: { league, season: apiSeason, page_size: 50 } })
      .then((res) => {
        const data = res as unknown as { matches?: ApiMatch[] } | ApiMatch[];
        const list: ApiMatch[] = Array.isArray(data) ? data : (data as { matches?: ApiMatch[] }).matches ?? [];
        setMatches(list);
      })
      .catch(() => setMatches([]))
      .finally(() => setMatchesLoading(false));
  }, [league, apiSeason]);

  const fetchValueBets = useCallback(() => {
    setValueBetsLoading(true);
    setValueBetsError(null);
    const evThreshold = parseFloat(minEv) || 0.01;
    client.get('/betting/value-bets', { params: { league, min_ev: evThreshold } })
      .then((res) => {
        const data = res as unknown as { value_bets?: ValueBet[] } | ValueBet[];
        const bets: ValueBet[] = Array.isArray(data) ? data : (data as { value_bets?: ValueBet[] }).value_bets ?? [];
        setValueBets(bets);
      })
      .catch((err) => {
        setValueBetsError(err instanceof Error ? err.message : 'Failed to load value bets');
        setValueBets([]);
      })
      .finally(() => setValueBetsLoading(false));
  }, [league, minEv]);

  useEffect(() => { fetchValueBets(); }, [league]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleBet = async (matchId: number, betType: string, amount: number, _odds: number) => {
    if (!user) throw new Error('Not logged in');
    await client.post('/user/bet', {
      user_id: user.user_id,
      match_id: matchId,
      bet_type: betType,
      amount,
    });
    await refreshBalance();
  };

  const filteredBets = valueBets.filter((b) => {
    if (filter === 'strong') return b.ev_pct >= 10;
    if (filter === 'value') return b.ev_pct >= 5;
    return true;
  });

  // Group matches by matchday
  const matchdaySet = Array.from(new Set(upcomingMatches.map((m) => m.matchday))).sort((a, b) => a - b);

  const tabMatches = matchdayTab === 'all'
    ? upcomingMatches
    : upcomingMatches.filter((m) => m.matchday === matchdayTab);

  return (
    <div className="space-y-5 max-w-7xl">
      {/* Disclaimer */}
      <div className="flex items-start gap-2 bg-amber-500/5 border border-amber-500/20 rounded-lg px-4 py-2.5">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
        <p className="text-xs text-amber-400/80">
          EV calculations are model estimates only. Past performance does not guarantee future results. Gamble responsibly.
        </p>
      </div>

      {/* Upcoming Matches */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-semibold text-slate-200">Upcoming Matches</h2>
          {upcomingLoading && <span className="text-xs text-slate-500">Loading…</span>}
          {!upcomingLoading && (
            <span className="text-xs text-slate-500">{upcomingMatches.length} matches</span>
          )}
        </div>

        {/* Matchday tabs */}
        <div className="flex flex-wrap gap-1 mb-4">
          {([
            { key: 'all' as MatchdayTab, label: 'All', count: upcomingMatches.length },
            ...matchdaySet.map((md) => ({
              key: md as MatchdayTab,
              label: `MD ${md}`,
              count: upcomingMatches.filter((m) => m.matchday === md).length,
            })),
          ]).map(({ key, label, count }) => (
            <button
              key={String(key)}
              onClick={() => setMatchdayTab(key)}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors border',
                matchdayTab === key
                  ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
                  : 'bg-slate-800/50 border-slate-700/50 text-slate-500 hover:text-slate-300'
              )}
            >
              {label}
              <span className={clsx(
                'text-[10px] font-mono rounded-full px-1',
                matchdayTab === key ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-700 text-slate-500'
              )}>
                {count}
              </span>
            </button>
          ))}
        </div>

        {upcomingLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-56 rounded-lg" />
            ))}
          </div>
        ) : tabMatches.length === 0 ? (
          <div className="text-xs text-slate-500 bg-slate-800/30 border border-slate-700/30 rounded-lg px-4 py-6 text-center">
            No scheduled matches for this period.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {tabMatches.map((match) => (
              <MatchCard
                key={match.match_id}
                match={match}
                prediction={predictions[match.match_id] ?? null}
                predLoading={predLoadingIds.has(match.match_id)}
                matchDetail={matchDetails[match.match_id] ?? null}
                detailLoading={detailLoadingIds.has(match.match_id)}
                userCoins={user?.coins ?? 0}
                isLoggedIn={!!user}
                apiSeason={apiSeason}
                onBet={handleBet}
              />
            ))}
          </div>
        )}
      </div>

      {/* EV Calculator */}
      <EVCalculator matches={matches} matchesLoading={matchesLoading} />

      {/* Value Bets Scanner */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">Value Bet Scanner</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {valueBetsLoading ? 'Loading…' : `${filteredBets.length} bets found with positive EV`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-500">Min EV</span>
              <input
                value={minEv} onChange={(e) => setMinEv(e.target.value)}
                onBlur={fetchValueBets} onKeyDown={(e) => e.key === 'Enter' && fetchValueBets()}
                type="number" step="0.01" min="0"
                className="bg-slate-700 border border-slate-600 rounded text-xs text-slate-300 px-2 py-1 w-16 font-mono focus:outline-none"
                placeholder="0.01"
              />
            </div>
            <div className="flex bg-slate-800 border border-slate-700 rounded overflow-hidden">
              {(['all', 'value', 'strong'] as const).map((f) => (
                <button key={f} onClick={() => setFilter(f)}
                  className={clsx('px-3 py-1.5 text-xs font-medium transition-colors',
                    filter === f ? 'bg-slate-700 text-slate-200' : 'text-slate-500 hover:text-slate-300')}>
                  {f === 'all' ? 'All EV+' : f === 'value' ? 'EV > 5%' : 'EV > 10%'}
                </button>
              ))}
            </div>
            <button onClick={fetchValueBets} disabled={valueBetsLoading}
              className="p-1.5 text-slate-500 hover:text-slate-300 border border-slate-700 rounded transition-colors disabled:opacity-50">
              <RefreshCw className={clsx('w-3.5 h-3.5', valueBetsLoading && 'animate-spin')} />
            </button>
          </div>
        </div>

        {valueBetsError && (
          <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded px-3 py-2 mb-3">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />{valueBetsError}
          </div>
        )}

        {valueBetsLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 rounded" />)}
          </div>
        ) : (
          <DataTable
            columns={VALUE_BET_COLUMNS}
            data={filteredBets as unknown as (ValueBet & Record<string, unknown>)[]}
            rowKey={(r) => `${r.match_id}-${r.market}-${r.selection}`}
            emptyMessage="No value bets found for current filters"
          />
        )}
      </div>
    </div>
  );
}
