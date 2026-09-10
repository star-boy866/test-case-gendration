import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ShieldAlert,
  Lock,
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Loader2,
  KeyRound,
  ShieldCheck,
} from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";
import { changePassword } from "../services/api";

export default function FirstLoginPasswordChangePage() {
  const { tempToken, userHint, logout, refreshUser } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState(() => {
    try {
      return (
        userHint ||
        sessionStorage.getItem("temp_auth_user") ||
        localStorage.getItem("healthcare_nl_testgen_last_user") ||
        "obuli"
      );
    } catch {
      return "obuli";
    }
  });
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Policy validation checks
  const hasMinLength = newPassword.length >= 12;
  const hasUpper = /[A-Z]/.test(newPassword);
  const hasLower = /[a-z]/.test(newPassword);
  const hasDigit = /[0-9]/.test(newPassword);
  const hasSpecial = /[^A-Za-z0-9]/.test(newPassword);
  const passwordsMatch = newPassword === confirmPassword && newPassword.length > 0;
  const isPolicySatisfied =
    hasMinLength && hasUpper && hasLower && hasDigit && hasSpecial && passwordsMatch;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isPolicySatisfied) {
      setError("Please ensure your new password satisfies all security criteria.");
      return;
    }

    setSubmitting(true);
    setError(null);

    const resolvedUser = (username || "").trim() || "obuli";

    const token =
      tempToken ||
      (() => {
        try {
          return sessionStorage.getItem("temp_auth_token");
        } catch {
          return null;
        }
      })();

    try {
      const res = await changePassword(
        {
          username: resolvedUser,
          current_password: currentPassword,
          new_password: newPassword,
          temp_token: token,
        },
        token
      );

      if (res.data.access_token) {
        localStorage.setItem("healthcare_nl_testgen_token", res.data.access_token);
        try {
          sessionStorage.removeItem("temp_auth_token");
          sessionStorage.removeItem("temp_auth_user");
        } catch {}
        await refreshUser();
        navigate("/cognos", { replace: true });
      } else {
        // Password changed, send back to login
        try {
          sessionStorage.removeItem("temp_auth_token");
          sessionStorage.removeItem("temp_auth_user");
        } catch {}
        navigate("/login?changed=true", { replace: true });
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        Array.isArray(detail)
          ? detail.map((d) => d.msg).join("; ")
          : detail || "Failed to change password. Please verify current credentials."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 px-4 py-12 text-slate-100">
      <div className="w-full max-w-lg rounded-2xl border border-slate-700/60 bg-slate-800/80 p-8 shadow-2xl backdrop-blur-md">
        
        {/* Header */}
        <div className="mb-6 flex items-center gap-3 border-b border-slate-700/80 pb-5">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/30">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">Password Change Required</h1>
            <p className="text-xs text-slate-400">
              Security Policy: First-login accounts must establish a permanent secret password.
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-300">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Account Username */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Account Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. obuli"
              className="w-full rounded-xl border border-slate-600 bg-slate-900/80 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              required
            />
          </div>

          {/* Current Temporary Password */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Current Temporary Password
            </label>
            <div className="relative">
              <input
                type={showCurrent ? "text" : "password"}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current / temporary password"
                className="w-full rounded-xl border border-slate-600 bg-slate-900/80 px-3.5 py-2.5 pr-10 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                required
              />
              <button
                type="button"
                onClick={() => setShowCurrent(!showCurrent)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-200"
              >
                {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* New Password */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
              New Password
            </label>
            <div className="relative">
              <input
                type={showNew ? "text" : "password"}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Minimum 12 characters"
                className="w-full rounded-xl border border-slate-600 bg-slate-900/80 px-3.5 py-2.5 pr-10 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                required
              />
              <button
                type="button"
                onClick={() => setShowNew(!showNew)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-200"
              >
                {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* Confirm Password */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Confirm New Password
            </label>
            <input
              type={showNew ? "text" : "password"}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter new password"
              className="w-full rounded-xl border border-slate-600 bg-slate-900/80 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              required
            />
          </div>

          {/* Real-Time Password Policy Checklist */}
          <div className="rounded-xl border border-slate-700/60 bg-slate-900/60 p-3.5 text-xs">
            <span className="mb-2 block font-semibold text-slate-300">Enterprise Password Complexity Rules:</span>
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div className={`flex items-center gap-1.5 ${hasMinLength ? "text-emerald-400" : "text-slate-400"}`}>
                {hasMinLength ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                <span>At least 12 characters</span>
              </div>
              <div className={`flex items-center gap-1.5 ${hasUpper ? "text-emerald-400" : "text-slate-400"}`}>
                {hasUpper ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                <span>Uppercase letter (A-Z)</span>
              </div>
              <div className={`flex items-center gap-1.5 ${hasLower ? "text-emerald-400" : "text-slate-400"}`}>
                {hasLower ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                <span>Lowercase letter (a-z)</span>
              </div>
              <div className={`flex items-center gap-1.5 ${hasDigit ? "text-emerald-400" : "text-slate-400"}`}>
                {hasDigit ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                <span>Numeric digit (0-9)</span>
              </div>
              <div className={`flex items-center gap-1.5 ${hasSpecial ? "text-emerald-400" : "text-slate-400"}`}>
                {hasSpecial ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                <span>Special character (!@#$)</span>
              </div>
              <div className={`flex items-center gap-1.5 ${passwordsMatch ? "text-emerald-400" : "text-slate-400"}`}>
                {passwordsMatch ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                <span>Passwords match</span>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={submitting || !isPolicySatisfied}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-500/20 transition-all hover:from-blue-500 hover:to-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Updating Password…</span>
                </>
              ) : (
                <>
                  <KeyRound className="h-4 w-4" />
                  <span>Set Permanent Password & Continue</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </form>

        <div className="mt-6 flex items-center justify-between border-t border-slate-700/60 pt-4 text-xs text-slate-400">
          <div className="flex items-center gap-1">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <span>Encrypted using Argon2id</span>
          </div>
          <button
            type="button"
            onClick={() => logout().then(() => navigate("/login"))}
            className="text-slate-400 hover:text-white underline"
          >
            Cancel & Return to Login
          </button>
        </div>

      </div>
    </div>
  );
}
