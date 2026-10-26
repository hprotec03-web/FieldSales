import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setUnauthorizedHandler } from "../lib/api";
import type { Me } from "../lib/types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  can: (permission: string) => boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try { setMe(await api.get<Me>("/auth/me")); } catch { setMe(null); }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setMe(null)); // any 401 sends the user back to /login
    refresh().finally(() => setLoading(false));
    return () => setUnauthorizedHandler(null);
  }, [refresh]);

  const value = useMemo<AuthState>(() => ({
    me, loading,
    can: (p) => !!me?.permissions.includes(p),
    login: async (username, password) => {
      const res = await api.post<{ user: Me }>("/auth/login", { username, password });
      setMe(res.user);
    },
    logout: async () => { try { await api.post("/auth/logout"); } finally { setMe(null); } },
    refresh,
  }), [me, loading, refresh]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside <AuthProvider>");
  return v;
}
