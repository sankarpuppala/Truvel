/** App-wide state: the signed-in user, config, theme, toasts and position.
 *
 * One provider rather than four, because every screen needs most of it and a
 * single context keeps the prop drilling out of the screens.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { ApiError, api } from './api';
import { getCoarsePosition, type Position } from './geo';
import type { AppConfig, Me } from './types';

export type Toast = {
  id: number;
  text: string;
  kind: 'plain' | 'kadam' | 'bad';
};

type State = {
  me: Me | null;
  loadingMe: boolean;
  config: AppConfig | null;
  devTools: boolean;
  theme: 'system' | 'light' | 'dark';
  position: Position | null;
  setPosition: (pos: Position | null) => void;
  activeCityName: string | null;
  setActiveCityName: (name: string | null) => void;
  /** A simulated position from the dev tools, used instead of the real one. */
  simulated: Position | null;
  toasts: Toast[];
  setMe: (me: Me | null) => void;
  refreshMe: () => Promise<void>;
  setTheme: (theme: 'system' | 'light' | 'dark') => void;
  requestPosition: (force?: boolean) => Promise<Position | null>;
  setSimulated: (position: Position | null) => void;
  toast: (text: string, kind?: Toast['kind']) => void;
  logout: () => Promise<void>;
};

const AppContext = createContext<State | null>(null);

const THEME_KEY = 'truvel.theme';

export function AppProvider({ children }: { children: ReactNode }) {
  const [me, setMeState] = useState<Me | null>(() => {
    try {
      const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('truvel_user') : null;
      return stored ? (JSON.parse(stored) as Me) : null;
    } catch {
      return null;
    }
  });

  const setMe = useCallback((user: Me | null) => {
    setMeState(user);
    if (typeof localStorage !== 'undefined') {
      if (user) {
        localStorage.setItem('truvel_user', JSON.stringify(user));
      } else {
        localStorage.removeItem('truvel_user');
        localStorage.removeItem('truvel_token');
      }
    }
  }, []);

  const [loadingMe, setLoadingMe] = useState(true);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [devTools, setDevTools] = useState(false);
  const [position, setPositionState] = useState<Position | null>(() => {
    try {
      const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('truvel_user_position') : null;
      return stored ? (JSON.parse(stored) as Position) : null;
    } catch {
      return null;
    }
  });

  const [activeCityName, setActiveCityNameState] = useState<string | null>(() => {
    try {
      return typeof localStorage !== 'undefined' ? localStorage.getItem('truvel_user_city_name') : null;
    } catch {
      return null;
    }
  });

  const setPosition = useCallback((newPos: Position | null) => {
    setPositionState(newPos);
    if (typeof localStorage !== 'undefined') {
      if (newPos) {
        localStorage.setItem('truvel_user_position', JSON.stringify(newPos));
      } else {
        localStorage.removeItem('truvel_user_position');
      }
    }
  }, []);

  const setActiveCityName = useCallback((name: string | null) => {
    setActiveCityNameState(name);
    if (typeof localStorage !== 'undefined') {
      if (name) {
        localStorage.setItem('truvel_user_city_name', name);
      } else {
        localStorage.removeItem('truvel_user_city_name');
      }
    }
  }, []);

  const [simulated, setSimulated] = useState<Position | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [theme, setThemeState] = useState<'system' | 'light' | 'dark'>(() => {
    const stored = localStorage.getItem(THEME_KEY);
    return stored === 'light' || stored === 'dark' ? stored : 'system';
  });
  const toastId = useRef(0);

  // Theme: `data-theme` on <html>, which tokens.css keys off. Absent means
  // "follow the system", which is the default (SPEC §12.2).
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const refreshMe = useCallback(async () => {
    try {
      const { user } = await api.me();
      setMe(user);
      if (user.theme === 'light' || user.theme === 'dark' || user.theme === 'system') {
        setThemeState(user.theme);
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setMe(null);
      } else {
        console.warn('could not load the signed-in user', error);
      }
    } finally {
      setLoadingMe(false);
    }
  }, [setMe]);

  useEffect(() => {
    void refreshMe();
    void api
      .config()
      .then(setConfig)
      .catch(() => setConfig(null));
    // The dev tools appear only when the frontend was *built* with the flag and
    // the server *also* allows fake location (SPEC §8.7, AC-25).
    const builtWithDevTools = import.meta.env.VITE_DEV_TOOLS === '1';
    if (builtWithDevTools) {
      void api
        .health()
        .then((health) => setDevTools(Boolean(health.dev_fake_location)))
        .catch(() => setDevTools(false));
    }
  }, [refreshMe]);

  const toast = useCallback((text: string, kind: Toast['kind'] = 'plain') => {
    const id = ++toastId.current;
    setToasts((current) => [...current, { id, text, kind }]);
    // 2.5 s, as SPEC §12.7 specifies for the kadam toast.
    window.setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id));
    }, 2500);
  }, []);

  const requestPosition = useCallback(async (force = false) => {
    if (simulated) return simulated;
    if (!force && position) return position;
    try {
      const next = await getCoarsePosition();
      setPosition(next);
      return next;
    } catch {
      // Location denied or unavailable fallback
      return position;
    }
  }, [simulated, position, setPosition]);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setMe(null);
      setSimulated(null);
    }
  }, []);

  const value = useMemo<State>(
    () => ({
      me,
      loadingMe,
      config,
      devTools,
      theme,
      position: simulated ?? position,
      setPosition,
      activeCityName,
      setActiveCityName,
      simulated,
      toasts,
      setMe,
      refreshMe,
      setTheme: setThemeState,
      requestPosition,
      setSimulated,
      toast,
      logout,
    }),
    [
      me,
      loadingMe,
      config,
      devTools,
      theme,
      position,
      setPosition,
      activeCityName,
      setActiveCityName,
      simulated,
      toasts,
      refreshMe,
      requestPosition,
      toast,
      logout,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): State {
  const value = useContext(AppContext);
  if (!value) throw new Error('useApp must be used inside <AppProvider>');
  return value;
}
