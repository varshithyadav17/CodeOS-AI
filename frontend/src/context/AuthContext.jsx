import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { cancelGoogleSignInSetup } from "../lib/googleIdentity";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authPending, setAuthPending] = useState(false);
  const revision = useRef(0);
  const initialCheck = useRef(null);
  const mutating = useRef(false);

  const init = useCallback(() => {
    if (initialCheck.current) return initialCheck.current.promise;
    const startedAt = revision.current;
    const controller = new AbortController();
    const check = { controller, promise: null };
    check.promise = api.get("/auth/me", { signal: controller.signal }).then(
      ({ data }) => { if (startedAt === revision.current) setUser(data.user); },
      () => { if (startedAt === revision.current) setUser(null); },
    ).finally(() => {
      if (initialCheck.current === check) initialCheck.current = null;
      if (startedAt === revision.current) setLoading(false);
    });
    initialCheck.current = check;
    return check.promise;
  }, []);

  // Restore the cookie session once above the per-user workspace, which
  // remounts when someone signs in or out.
  useEffect(() => { init(); }, [init]);

  const updateSession = useCallback(async (path, body) => {
    if (mutating.current) throw new Error("An authentication request is already in progress.");
    mutating.current = true;
    setAuthPending(true);
    try {
      const { data } = await api.post(path, body);
      // An earlier anonymous session check must not replace a new login.
      revision.current += 1;
      initialCheck.current?.controller.abort();
      cancelGoogleSignInSetup();
      const next = data.user ?? null;
      setUser(next);
      setLoading(false);
      return next;
    } finally {
      mutating.current = false;
      setAuthPending(false);
    }
  }, []);

  const login = useCallback((email, password) => updateSession("/auth/login", { email, password }), [updateSession]);
  const signup = useCallback((email, password, name) => updateSession("/auth/signup", { email, password, name }), [updateSession]);
  const googleExchange = useCallback((credential, linkPassword) =>
    updateSession("/auth/google", { credential, link_password: linkPassword || undefined }), [updateSession]);

  const refreshUser = useCallback(async () => {
    const startedAt = revision.current;
    const r = await api.get("/auth/me");
    if (startedAt === revision.current) setUser(r.data.user);
    return r.data.user;
  }, []);

  const logout = useCallback(async () => {
    // Keep the session visible until the server clears the HttpOnly cookie.
    await updateSession("/auth/logout");
    window.google?.accounts?.id?.disableAutoSelect();
  }, [updateSession]);

  const value = { user, loading, authPending, login, signup, googleExchange, logout, refreshUser };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth() must be used within an <AuthProvider>");
  }
  return ctx;
}
