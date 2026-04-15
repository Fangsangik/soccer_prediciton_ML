import clsx from 'clsx';
import { TEAM_COLORS } from '@/utils/colors';

interface TeamLogoProps {
  shortName: string;
  crestUrl?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  className?: string;
}

const SIZE_MAP = {
  xs: { outer: 'w-5 h-5', text: 'text-[8px]' },
  sm: { outer: 'w-7 h-7', text: 'text-[10px]' },
  md: { outer: 'w-9 h-9', text: 'text-xs' },
  lg: { outer: 'w-12 h-12', text: 'text-sm' },
};

export default function TeamLogo({ shortName, crestUrl, size = 'md', className }: TeamLogoProps) {
  const colors = TEAM_COLORS[shortName];
  const { outer, text } = SIZE_MAP[size];

  if (crestUrl) {
    return (
      <img
        src={crestUrl}
        alt={shortName}
        className={clsx(outer, 'object-contain', className)}
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = 'none';
        }}
      />
    );
  }

  return (
    <div
      className={clsx(
        outer,
        'rounded flex items-center justify-center font-stat font-bold shrink-0',
        className
      )}
      style={{
        backgroundColor: colors ? `${colors.primary}33` : '#1e293b',
        border: `1px solid ${colors ? `${colors.primary}66` : '#334155'}`,
        color: colors ? colors.primary : '#94a3b8',
      }}
    >
      <span className={text}>{shortName.slice(0, 3)}</span>
    </div>
  );
}
