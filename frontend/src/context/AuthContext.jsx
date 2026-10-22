import { createContext, useCallback, useContext, useState } from "react";
import { api } from "../lib/api";

const AuthContext = createContext(null);

/**
 * Auth state lives in memory only. Persistence is done by the backend's
 * HttpOnly cookie (`codeos_token`), which is XSS-resistant. `init()` asks
 * the backend "who am I?" — if the cookie is valid we get the user,
 * otherwise we show the login screen.
 *
 * This replaces the previous Zustand `useAuth` store 1:1 — same fields,
 * same async behavior (callers still catch/throw the same way) — just
 * exposed via React context instead of an external store.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const init = useCallback(async () => {
    try {
      const r = await api.get("/auth/me");
      setUser(r.data.user);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email, password) => {
    const r = await api.post("/auth/login", { email, password });
    setUser(r.data.user);
    return r.data.user;
  }, []);

  const signup = useCallback(async (email, password, name) => {
    const r = await api.post("/auth/signup", { email, password, name });
    setUser(r.data.user);
    return r.data.user;
  }, []);

  const googleExchange = useCallback(async (credential, linkPassword) => {
    const r = await api.post("/auth/google", { credential, link_password: linkPassword || undefined });
    setUser(r.data.user);
    return r.data.user;
  }, []);

  const refreshUser = useCallback(async () => {
    const r = await api.get("/auth/me");
    setUser(r.data.user);
    return r.data.user;
  }, []);

  const logout = useCallback(async () => {
    // Keep the session visible until the server clears the HttpOnly cookie.
    await api.post("/auth/logout");
    window.google?.accounts?.id?.disableAutoSelect();
    setUser(null);
  }, []);

  const value = { user, loading, init, login, signup, googleExchange, logout, refreshUser };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth() must be used within an <AuthProvider>");
  }
  return ctx;
}
