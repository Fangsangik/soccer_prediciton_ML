import clsx from 'clsx';

interface PlayerAvatarProps {
  name: string;
  imageUrl?: string;
  size?: 'sm' | 'md' | 'lg';
  position?: string;
}

const SIZE_CLASSES = {
  sm: { container: 'w-8 h-8', text: 'text-xs', badge: 'text-[8px] px-1 py-px' },
  md: { container: 'w-10 h-10', text: 'text-sm', badge: 'text-[9px] px-1 py-px' },
  lg: { container: 'w-14 h-14', text: 'text-base', badge: 'text-[9px] px-1.5 py-0.5' },
};

const POSITION_COLORS: Record<string, string> = {
  GKP: 'bg-amber-500/80 text-amber-950',
  GK: 'bg-amber-500/80 text-amber-950',
  DEF: 'bg-sky-500/80 text-sky-950',
  DF: 'bg-sky-500/80 text-sky-950',
  CB: 'bg-sky-500/80 text-sky-950',
  LB: 'bg-sky-500/80 text-sky-950',
  RB: 'bg-sky-500/80 text-sky-950',
  MID: 'bg-emerald-500/80 text-emerald-950',
  MF: 'bg-emerald-500/80 text-emerald-950',
  CM: 'bg-emerald-500/80 text-emerald-950',
  CAM: 'bg-emerald-500/80 text-emerald-950',
  FWD: 'bg-red-500/80 text-red-950',
  FW: 'bg-red-500/80 text-red-950',
  RW: 'bg-red-500/80 text-red-950',
  LW: 'bg-red-500/80 text-red-950',
  ST: 'bg-red-500/80 text-red-950',
};

function getInitials(name: string): string {
  const parts = name.trim().split(' ');
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// Deterministic color from name
function getAvatarColor(name: string): string {
  const colors = [
    'bg-slate-600',
    'bg-sky-700',
    'bg-teal-700',
    'bg-emerald-700',
    'bg-cyan-700',
    'bg-indigo-700',
    'bg-stone-600',
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) & 0xfffffff;
  }
  return colors[hash % colors.length];
}

export default function PlayerAvatar({ name, imageUrl, size = 'md', position }: PlayerAvatarProps) {
  const sizes = SIZE_CLASSES[size];
  const initials = getInitials(name);
  const bgColor = getAvatarColor(name);
  const posColor = position ? (POSITION_COLORS[position] ?? 'bg-slate-500/80 text-slate-900') : null;

  return (
    <div className="relative inline-flex shrink-0">
      {imageUrl ? (
        <img
          src={imageUrl}
          alt={name}
          className={clsx(sizes.container, 'rounded-full object-cover border border-slate-700/50')}
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = 'none';
          }}
        />
      ) : (
        <div
          className={clsx(
            sizes.container,
            bgColor,
            'rounded-full flex items-center justify-center border border-slate-700/50'
          )}
        >
          <span className={clsx(sizes.text, 'font-semibold text-white leading-none')}>
            {initials}
          </span>
        </div>
      )}
      {position && posColor && (
        <span
          className={clsx(
            'absolute -bottom-1 -right-1 rounded font-bold leading-none',
            sizes.badge,
            posColor
          )}
        >
          {position}
        </span>
      )}
    </div>
  );
}
