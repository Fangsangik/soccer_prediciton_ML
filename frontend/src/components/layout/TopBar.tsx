import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { ChevronDown, Coins, LogIn, X } from 'lucide-react';
import clsx from 'clsx';
import { useLeague } from '@/contexts/LeagueContext';
import { useUser } from '@/contexts/UserContext';

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/matches': 'Match Predictions',
  '/betting': 'Betting EV',
  '/fpl': 'FPL Optimizer',
  '/scouting': 'Player Scouting',
  '/performance': 'Model Performance',
  '/profile': 'Profile',
};

const LEAGUES = [
  { code: 'PL', label: 'Premier League' },
  { code: 'PD', label: 'La Liga' },
  { code: 'BL1', label: 'Bundesliga' },
  { code: 'SA', label: 'Serie A' },
  { code: 'FL1', label: 'Ligue 1' },
  { code: 'CL', label: 'Champions League' },
  { code: 'EL', label: 'Europa League' },
  { code: 'ECL', label: 'Conference League' },
];

const SEASONS = ['2024/25', '2025/26', '2023/24'];

interface SelectProps {
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}

function Select({ value, options, onChange }: SelectProps) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={clsx(
          'appearance-none bg-slate-800 border border-slate-700 rounded',
          'text-xs text-slate-300 pl-2.5 pr-6 py-1.5',
          'focus:outline-none focus:border-slate-600 cursor-pointer',
          'hover:bg-slate-700/80 transition-colors'
        )}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-1.5 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500 pointer-events-none" />
    </div>
  );
}

function LoginModal({ onClose }: { onClose: () => void }) {
  const { login, register } = useUser();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) return;

    if (mode === 'register' && password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    setError('');
    try {
      if (mode === 'login') {
        await login(username.trim(), password);
      } else {
        await register(username.trim(), password);
      }
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setMode((m) => (m === 'login' ? 'register' : 'login'));
    setError('');
    setPassword('');
    setConfirmPassword('');
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center">
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-80 shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-100">
            {mode === 'login' ? 'Login' : 'Create Account'}
          </h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {mode === 'register' && (
          <p className="text-xs text-slate-400 mb-4">
            Create an account to get <span className="text-amber-400 font-mono">50,000 coins</span>.
          </p>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Username"
            minLength={2}
            maxLength={50}
            className={clsx(
              'w-full bg-slate-800 border border-slate-700 rounded px-3 py-2',
              'text-sm text-slate-200 placeholder-slate-500',
              'focus:outline-none focus:border-emerald-500/50'
            )}
            autoFocus
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            maxLength={128}
            className={clsx(
              'w-full bg-slate-800 border border-slate-700 rounded px-3 py-2',
              'text-sm text-slate-200 placeholder-slate-500',
              'focus:outline-none focus:border-emerald-500/50'
            )}
          />
          {mode === 'register' && (
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm password"
              maxLength={128}
              className={clsx(
                'w-full bg-slate-800 border border-slate-700 rounded px-3 py-2',
                'text-sm text-slate-200 placeholder-slate-500',
                'focus:outline-none focus:border-emerald-500/50'
              )}
            />
          )}
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading || !username.trim() || !password}
            className={clsx(
              'w-full py-2 rounded text-sm font-medium transition-colors',
              'bg-emerald-600 hover:bg-emerald-500 text-white',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {loading
              ? mode === 'login' ? 'Logging in...' : 'Creating...'
              : mode === 'login' ? 'Login' : 'Start with 50,000 coins'}
          </button>
        </form>

        <div className="mt-4 text-center">
          <button
            onClick={switchMode}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            {mode === 'login'
              ? "New? Create Account"
              : "Already have an account? Login"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function TopBar() {
  const location = useLocation();
  const title = PAGE_TITLES[location.pathname] ?? 'Football Analytics';

  const { league, setLeague, season, setSeason } = useLeague();
  const { user, checkin } = useUser();

  const [showLogin, setShowLogin] = useState(false);
  const [checkinLoading, setCheckinLoading] = useState(false);
  const [checkinMsg, setCheckinMsg] = useState('');

  const today = new Date().toISOString().split('T')[0];
  const alreadyCheckedIn = user?.last_checkin === today;

  const handleCheckin = async () => {
    setCheckinLoading(true);
    setCheckinMsg('');
    try {
      const newBalance = await checkin();
      setCheckinMsg(`+100 coins! Balance: ${newBalance.toLocaleString()}`);
      setTimeout(() => setCheckinMsg(''), 3000);
    } catch (err: unknown) {
      setCheckinMsg(err instanceof Error ? err.message : 'Check-in failed');
      setTimeout(() => setCheckinMsg(''), 3000);
    } finally {
      setCheckinLoading(false);
    }
  };

  return (
    <>
      <header className="fixed top-0 left-60 right-0 h-14 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-6 z-10">
        <h1 className="text-sm font-semibold text-slate-100">{title}</h1>

        <div className="flex items-center gap-3">
          <Select
            value={league}
            onChange={setLeague}
            options={LEAGUES.map((l) => ({ value: l.code, label: l.label }))}
          />
          <Select
            value={season}
            onChange={setSeason}
            options={SEASONS.map((s) => ({ value: s, label: s }))}
          />

          <div className="w-px h-5 bg-slate-700" />

          {user ? (
            <div className="flex items-center gap-2">
              {/* Coin balance */}
              <div className="flex items-center gap-1.5 bg-slate-800/60 border border-slate-700/60 rounded px-2.5 py-1.5">
                <Coins className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-xs font-mono font-semibold text-amber-400">
                  {user.coins.toLocaleString()}
                </span>
              </div>

              {/* Check-in button or status */}
              {checkinMsg ? (
                <span className="text-xs font-mono text-emerald-400">{checkinMsg}</span>
              ) : !alreadyCheckedIn ? (
                <button
                  onClick={handleCheckin}
                  disabled={checkinLoading}
                  className={clsx(
                    'text-xs font-medium px-2.5 py-1.5 rounded border transition-colors',
                    'bg-amber-500/10 border-amber-500/30 text-amber-400',
                    'hover:bg-amber-500/20 hover:border-amber-500/50',
                    'disabled:opacity-50 disabled:cursor-not-allowed'
                  )}
                >
                  {checkinLoading ? '...' : 'Check In +100'}
                </button>
              ) : null}

              {/* Username + Admin badge */}
              <span className="text-xs text-slate-400 font-medium">{user.username}</span>
              {user.is_admin && (
                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded border bg-amber-500/10 border-amber-500/30 text-amber-400">
                  Admin
                </span>
              )}
            </div>
          ) : (
            <button
              onClick={() => setShowLogin(true)}
              className={clsx(
                'flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded border transition-colors',
                'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
                'hover:bg-emerald-500/20 hover:border-emerald-500/50'
              )}
            >
              <LogIn className="w-3.5 h-3.5" />
              Login
            </button>
          )}
        </div>
      </header>

      {showLogin && <LoginModal onClose={() => setShowLogin(false)} />}
    </>
  );
}
