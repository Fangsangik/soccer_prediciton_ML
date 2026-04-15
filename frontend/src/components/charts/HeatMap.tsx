import clsx from 'clsx';

interface HeatMapProps {
  data: Record<string, number>;
  maxGoals?: number;
  homeTeam?: string;
  awayTeam?: string;
}

function interpolateColor(value: number, max: number): string {
  const ratio = Math.min(value / max, 1);
  if (ratio === 0) return 'bg-slate-800/40';
  if (ratio < 0.15) return 'bg-slate-700/60';
  if (ratio < 0.3) return 'bg-emerald-900/60';
  if (ratio < 0.5) return 'bg-emerald-800/70';
  if (ratio < 0.7) return 'bg-emerald-700/80';
  if (ratio < 0.85) return 'bg-emerald-600/90';
  return 'bg-emerald-500';
}

export default function HeatMap({
  data,
  maxGoals = 4,
  homeTeam = 'Home',
  awayTeam = 'Away',
}: HeatMapProps) {
  const goals = Array.from({ length: maxGoals + 1 }, (_, i) => i);

  const maxProb = Math.max(...Object.values(data), 0.001);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <div className="text-xs text-slate-500 w-16 shrink-0">{homeTeam} →</div>
        <div className="flex gap-1">
          {goals.map((g) => (
            <div key={g} className="w-8 text-center text-[10px] font-stat text-slate-500">
              {g}
            </div>
          ))}
        </div>
      </div>

      {goals.map((away) => (
        <div key={away} className="flex items-center gap-3">
          <div className="text-[10px] font-stat text-slate-500 w-16 shrink-0 text-right">
            {awayTeam} {away}
          </div>
          <div className="flex gap-1">
            {goals.map((home) => {
              const key = `${home}-${away}`;
              const prob = data[key] ?? 0;
              return (
                <div
                  key={key}
                  className={clsx(
                    'w-8 h-8 rounded flex items-center justify-center',
                    interpolateColor(prob, maxProb)
                  )}
                  title={`${home}-${away}: ${(prob * 100).toFixed(1)}%`}
                >
                  {prob > 0.03 && (
                    <span className="text-[9px] font-stat text-white/80">
                      {(prob * 100).toFixed(0)}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}

      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-slate-700/50">
        <span className="text-[10px] text-slate-600">Probability:</span>
        <div className="flex gap-1">
          {['bg-slate-800/40', 'bg-emerald-900/60', 'bg-emerald-700/80', 'bg-emerald-500'].map(
            (cls, i) => (
              <div key={i} className={clsx('w-4 h-3 rounded-sm', cls)} />
            )
          )}
        </div>
        <span className="text-[10px] text-slate-600">Low → High</span>
      </div>
    </div>
  );
}
