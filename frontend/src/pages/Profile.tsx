import { useState, useEffect } from 'react';
import clsx from 'clsx';
import { Coins, CheckCircle, Clock, Trophy, TrendingUp, TrendingDown, Minus, Shield } from 'lucide-react';
import { useUser } from '@/contexts/UserContext';
import client from '@/api/client';

interface Transaction {
  tx_id: number;
  amount: number;
  type: string;
  description: string;
  match_id: number | null;
  created_at: string;
}

interface Bet {
  bet_id: number;
  match_id: number;
  bet_type: string;
  amount: number;
  odds: number;
  status: string;
  payout: number;
  created_at: string;
  settled_at: string | null;
  home_team: string | null;
  away_team: string | null;
  kickoff: string | null;
  potential_payout: number;
}

interface Team {
  team_id: number;
  name: string;
  short_name: string;
  league_code: string | null;
}

interface AdminUser {
  user_id: number;
  username: string;
  coins: number;
  is_admin: boolean;
  created_at: string;
}

const LEAGUES = [
  { code: 'PL', label: 'Premier League' },
  { code: 'PD', label: 'La Liga' },
  { code: 'BL1', label: 'Bundesliga' },
  { code: 'SA', label: 'Serie A' },
  { code: 'FL1', label: 'Ligue 1' },
  { code: 'KL1', label: 'K League 1' },
];

