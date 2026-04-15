import clsx from 'clsx';
import { RESULT_COLORS, VERDICT_COLORS, POSITION_COLORS } from '@/utils/colors';

type BadgeVariant =
  | 'W' | 'D' | 'L'
  | 'strong_value' | 'value' | 'marginal' | 'no_value'
  | 'GKP' | 'DEF' | 'MID' | 'FWD'
  | 'scheduled' | 'in_play' | 'finished' | 'postponed'
  | 'default';

interface BadgeProps {
  variant: BadgeVariant;
  label?: string;
  size?: 'xs' | 'sm';
}

const STATUS_STYLES: Record<string, string> = {
  scheduled: 'bg-slate-700/50 text-slate-400 border-slate-600/30',
  in_play: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
  finished: 'bg-slate-700/30 text-slate-500 border-slate-700/30',
  postponed: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  default: 'bg-slate-700/50 text-slate-400 border-slate-600/30',
};

function getStyles(variant: BadgeVariant): string {
  if (variant === 'W' || variant === 'D' || variant === 'L') {
    return `${RESULT_COLORS[variant].bg}/20 ${RESULT_COLORS[variant].text} border ${RESULT_COLORS[variant].border}/30`;
  }
  if (variant in VERDICT_COLORS) {
    const v = VERDICT_COLORS[variant as keyof typeof VERDICT_COLORS];
    return `${v.bg} ${v.text} border ${v.border}`;
  }
  if (variant in POSITION_COLORS) {
    return `border ${POSITION_COLORS[variant as keyof typeof POSITION_COLORS]}`;
  }
  return STATUS_STYLES[variant] ?? STATUS_STYLES.default;
}

function getLabel(variant: BadgeVariant, label?: string): string {
  if (label) return label;
  if (variant === 'strong_value') return 'Strong Value';
  if (variant === 'no_value') return 'No Value';
  if (variant === 'in_play') return 'Live';
  return variant.toString().toUpperCase();
}

export default function Badge({ variant, label, size = 'sm' }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center border rounded font-medium font-stat',
        size === 'xs' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-0.5',
        getStyles(variant)
      )}
    >
      {variant === 'in_play' && (
        <span className="w-1 h-1 rounded-full bg-emerald-400 mr-1 animate-pulse" />
      )}
      {getLabel(variant, label)}
    </span>
  );
}
