import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react';
import client from '@/api/client';

interface User {
  user_id: number;
  username: string;
  coins: number;
  favorite_league: string | null;
  favorite_team_id: number | null;
  last_checkin: string | null;
  is_admin: boolean;
}

interface UserContextValue {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  checkin: () => Promise<number>;
  refreshBalance: () => Promise<void>;
  logout: () => void;
  setFavorites: (league: string | null, teamId: number | null) => Promise<void>;
}

const UserContext = createContext<UserContextValue>({
  user: null,
  login: async () => {},
  register: async () => {},
  checkin: async () => 0,
  refreshBalance: async () => {},
  logout: () => {},
  setFavorites: async () => {},
});

const STORAGE_KEY = 'fa_user_id';

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  const fetchUser = useCallback(async (userId: number) => {
    try {
      const data = await client.get(`/user/${userId}`) as unknown as User;
      setUser(data);
    } catch {
      localStorage.removeItem(STORAGE_KEY);
      setUser(null);
    }
  }, []);

  // Restore session from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const userId = parseInt(stored, 10);
      if (!isNaN(userId)) {
        fetchUser(userId);
      }
    }
  }, [fetchUser]);

  const login = useCallback(async (username: string, password: string) => {
    const data = await client.post('/user/login', { username, password }) as unknown as User;
    localStorage.setItem(STORAGE_KEY, String(data.user_id));
    setUser(data);
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    try {
      const data = await client.post('/user/register', { username, password }) as unknown as User;
      localStorage.setItem(STORAGE_KEY, String(data.user_id));
      setUser(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes('already taken')) {
        throw new Error('Username already taken. Please choose a different name.');
      }
      throw err;
    }
  }, []);

  const checkin = useCallback(async (): Promise<number> => {
    if (!user) throw new Error('Not logged in');
    const data = await client.post('/user/checkin', { user_id: user.user_id }) as unknown as { coins: number; bonus: number };
    setUser((prev) => prev ? { ...prev, coins: data.coins, last_checkin: new Date().toISOString().split('T')[0] } : prev);
    return data.coins;
  }, [user]);

  const refreshBalance = useCallback(async () => {
    if (!user) return;
    await fetchUser(user.user_id);
  }, [user, fetchUser]);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  }, []);

  const setFavorites = useCallback(async (league: string | null, teamId: number | null) => {
    if (!user) throw new Error('Not logged in');
    await client.post('/user/preferences', {
      user_id: user.user_id,
      favorite_league: league,
      favorite_team_id: teamId,
    });
    setUser((prev) => prev ? { ...prev, favorite_league: league, favorite_team_id: teamId } : prev);
  }, [user]);

  const value = useMemo(
    () => ({ user, login, register, checkin, refreshBalance, logout, setFavorites }),
    [user, login, register, checkin, refreshBalance, logout, setFavorites]
  );

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser() {
  return useContext(UserContext);
}
