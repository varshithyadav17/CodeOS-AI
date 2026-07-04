import { create } from "zustand";
import { api } from "../lib/api";

// Auth state lives in memory only. Persistence is done by the backend's
// HttpOnly cookie (`codeos_token`), which is XSS-resistant. `init()`
// asks the backend "who am I?" — if the cookie is valid we get the user,
// otherwise we show the login screen.
export const useAuth = create((set) => ({
  user: null,
  loading: true,

  init: async () => {
    try {
      const r = await api.get("/auth/me");
      set({ user: r.data.user, loading: false });
    } catch {
      set({ user: null, loading: false });
    }
  },

  login: async (email, password) => {
    const r = await api.post("/auth/login", { email, password });
    set({ user: r.data.user });
    return r.data.user;
  },

  signup: async (email, password, name) => {
    const r = await api.post("/auth/signup", { email, password, name });
    set({ user: r.data.user });
    return r.data.user;
  },

  googleExchange: async (sessionId) => {
    const r = await api.post("/auth/google", { session_id: sessionId });
    set({ user: r.data.user });
    return r.data.user;
  },

  logout: async () => {
    try {
      await api.post("/auth/logout");
    } catch (err) {
      // Logging out should never throw at the UI; cookies will eventually
      // expire even if the request failed.
      console.warn("Logout request failed:", err);
    }
    set({ user: null });
  },
}));
