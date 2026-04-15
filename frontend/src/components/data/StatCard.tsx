import type { ReactNode } from 'react';
import clsx from 'clsx';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface StatCardProps {
  label: string;
  value: string | number;
  change?: number;
  icon?: ReactNode;
  variant?: 'default' | 'positive' | 'negative' | 'warning';
  sub?: string;
}

const VARIANT_STYLES = {
  default: 'border-slate-700/50',
  positive: 'border-emerald-500/30',
  negative: 'border-red-500/30',
  warning: 'border-amber-500/30',
};

const VARIANT_ICON_BG = {
  default: 'bg-slate-700/50 text-slate-400',
  positive: 'bg-emerald-500/10 text-emerald-400',
  negative: 'bg-red-500/10 text-red-400',
  warning: 'bg-amber-500/10 text-amber-400',
};

export default function StatCard({
  label,
  value,
  change,
  icon,
  variant = 'default',
  sub,
}: StatCardProps) {
  const isPositiveChange = change !== undefined && change > 0;
  const isNegativeChange = change !== undefined && change < 0;

  return (
    <div
      className={clsx(
        'bg-slate-800/50 border rounded-lg p-4 flex flex-col gap-3',
        VARIANT_STYLES[variant]
      )}
    >
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium text-slate-400 uppercase tracking-wide">{label}</p>
        {icon && (
          <span className={clsx('p-1.5 rounded', VARIANT_ICON_BG[variant])}>
            {icon}
          </span>
        )}
      </div>

      <div className="flex items-end justify-between gap-2">
        <p className={clsx('font-stat text-2xl font-semibold leading-none', {
          'text-emerald-400': variant === 'positive',
          'text-red-400': variant === 'negative',
          'text-amber-400': variant === 'warning',
          'text-slate-100': variant === 'default',
        })}>
          {value}
        </p>

        {change !== undefined && (
          <span
            className={clsx('flex items-center gap-0.5 text-xs font-stat font-medium', {
              'text-emerald-400': isPositiveChange,
              'text-red-400': isNegativeChange,
              'text-slate-500': change === 0,
            })}
          >
            {isPositiveChange && <TrendingUp className="w-3 h-3" />}
            {isNegativeChange && <TrendingDown className="w-3 h-3" />}
            {change > 0 ? '+' : ''}{change.toFixed(1)}%
          </span>
        )}
      </div>

      {sub && <p className="text-xs text-slate-500">{sub}</p>}
    </div>
  );
}
