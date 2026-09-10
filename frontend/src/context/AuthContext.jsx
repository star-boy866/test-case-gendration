import { createContext, useContext, useState, useEffect, useCallback } from "react";
import {
  login as apiLogin,
  verifyMfa as apiVerifyMfa,
  changePassword as apiChangePassword,
  logout as apiLogout,
  logoutAll as apiLogoutAll,
  getMe,
  getStoredToken,
  setStoredToken,
  clearStoredToken,
  clearCognosWorkspaceState,
} from "../services/api";

const AuthContext = createContext(null);

// Strict 4-Tier Hierarchy aligned with backend core/rbac.py
export const ROLE_HIERARCHY = {
  pending: 0,
  tester: 1,
  approver: 1, // backward compatibility
  admin: 2,
  standard_admin: 3,
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // { id, username, role, status, must_change_password, mfa_enabled }
  const [loading, setLoading] = useState(true);
  const [authStage, setAuthStage] = useState(null); // null | "MFA_REQUIRED" | "MUST_CHANGE_PASSWORD" | "PENDING_APPROVAL"
  const [tempToken, setTempToken] = useState(() => {
    try {
      return sessionStorage.getItem("temp_auth_token") || null;
    } catch {
      return null;
    }
  });
  const [userHint, setUserHint] = useState(() => {
    try {
      return sessionStorage.getItem("temp_auth_user") || null;
    } catch {
      return null;
    }
  });

  const clearTempAuth = () => {
    try {
      sessionStorage.removeItem("temp_auth_token");
      sessionStorage.removeItem("temp_auth_user");
    } catch {}
    setTempToken(null);
    setUserHint(null);
  };

  const refreshUser = useCallback(async () => {
    try {
      const res = await getMe();
      setUser(res.data);
      return res.data;
    } catch {
      clearStoredToken();
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setLoading(false);
      return;
    }
    refreshUser().finally(() => setLoading(false));
  }, [refreshUser]);

  const login = async (username, password) => {
    const res = await apiLogin({ username, password });
    const data = res.data;
    const resolvedUser = data.user?.username || data.user_hint || username;

    if (data.status === "SUCCESS") {
      clearCognosWorkspaceState();
      setStoredToken(data.access_token);
      clearTempAuth();
      setAuthStage(null);
      const profile = await refreshUser();
      const resolvedProfile = profile || data.user;
      const role = (resolvedProfile?.role || data.role || "").toLowerCase().replace("-", "_");
      return { status: "SUCCESS", user: resolvedProfile, role };
    }

    if (data.status === "MFA_REQUIRED") {
      setAuthStage("MFA_REQUIRED");
      const token = data.temp_token || data.mfa_ticket;
      setTempToken(token);
      setUserHint(resolvedUser);
      try {
        sessionStorage.setItem("temp_auth_token", token || "");
        sessionStorage.setItem("temp_auth_user", resolvedUser || "");
      } catch {}
      return { status: "MFA_REQUIRED", tempToken: token, userHint: resolvedUser };
    }

    if (data.status === "MUST_CHANGE_PASSWORD") {
      setAuthStage("MUST_CHANGE_PASSWORD");
      setTempToken(data.temp_token);
      setUserHint(resolvedUser);
      try {
        sessionStorage.setItem("temp_auth_token", data.temp_token || "");
        sessionStorage.setItem("temp_auth_user", resolvedUser || "");
      } catch {}
      return { status: "MUST_CHANGE_PASSWORD", tempToken: data.temp_token, userHint: resolvedUser };
    }

    if (data.status === "PENDING_APPROVAL") {
      setAuthStage("PENDING_APPROVAL");
      setTempToken(data.temp_token);
      setUserHint(resolvedUser);
      try {
        sessionStorage.setItem("temp_auth_token", data.temp_token || "");
        sessionStorage.setItem("temp_auth_user", resolvedUser || "");
      } catch {}
      return { status: "PENDING_APPROVAL", tempToken: data.temp_token, userHint: resolvedUser };
    }

    return data;
  };

  const verifyMfaCode = async (code) => {
    const token = tempToken || sessionStorage.getItem("temp_auth_token");
    if (!token) throw new Error("No active MFA session.");
    const res = await apiVerifyMfa({ temp_token: token, code });
    const data = res.data;
    if (data.access_token) {
      clearCognosWorkspaceState();
      setStoredToken(data.access_token);
      clearTempAuth();
      setAuthStage(null);
      const profile = await refreshUser();
      const resolvedProfile = profile || data.user;
      const role = (resolvedProfile?.role || data.role || "").toLowerCase().replace("-", "_");
      return { status: "SUCCESS", user: resolvedProfile, role };
    }
    return data;
  };

  const completePasswordChange = async (currentPassword, newPassword, targetUsername = null) => {
    const token = tempToken || sessionStorage.getItem("temp_auth_token") || null;
    if (!token) throw new Error("No password change session active.");
    const username = targetUsername || userHint || sessionStorage.getItem("temp_auth_user") || null;

    const res = await apiChangePassword(
      {
        current_password: currentPassword,
        new_password: newPassword,
        username,
        temp_token: token,
      },
      token
    );
    const data = res.data;
    if (data.access_token) {
      clearCognosWorkspaceState();
      setStoredToken(data.access_token);
      clearTempAuth();
      setAuthStage(null);
      const profile = await refreshUser();
      const resolvedProfile = profile || data.user;
      const role = (resolvedProfile?.role || data.role || "").toLowerCase().replace("-", "_");
      return { status: "SUCCESS", user: resolvedProfile, role };
    }
    return data;
  };

  const logout = async () => {
    try {
      await apiLogout();
    } catch {
      // ignore network/session errors on logout
    } finally {
      clearCognosWorkspaceState();
      clearStoredToken();
      clearTempAuth();
      setUser(null);
      setAuthStage(null);
    }
  };

  const logoutAll = async () => {
    try {
      await apiLogoutAll();
    } catch {
      // ignore errors
    } finally {
      clearCognosWorkspaceState();
      clearStoredToken();
      clearTempAuth();
      setUser(null);
      setAuthStage(null);
    }
  };

  const hasAtLeast = (minimumRole) => {
    if (!user || user.status !== "ACTIVE") return false;
    const roleKey = (user.role || "").toLowerCase().replace("-", "_");
    const minKey = (minimumRole || "").toLowerCase().replace("-", "_");
    const userLevel = ROLE_HIERARCHY[roleKey] ?? -1;
    const minLevel = ROLE_HIERARCHY[minKey] ?? 99;
    return userLevel >= minLevel;
  };

  const normalizedRole = (user?.role || "").toLowerCase().replace("-", "_");
  const isStandardAdmin = normalizedRole === "standard_admin" && user?.status === "ACTIVE";
  const isAdmin = (normalizedRole === "standard_admin" || normalizedRole === "admin") && user?.status === "ACTIVE";
  const isTester = normalizedRole === "tester" && user?.status === "ACTIVE";

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        authStage,
        tempToken,
        userHint,
        login,
        verifyMfaCode,
        completePasswordChange,
        logout,
        logoutAll,
        hasAtLeast,
        isStandardAdmin,
        isAdmin,
        isTester,
        refreshUser,
      }}
    >
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
