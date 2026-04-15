import { useState, useEffect, useMemo } from 'react';
import { Target, Activity, BarChart2, Hash, AlertCircle } from 'lucide-react';
import clsx from 'clsx';
import StatCard from '@/components/data/StatCard';
import DataTable, { type Column } from '@/components/data/DataTable';
import CalibrationPlot from '@/components/charts/CalibrationPlot';
import { Skeleton } from '@/components/data/Skeleton';
import client from '@/api/client';
import { useLeague } from '@/contexts/LeagueContext';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ApiMatch {
  match_id: number;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  kickoff: string;
  status: string;
}

interface ApiPrediction {
  match_id: number;
  probabilities: { home_win: number; draw: number; away_win: number };
  confidence: number;
}

interface PredictionLog {
  match: string;
  predicted: string;
  actual: string;
  correct: boolean;
  confidence: number;
  date: string;
  [key: string]: unknown;
}

interface CalibrationBin {
  predicted: number;
  observed: number;
  count: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getResult(homeScore: number, awayScore: number): 'home_win' | 'draw' | 'away_win' {
  if (homeScore > awayScore) return 'home_win';
  if (homeScore < awayScore) return 'away_win';
  return 'draw';
}

function getPredictedOutcome(probs: { home_win: number; draw: number; away_win: number }): string {
  const max = Math.max(probs.home_win, probs.draw, probs.away_win);
  if (max === probs.home_win) return 'Home Win';
  if (max === probs.away_win) return 'Away Win';
  return 'Draw';
}

function getPredictedKey(probs: { home_win: number; draw: number; away_win: number }): 'home_win' | 'draw' | 'away_win' {
  const max = Math.max(probs.home_win, probs.draw, probs.away_win);
  if (max === probs.home_win) return 'home_win';
  if (max === probs.away_win) return 'away_win';
  return 'draw';
}

function getActualLabel(result: 'home_win' | 'draw' | 'away_win'): string {
  if (result === 'home_win') return 'Home Win';
  if (result === 'away_win') return 'Away Win';
  return 'Draw';
}

function buildCalibrationBins(
  pairs: Array<{ prob: number; outcome: number }>
): CalibrationBin[] {
  const bins: { sum: number; count: number; total: number }[] = Array.from({ length: 10 }, () => ({
    sum: 0,
    count: 0,
    total: 0,
  }));

  for (const { prob, outcome } of pairs) {
    const binIdx = Math.min(Math.floor(prob * 10), 9);
    bins[binIdx].sum += prob;
    bins[binIdx].count += outcome;
    bins[binIdx].total += 1;
  }

  return bins.map((b, i) => ({
    predicted: b.total > 0 ? b.sum / b.total : i * 0.1 + 0.05,
    observed: b.total > 0 ? b.count / b.total : 0,
    count: b.total,
  }));
}

// ─── Table columns ────────────────────────────────────────────────────────────

const LOG_COLUMNS: Column<PredictionLog>[] = [
  {
    key: 'match',
    label: 'Match',
    render: (v) => <span className="font-medium text-slate-200 text-xs">{v as string}</span>,
  },
  {
    key: 'predicted',
    label: 'Predicted',
    render: (v) => <span className="text-xs text-slate-400">{v as string}</span>,
  },
  {
    key: 'actual',
    label: 'Actual',
    render: (v) => <span className="text-xs text-slate-300">{v as string}</span>,
  },
  {
    key: 'correct',
    label: 'Result',
    align: 'center',
    render: (v) =>
      v ? (
        <span className="text-emerald-400 font-mono text-sm">&#10003;</span>
      ) : (
        <span className="text-red-400 font-mono text-sm">&#10007;</span>
      ),
  },
  {
    key: 'confidence',
    label: 'Conf.',
    align: 'right',
    sortable: true,
    render: (v) => (
      <span className="font-mono text-xs text-slate-400">{((v as number) * 100).toFixed(0)}%</span>
    ),
  },
  {
    key: 'date',
    label: 'Date',
    align: 'right',
    render: (v) => <span className="font-mono text-xs text-slate-500">{v as string}</span>,
  },
];

// ─── Main component ───────────────────────────────────────────────────────────

export default function ModelPerformance() {
  const { league, apiSeason } = useLeague();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [predictionLog, setPredictionLog] = useState<PredictionLog[]>([]);
  const [calibrationPairs, setCalibrationPairs] = useState<Array<{ prob: number; outcome: number }>>([]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setPredictionLog([]);
    setCalibrationPairs([]);

    async function load() {
      // Fetch finished matches for selected season
      const matchesRes = await (client.get('/matches', {
        params: { league, season: apiSeason, status: 'FINISHED', page_size: 50 },
      }) as Promise<{ matches: ApiMatch[] }>);

      const matches: ApiMatch[] = matchesRes.matches ?? [];
      if (matches.length === 0) return;

      // Fetch predictions in parallel, ignore failures
      const predEntries = await Promise.all(
        matches.map(async (m) => {
          try {
            const pred = await (client.get(`/predictions/${m.match_id}`) as Promise<ApiPrediction>);
            return { match: m, pred };
          } catch {
            return null;
          }
        })
      );

      if (cancelled) return;

      const logs: PredictionLog[] = [];
      const pairs: Array<{ prob: number; outcome: number }> = [];

      for (const entry of predEntries) {
        if (!entry) continue;
        const { match, pred } = entry;
        if (match.home_score == null || match.away_score == null) continue;

        const actual = getResult(match.home_score, match.away_score);
        const predictedKey = getPredictedKey(pred.probabilities);
        const correct = predictedKey === actual;

        logs.push({
          match: `${match.home_team.substring(0, 3).toUpperCase()} vs ${match.away_team.substring(0, 3).toUpperCase()}`,
          predicted: getPredictedOutcome(pred.probabilities),
          actual: getActualLabel(actual),
          correct,
          confidence: pred.confidence,
          date: match.kickoff.split('T')[0],
        });

        // Add calibration pairs for all three outcomes
        const outcomes: Array<{ prob: number; outcome: number }> = [
          { prob: pred.probabilities.home_win, outcome: actual === 'home_win' ? 1 : 0 },
          { prob: pred.probabilities.draw, outcome: actual === 'draw' ? 1 : 0 },
          { prob: pred.probabilities.away_win, outcome: actual === 'away_win' ? 1 : 0 },
        ];
        pairs.push(...outcomes);
      }

      if (!cancelled) {
        setPredictionLog(logs);
        setCalibrationPairs(pairs);
      }
    }

    load()
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [league, apiSeason]);

  // Computed metrics
  const metrics = useMemo(() => {
    if (predictionLog.length === 0) return null;
    const correct = predictionLog.filter((p) => p.correct).length;
    const total = predictionLog.length;
    const accuracy = (correct / total) * 100;

    // Brier score from calibration pairs
    let brierSum = 0;
    for (const { prob, outcome } of calibrationPairs) {
      brierSum += (prob - outcome) ** 2;
    }
    const brier = calibrationPairs.length > 0 ? brierSum / calibrationPairs.length : 0;

    return { correct, total, accuracy, brier };
  }, [predictionLog, calibrationPairs]);

  const calibrationData = useMemo(
    () => buildCalibrationBins(calibrationPairs),
    [calibrationPairs]
  );

  if (loading) {
    return (
      <div className="space-y-5 max-w-7xl">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20 rounded-lg" />)}
        </div>
        <Skeleton className="h-64 rounded-lg" />
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          <Skeleton className="h-64 rounded-lg" />
          <Skeleton className="h-64 rounded-lg" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-500">
        <AlertCircle className="w-10 h-10 mb-3 text-red-500/50" />
        <p className="text-sm text-red-400">Failed to load performance data</p>
        <p className="text-xs mt-1 text-slate-600">{error}</p>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-500">
        <AlertCircle className="w-10 h-10 mb-3 text-slate-600" />
        <p className="text-sm">No finished matches with predictions found for {league}</p>
      </div>
    );
  }

  const calibrationStatus = metrics.brier < 0.22 ? 'Well calibrated' : metrics.brier < 0.235 ? 'Acceptable' : 'Needs improvement';
  const calibrationColor = metrics.brier < 0.22 ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' : metrics.brier < 0.235 ? 'text-amber-400 bg-amber-500/10 border-amber-500/20' : 'text-red-400 bg-red-500/10 border-red-500/20';

  return (
    <div className="space-y-5 max-w-7xl">
      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Overall Accuracy"
          value={`${metrics.accuracy.toFixed(1)}%`}
          variant="positive"
          icon={<Target className="w-3.5 h-3.5" />}
        />
        <StatCard
          label="Brier Score"
          value={metrics.brier.toFixed(3)}
          variant="positive"
          sub="Lower is better"
          icon={<Activity className="w-3.5 h-3.5" />}
        />
        <StatCard
          label="Correct"
          value={`${metrics.correct}/${metrics.total}`}
          sub={`${metrics.accuracy.toFixed(1)}% accuracy`}
          icon={<BarChart2 className="w-3.5 h-3.5" />}
        />
        <StatCard
          label="Total Predictions"
          value={metrics.total.toLocaleString()}
          sub={`${league} · finished matches`}
          icon={<Hash className="w-3.5 h-3.5" />}
        />
      </div>

      {/* Calibration plot */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">Calibration Curve</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Predicted probability vs. observed outcome frequency — dashed = perfect calibration
            </p>
          </div>
          <span className={clsx('text-xs font-mono rounded px-2 py-1 border', calibrationColor)}>
            {calibrationStatus}
          </span>
        </div>
        <CalibrationPlot data={calibrationData} />
      </div>

      {/* Recent predictions log */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
            Recent Predictions
          </h2>
          <span className="text-xs text-slate-500 font-mono">
            {predictionLog.filter((p) => p.correct).length}/{predictionLog.length} correct
          </span>
        </div>
        {predictionLog.length === 0 ? (
          <div className="flex items-center gap-2 justify-center py-8 text-slate-500">
            <AlertCircle className="w-4 h-4" />
            <span className="text-xs">No prediction data available</span>
          </div>
        ) : (
          <DataTable
            columns={LOG_COLUMNS}
            data={predictionLog}
            rowKey={(r) => r.match + r.date}
            compact
          />
        )}
      </div>
    </div>
  );
}
