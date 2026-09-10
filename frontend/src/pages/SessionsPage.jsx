import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Laptop,
  Smartphone,
  Globe,
  Clock,
  Shield,
  LogOut,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Trash2,
} from "lucide-react";
import { listSessions, revokeSession, logoutAll } from "../services/api";
import { useAuth } from "../context/AuthContext.jsx";

export default function SessionsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [revokingId, setRevokingId] = useState(null);
  const [revokingAll, setRevokingAll] = useState(false);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listSessions();
      setSessions(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not retrieve active sessions.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleRevoke = async (sessionId) => {
    setRevokingId(sessionId);
    setError(null);
    try {
      await revokeSession(sessionId);
      setSuccessMsg("Device session revoked successfully.");
      fetchSessions();
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to revoke session.");
    } finally {
      setRevokingId(null);
    }
  };

  const handleRevokeAll = async () => {
    if (!window.confirm("Are you sure you want to log out from all devices? This will invalidate all active sessions including this one.")) {
      return;
    }
    setRevokingAll(true);
    setError(null);
    try {
      await logoutAll();
      navigate("/login", { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to log out from all devices.");
      setRevokingAll(false);
    }
  };

  const getDeviceIcon = (ua = "") => {
    const lower = ua.toLowerCase();
    if (lower.includes("mobile") || lower.includes("iphone") || lower.includes("android")) {
      return <Smartphone className="h-5 w-5 text-indigo-500" />;
    }
    return <Laptop className="h-5 w-5 text-blue-500" />;
  };

  return (
    <div className="space-y-6 p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2.5">
            <Shield className="h-7 w-7 text-blue-600" />
            Sessions & Device Management
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Monitor and manage all active browser sessions and trusted devices associated with your account.
          </p>
        </div>

        <button
          type="button"
          onClick={handleRevokeAll}
          disabled={revokingAll}
          className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs font-bold text-rose-700 hover:bg-rose-100 transition-colors shadow-xs disabled:opacity-50"
        >
          {revokingAll ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <LogOut className="h-4 w-4" />
          )}
          <span>Log Out From All Devices</span>
        </button>
      </div>

      {successMsg && (
        <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-xs font-medium text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-rose-300 bg-rose-50 p-4 text-xs font-medium text-rose-800 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Session Security Overview Card */}
      <div className="rounded-2xl border border-blue-100 bg-gradient-to-r from-blue-50/70 to-indigo-50/70 p-5 flex items-start gap-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white shadow-sm shrink-0">
          <Globe className="h-5 w-5" />
        </div>
        <div className="text-xs text-slate-700 space-y-1">
          <h3 className="font-bold text-slate-900 text-sm">Server-Side Session Invalidation</h3>
          <p className="leading-relaxed">
            Every login creates an isolated server-side session token stored with strict idle and maximum lifetime limits.
            Revoking a session immediately purges authentication on that device.
          </p>
        </div>
      </div>

      {/* Sessions List */}
      <div className="space-y-3">
        <h2 className="text-sm font-bold text-slate-800">
          Active Sessions ({sessions.length})
        </h2>

        {loading ? (
          <div className="flex h-32 items-center justify-center rounded-2xl border border-slate-200 bg-white">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center text-xs text-slate-400">
            No active sessions found.
          </div>
        ) : (
          <div className="grid gap-3">
            {sessions.map((s) => (
              <div
                key={s.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between rounded-2xl border border-slate-200 bg-white p-4 shadow-xs hover:border-slate-300 transition-all gap-4"
              >
                <div className="flex items-start gap-3.5">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 shrink-0">
                    {getDeviceIcon(s.user_agent)}
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-slate-900">
                        {s.user_agent ? s.user_agent.split("(")[0].trim() || "Web Browser" : "Web Client"}
                      </span>
                      {s.is_current && (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800 border border-emerald-200">
                          Current Device
                        </span>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                      <span>IP: <strong className="text-slate-700 font-mono">{s.ip_address || "127.0.0.1"}</strong></span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        Last active: {new Date(s.last_activity_at).toLocaleTimeString()}
                      </span>
                      <span>Expires: {new Date(s.expires_at).toLocaleTimeString()}</span>
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono truncate max-w-lg">
                      {s.user_agent}
                    </div>
                  </div>
                </div>

                <div className="flex items-center sm:self-center self-end">
                  <button
                    type="button"
                    disabled={revokingId === s.session_id}
                    onClick={() => handleRevoke(s.session_id)}
                    className="flex items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-semibold text-rose-600 hover:bg-rose-50 hover:border-rose-200 transition-colors disabled:opacity-50"
                  >
                    {revokingId === s.session_id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                    <span>{s.is_current ? "Sign Out" : "Revoke"}</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
