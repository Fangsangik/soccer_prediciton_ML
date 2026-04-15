import clsx from 'clsx';

interface ProbabilityBarProps {
  homeProb: number;
  drawProb: number;
  awayProb: number;
  homeLabel?: string;
  awayLabel?: string;
  height?: 'sm' | 'md' | 'lg';
  showLabels?: boolean;
}

export default function ProbabilityBar({
  homeProb,
  drawProb,
  awayProb,
  homeLabel = 'H',
  awayLabel = 'A',
  height = 'md',
  showLabels = true,
}: ProbabilityBarProps) {
  const homePct = (homeProb * 100).toFixed(0);
  const drawPct = (drawProb * 100).toFixed(0);
  const awayPct = (awayProb * 100).toFixed(0);

  const heightClass = {
    sm: 'h-5',
    md: 'h-6',
    lg: 'h-8',
  }[height];

  const textClass = {
    sm: 'text-[10px]',
    md: 'text-xs',
    lg: 'text-sm',
  }[height];

  return (
    <div className="space-y-1">
      {showLabels && (
        <div className="flex justify-between text-[10px] text-slate-500 font-medium">
          <span>{homeLabel}</span>
          <span>Draw</span>
          <span>{awayLabel}</span>
        </div>
      )}
      <div className={clsx('flex rounded overflow-hidden w-full', heightClass)}>
        {/* Home win */}
        <div
          className="bg-emerald-500 flex items-center justify-center transition-all"
          style={{ width: `${homeProb * 100}%` }}
        >
          {homeProb > 0.12 && (
            <span className={clsx('font-stat font-semibold text-white', textClass)}>
              {homePct}%
            </span>
          )}
        </div>
        {/* Draw */}
        <div
          className="bg-slate-500 flex items-center justify-center transition-all"
          style={{ width: `${drawProb * 100}%` }}
        >
          {drawProb > 0.1 && (
            <span className={clsx('font-stat font-semibold text-slate-200', textClass)}>
              {drawPct}%
            </span>
          )}
        </div>
        {/* Away win */}
        <div
          className="bg-red-500 flex items-center justify-center transition-all"
          style={{ width: `${awayProb * 100}%` }}
        >
          {awayProb > 0.12 && (
            <span className={clsx('font-stat font-semibold text-white', textClass)}>
              {awayPct}%
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