function BetStatusBadge({ status }: { status: string }) {
  const cfg = {
    pending: { label: 'Pending', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
    won: { label: 'Won', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
    lost: { label: 'Lost', cls: 'bg-red-500/10 text-red-400 border-red-500/20' },
    cancelled: { label: 'Cancelled', cls: 'bg-slate-500/10 text-slate-400 border-slate-500/20' },
  };
  const { label, cls } = cfg[status as keyof typeof cfg] ?? cfg.pending;
  return (
    <span className={clsx('text-[10px] font-medium px-1.5 py-0.5 rounded border', cls)}>
      {label}
    </span>
  );
}

export default function Profile() {
  const { user, checkin, logout, setFavorites, refreshBalance } = useUser();

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [bets, setBets] = useState<Bet[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(false);

  const [favLeague, setFavLeague] = useState(user?.favorite_league ?? '');
  const [favTeamId, setFavTeamId] = useState<number | null>(user?.favorite_team_id ?? null);

  const [checkinLoading, setCheckinLoading] = useState(false);
  const [checkinMsg, setCheckinMsg] = useState('');
  const [saveMsg, setSaveMsg] = useState('');

  // Admin state
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [adminLoading, setAdminLoading] = useState(false);
  const [giveCoinsTarget, setGiveCoinsTarget] = useState<number | ''>('');
  const [giveCoinsAmount, setGiveCoinsAmount] = useState('');
  const [adminMsg, setAdminMsg] = useState('');

  const today = new Date().toISOString().split('T')[0];
  const alreadyCheckedIn = user?.last_checkin === today;

  // Fetch teams when favLeague changes
  useEffect(() => {
    if (!favLeague) {
      setTeams([]);
      setFavTeamId(null);
      return;
    }
    client.get('/matches/teams/list', { params: { league: favLeague } })
      .then((data) => {
        const res = data as unknown as { teams: Team[] };
        setTeams(res.teams ?? []);
      })
      .catch(() => setTeams([]));
  }, [favLeague]);

  // Sync local state when user changes
  useEffect(() => {
    setFavLeague(user?.favorite_league ?? '');
    setFavTeamId(user?.favorite_team_id ?? null);
  }, [user?.favorite_league, user?.favorite_team_id]);

  // Fetch transactions and bets
  useEffect(() => {
    if (!user) return;
    setLoading(true);
    Promise.allSettled([
      client.get(`/user/${user.user_id}/transactions`),
      client.get(`/user/${user.user_id}/bets`),
    ]).then(([txRes, betsRes]) => {
      if (txRes.status === 'fulfilled') {
        const d = txRes.value as unknown as { transactions: Transaction[] };
        setTransactions(d.transactions ?? []);
      }
      if (betsRes.status === 'fulfilled') {
        const d = betsRes.value as unknown as { bets: Bet[] };
        setBets(d.bets ?? []);
      }
    }).finally(() => setLoading(false));
  }, [user?.user_id]);

  const handleCheckin = async () => {
    setCheckinLoading(true);
    setCheckinMsg('');
    try {
      const newBalance = await checkin();
      setCheckinMsg(`+100 coins! New balance: ${newBalance.toLocaleString()}`);
      setTimeout(() => setCheckinMsg(''), 4000);
    } catch (err: unknown) {
      setCheckinMsg(err instanceof Error ? err.message : 'Check-in failed');
      setTimeout(() => setCheckinMsg(''), 4000);
    } finally {
      setCheckinLoading(false);
    }
  };

  // Fetch admin users list
  useEffect(() => {
    if (!user?.is_admin) return;
    setAdminLoading(true);
    client.get('/user/admin/all-users', { params: { admin_user_id: user.user_id } })
      .then((data) => {
        const res = data as unknown as { users: AdminUser[] };
        setAdminUsers(res.users ?? []);
      })
      .catch(() => setAdminUsers([]))
      .finally(() => setAdminLoading(false));
  }, [user?.user_id, user?.is_admin]);

  const handleGiveCoins = async () => {
    if (!user || !giveCoinsTarget || !giveCoinsAmount) return;
    setAdminMsg('');
    try {
      await client.post('/user/admin/give-coins', {
        admin_user_id: user.user_id,
        target_user_id: Number(giveCoinsTarget),
        amount: Number(giveCoinsAmount),
      });
      setAdminMsg(`Gave ${Number(giveCoinsAmount).toLocaleString()} coins to user #${giveCoinsTarget}`);
      setGiveCoinsAmount('');
      // Refresh admin users
      const data = await client.get('/user/admin/all-users', { params: { admin_user_id: user.user_id } }) as unknown as { users: AdminUser[] };
      setAdminUsers(data.users ?? []);
      await refreshBalance();
      setTimeout(() => setAdminMsg(''), 4000);
    } catch (err: unknown) {
      setAdminMsg(err instanceof Error ? err.message : 'Failed');
      setTimeout(() => setAdminMsg(''), 4000);
    }
  };

  const handleResetUser = async (targetId: number) => {
    if (!user) return;
    setAdminMsg('');
    try {
      await client.post('/user/admin/reset-user', {
        admin_user_id: user.user_id,
        target_user_id: targetId,
      });
      setAdminMsg(`Reset user #${targetId} coins to 50,000`);
      const data = await client.get('/user/admin/all-users', { params: { admin_user_id: user.user_id } }) as unknown as { users: AdminUser[] };
      setAdminUsers(data.users ?? []);
      await refreshBalance();
      setTimeout(() => setAdminMsg(''), 4000);
    } catch (err: unknown) {
      setAdminMsg(err instanceof Error ? err.message : 'Failed');
      setTimeout(() => setAdminMsg(''), 4000);
    }
  };

  const handleSavePreferences = async () => {
    setSaveMsg('');
    try {
      await setFavorites(favLeague || null, favTeamId);
      setSaveMsg('Preferences saved!');
      setTimeout(() => setSaveMsg(''), 3000);
    } catch (err: unknown) {
      setSaveMsg(err instanceof Error ? err.message : 'Failed to save');
      setTimeout(() => setSaveMsg(''), 3000);
    }
  };

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-88px)] text-slate-500">
        <p className="text-sm">Please login to view your profile.</p>
      </div>
    );
  }

  const wonBets = bets.filter((b) => b.status === 'won').length;
  const lostBets = bets.filter((b) => b.status === 'lost').length;
  const pendingBets = bets.filter((b) => b.status === 'pending').length;
  const totalWinnings = bets.filter((b) => b.status === 'won').reduce((s, b) => s + b.payout, 0);

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header: Coin balance */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="col-span-2 bg-slate-800/50 border border-slate-700/50 rounded-lg p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
            <Coins className="w-6 h-6 text-amber-400" />
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-0.5">Coin Balance</p>
            <p className="text-3xl font-mono font-bold text-amber-400">{user.coins.toLocaleString()}</p>
            <p className="text-xs text-slate-500 mt-0.5">@{user.username}</p>
          </div>
          <div className="ml-auto flex flex-col items-end gap-2">
            {checkinMsg ? (
              <span className="text-xs font-mono text-emerald-400">{checkinMsg}</span>
            ) : !alreadyCheckedIn ? (
              <button
                onClick={handleCheckin}
                disabled={checkinLoading}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded border text-xs font-medium transition-colors',
                  'bg-amber-500/10 border-amber-500/30 text-amber-400',
                  'hover:bg-amber-500/20 hover:border-amber-500/50',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                <CheckCircle className="w-3.5 h-3.5" />
                {checkinLoading ? 'Checking in...' : 'Daily Check-In +100'}
              </button>
            ) : (
              <span className="flex items-center gap-1.5 text-xs text-emerald-400">
                <CheckCircle className="w-3.5 h-3.5" />
                Checked in today
              </span>
            )}
            <button
              onClick={logout}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              Logout
            </button>
          </div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
          <p className="text-xs text-slate-500 mb-1">Bet Record</p>
          <div className="flex items-baseline gap-1">
            <span className="font-mono text-lg font-bold text-emerald-400">{wonBets}W</span>
            <span className="font-mono text-sm text-slate-500">-</span>
            <span className="font-mono text-lg font-bold text-red-400">{lostBets}L</span>
          </div>
          <p className="text-xs text-slate-600 mt-1">{pendingBets} pending</p>
        </div>

        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
          <p className="text-xs text-slate-500 mb-1">Total Winnings</p>
          <p className="font-mono text-lg font-bold text-amber-400">{totalWinnings.toLocaleString()}</p>
          <p className="text-xs text-slate-600 mt-1">coins won from bets</p>
        </div>
      </div>

      {/* Preferences */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-5">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-4">Preferences</p>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="text-xs text-slate-500 block mb-1.5">Favorite League</label>
            <select
              value={favLeague}
              onChange={(e) => { setFavLeague(e.target.value); setFavTeamId(null); }}
              className={clsx(
                'appearance-none bg-slate-700 border border-slate-600 rounded',
                'text-xs text-slate-300 px-3 py-1.5 pr-8',
                'focus:outline-none focus:border-emerald-500/50'
              )}
            >
              <option value="">-- Select League --</option>
              {LEAGUES.map((l) => (
                <option key={l.code} value={l.code}>{l.label}</option>
              ))}
            </select>
          </div>

          {teams.length > 0 && (
            <div>
              <label className="text-xs text-slate-500 block mb-1.5">Favorite Team</label>
              <select
                value={favTeamId ?? ''}
                onChange={(e) => setFavTeamId(e.target.value ? parseInt(e.target.value, 10) : null)}
                className={clsx(
                  'appearance-none bg-slate-700 border border-slate-600 rounded',
                  'text-xs text-slate-300 px-3 py-1.5 pr-8',
                  'focus:outline-none focus:border-emerald-500/50'
                )}
              >
                <option value="">-- Select Team --</option>
                {teams.map((t) => (
                  <option key={t.team_id} value={t.team_id}>{t.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              onClick={handleSavePreferences}
              className={clsx(
                'px-3 py-1.5 rounded text-xs font-medium transition-colors',
                'bg-emerald-600 hover:bg-emerald-500 text-white'
              )}
            >
              Save Preferences
            </button>
            {saveMsg && (
              <span className={clsx('text-xs font-medium', saveMsg.includes('saved') ? 'text-emerald-400' : 'text-red-400')}>
                {saveMsg}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Admin Panel */}
      {user.is_admin && (
        <div className="bg-slate-800/50 border border-amber-500/30 rounded-lg p-5">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-4 h-4 text-amber-400" />
            <p className="text-xs font-semibold text-amber-400 uppercase tracking-wide">Admin Panel</p>
          </div>

          {/* Give coins */}
          <div className="flex flex-wrap items-end gap-3 mb-4">
            <div>
              <label className="text-xs text-slate-500 block mb-1">Target User</label>
              <select
                value={giveCoinsTarget}
                onChange={(e) => setGiveCoinsTarget(e.target.value ? parseInt(e.target.value, 10) : '')}
                className="appearance-none bg-slate-700 border border-slate-600 rounded text-xs text-slate-300 px-3 py-1.5 pr-8 focus:outline-none focus:border-emerald-500/50"
              >
                <option value="">-- Select User --</option>
                {adminUsers.map((u) => (
                  <option key={u.user_id} value={u.user_id}>
                    {u.username} (#{u.user_id}) - {u.coins.toLocaleString()} coins
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-500 block mb-1">Amount</label>
              <input
                type="number"
                value={giveCoinsAmount}
                onChange={(e) => setGiveCoinsAmount(e.target.value)}
                placeholder="10000"
                min={1}
                className="bg-slate-700 border border-slate-600 rounded text-xs text-slate-300 px-3 py-1.5 w-28 focus:outline-none focus:border-emerald-500/50 font-mono"
              />
            </div>
            <button
              onClick={handleGiveCoins}
              disabled={!giveCoinsTarget || !giveCoinsAmount}
              className={clsx(
                'px-3 py-1.5 rounded text-xs font-medium transition-colors',
                'bg-emerald-600 hover:bg-emerald-500 text-white',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              Give Coins
            </button>
            {adminMsg && (
              <span className={clsx('text-xs font-medium', adminMsg.includes('Failed') ? 'text-red-400' : 'text-emerald-400')}>
                {adminMsg}
              </span>
            )}
          </div>

          {/* User list */}
          <p className="text-xs text-slate-500 mb-2">All Users</p>
          {adminLoading ? (
            <p className="text-xs text-slate-600">Loading...</p>
          ) : (
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {adminUsers.map((u) => (
                <div key={u.user_id} className="flex items-center justify-between py-1.5 border-b border-slate-700/40 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-300 font-medium">{u.username}</span>
                    {u.is_admin && (
                      <span className="text-[10px] px-1 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">Admin</span>
                    )}
                    <span className="text-[10px] font-mono text-slate-500">#{u.user_id}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-amber-400">{u.coins.toLocaleString()}</span>
                    <button
                      onClick={() => handleResetUser(u.user_id)}
                      className="text-[10px] text-red-400 hover:text-red-300 transition-colors"
                    >
                      Reset
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Bet History */}
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-5">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Bet History</p>
          {loading ? (
            <p className="text-xs text-slate-600">Loading...</p>
          ) : bets.length === 0 ? (
            <p className="text-xs text-slate-600">No bets placed yet.</p>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
              {bets.map((bet) => (
                <div
                  key={bet.bet_id}
                  className="flex items-center justify-between py-2 border-b border-slate-700/40 last:border-0"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <BetStatusBadge status={bet.status} />
                      <span className="text-xs text-slate-300 font-medium">
                        {bet.home_team ?? '?'} vs {bet.away_team ?? '?'}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] text-slate-500">
                        {bet.bet_type.replace('_', ' ')} @ <span className="font-mono">{bet.odds.toFixed(2)}</span>
                      </span>
                      <span className="text-[10px] font-mono text-slate-500">
                        {new Date(bet.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <div className="text-right shrink-0 ml-3">
                    <p className="text-xs font-mono text-slate-400">-{bet.amount.toLocaleString()}</p>
                    {bet.status === 'won' && (
                      <p className="text-xs font-mono text-emerald-400">+{bet.payout.toLocaleString()}</p>
                    )}
                    {bet.status === 'pending' && (
                      <p className="text-[10px] font-mono text-amber-400/70">
                        pot. {bet.potential_payout.toLocaleString()}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Transaction History */}
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-5">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Transaction History</p>
          {loading ? (
            <p className="text-xs text-slate-600">Loading...</p>
          ) : transactions.length === 0 ? (
            <p className="text-xs text-slate-600">No transactions yet.</p>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
              {transactions.map((tx) => {
                const isPositive = tx.amount > 0;
                const Icon = isPositive ? TrendingUp : tx.amount < 0 ? TrendingDown : Minus;
                return (
                  <div
                    key={tx.tx_id}
                    className="flex items-center gap-3 py-2 border-b border-slate-700/40 last:border-0"
                  >
                    <div className={clsx(
                      'w-6 h-6 rounded flex items-center justify-center shrink-0',
                      isPositive ? 'bg-emerald-500/10' : 'bg-red-500/10'
                    )}>
                      <Icon className={clsx('w-3 h-3', isPositive ? 'text-emerald-400' : 'text-red-400')} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-slate-300 truncate">{tx.description}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] text-slate-600 flex items-center gap-1">
                          <Clock className="w-2.5 h-2.5" />
                          {new Date(tx.created_at).toLocaleDateString()}
                        </span>
                        <span className={clsx(
                          'text-[10px] px-1 py-0.5 rounded',
                          'bg-slate-700/50 text-slate-500'
                        )}>
                          {tx.type.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                    <span className={clsx(
                      'text-xs font-mono font-semibold shrink-0',
                      isPositive ? 'text-emerald-400' : 'text-red-400'
                    )}>
                      {isPositive ? '+' : ''}{tx.amount.toLocaleString()}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
