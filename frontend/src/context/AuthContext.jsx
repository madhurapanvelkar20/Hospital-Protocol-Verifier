import { createContext, useContext, useState, useCallback, useEffect } from "react";
import { login as apiLogin, signup as apiSignup, fetchMe } from "../api.js";

const AuthContext = createContext(null);

const STORAGE_KEY = "hpv_auth";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  // Restore session from localStorage on first load, and confirm the
  // token is still valid server-side (it could have expired).
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      setReady(true);
      return;
    }
    try {
      const parsed = JSON.parse(stored);
      fetchMe(parsed.token)
        .then((me) => {
          setToken(parsed.token);
          setUser(me);
        })
        .catch(() => {
          localStorage.removeItem(STORAGE_KEY);
        })
        .finally(() => setReady(true));
    } catch {
      localStorage.removeItem(STORAGE_KEY);
      setReady(true);
    }
  }, []);

  const persist = (newToken, newUser) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: newToken }));
  };

  const login = useCallback(async (email, password) => {
    const res = await apiLogin({ email, password });
    persist(res.access_token, { email: res.email, display_name: res.display_name });
    return res;
  }, []);

  const signup = useCallback(async (email, password, displayName) => {
    const res = await apiSignup({ email, password, displayName });
    persist(res.access_token, { email: res.email, display_name: res.display_name });
    return res;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  const value = { token, user, isAuthenticated: !!token, ready, login, signup, logout };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
