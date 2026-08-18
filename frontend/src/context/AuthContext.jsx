import { createContext, useContext, useState, useEffect } from "react";
import {
  login as apiLogin,
  registerFirstAdmin as apiRegister,
  getMe,
  getStoredToken,
  setStoredToken,
  clearStoredToken,
} from "../services/api";

const AuthContext = createContext(null);

// Mirrors app/core/rbac.py's ROLE_HIERARCHY — kept in sync manually since
// this is just a UI convenience (disabling buttons, showing hints) and the
// backend is the actual source of truth/enforcement either way. A stale
// client-side copy can at worst show a wrong hint; it can never grant
// access the server wouldn't also grant.
const ROLE_HIERARCHY = { tester: 0, approver: 1, admin: 2 };

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // { id, username, role, is_active }
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setLoading(false);
      return;
    }
    // A stored token might be expired/invalid (server restarted with a new
    // SECRET_KEY, token naturally expired, etc.) — verify it against /me
    // rather than trusting localStorage blindly.
    getMe()
      .then((res) => setUser(res.data))
      .catch(() => clearStoredToken())
      .finally(() => setLoading(false));
  }, []);

  const login = async (username, password) => {
    const res = await apiLogin({ username, password });
    setStoredToken(res.data.access_token);
    const me = await getMe();
    setUser(me.data);
    return me.data;
  };

  // Only works while the backend's users table is completely empty (see
  // api/auth.py's register() docstring) — every account after that must be
  // created by an admin via the Users admin panel instead.
  const registerFirstAdmin = async (username, password) => {
    await apiRegister({ username, password });
    return login(username, password);
  };

  const logout = () => {
    clearStoredToken();
    setUser(null);
  };

  const hasAtLeast = (minimumRole) => {
    if (!user) return false;
    return ROLE_HIERARCHY[user.role] >= ROLE_HIERARCHY[minimumRole];
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, registerFirstAdmin, logout, hasAtLeast }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
