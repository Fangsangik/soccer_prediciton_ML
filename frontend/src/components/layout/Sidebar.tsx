import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Calendar,
  TrendingUp,
  Users,
  Search,
  BarChart3,
  Trophy,
  Flame,
  Activity,
  UserCircle,
  Coins,
} from 'lucide-react';
import clsx from 'clsx';
import { useUser } from '@/contexts/UserContext';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/standings', label: 'Standings', icon: Trophy },
  { to: '/title-race', label: 'Title Race', icon: Flame },
  { to: '/matches', label: 'Matches', icon: Calendar },
  { to: '/betting', label: 'Betting EV', icon: TrendingUp },
  { to: '/fpl', label: 'FPL', icon: Users },
  { to: '/scouting', label: 'Scouting', icon: Search },
  { to: '/performance', label: 'Performance', icon: BarChart3 },
];

export default function Sidebar() {
  const { user } = useUser();

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-slate-950 border-r border-slate-800 flex flex-col z-20">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-14 border-b border-slate-800 shrink-0">
        <div className="w-7 h-7 rounded bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
          <Activity className="w-4 h-4 text-emerald-400" strokeWidth={2} />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-100 leading-none">Football</p>
          <p className="text-xs text-slate-500 leading-none mt-0.5">Analytics</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 overflow-y-auto">
        <ul className="space-y-0.5 px-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon, exact }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={exact}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors relative group',
                    isActive
                      ? 'text-slate-100 bg-slate-800/80'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <span className="absolute left-0 top-1 bottom-1 w-0.5 bg-emerald-500 rounded-r" />
                    )}
                    <Icon
                      className={clsx(
                        'w-4 h-4 shrink-0',
                        isActive ? 'text-emerald-400' : 'text-slate-500 group-hover:text-slate-400'
                      )}
                      strokeWidth={1.75}
                    />
                    <span className="font-medium">{label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}

          {/* Profile link */}
          <li>
            <NavLink
              to="/profile"
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors relative group',
                  isActive
                    ? 'text-slate-100 bg-slate-800/80'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1 bottom-1 w-0.5 bg-emerald-500 rounded-r" />
                  )}
                  <UserCircle
                    className={clsx(
                      'w-4 h-4 shrink-0',
                      isActive ? 'text-emerald-400' : 'text-slate-500 group-hover:text-slate-400'
                    )}
                    strokeWidth={1.75}
                  />
                  <span className="font-medium flex-1">Profile</span>
                  {user && (
                    <span className="flex items-center gap-1 text-[10px] font-mono text-amber-400">
                      <Coins className="w-2.5 h-2.5" />
                      {user.coins >= 1000
                        ? `${(user.coins / 1000).toFixed(1)}k`
                        : user.coins.toLocaleString()}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          </li>
        </ul>
      </nav>

      {/* Footer: data freshness */}
      <div className="px-4 py-3 border-t border-slate-800 shrink-0">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs text-slate-500">Data updated 4 min ago</span>
        </div>
        <p className="text-xs text-slate-600 mt-1">PL 2024/25 \u00b7 GW32</p>
      </div>
    </aside>
  );
}
