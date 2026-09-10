import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  UserPlus,
  Lock,
  User,
  Eye,
  EyeOff,
  Shield,
  FileText,
  ArrowRight,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
} from "lucide-react";
import { submitAccessRequest } from "../services/api";

export default function AccessRequestPage() {
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [requestedRole, setRequestedRole] = useState("tester");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password.length < 12) {
      setError("Password must be at least 12 characters long.");
      return;
    }
    if (reason.trim().length < 10) {
      setError("Please provide a meaningful business justification (at least 10 characters).");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const res = await submitAccessRequest({
        username: username.trim(),
        password,
        requested_role: requestedRole,
        reason: reason.trim(),
      });
      // Navigate to pending approval status page with username context
      navigate(`/pending-approval?username=${encodeURIComponent(username.trim())}`, {
        replace: true,
      });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail || "Failed to submit access request."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 px-4 py-12 text-slate-100">
      <div className="w-full max-w-lg rounded-2xl border border-slate-700/70 bg-slate-800/90 p-8 shadow-2xl backdrop-blur-md">
        
        {/* Header */}
        <div className="mb-6 flex items-center gap-3 border-b border-slate-700/80 pb-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/20 text-blue-400 border border-blue-500/30">
            <UserPlus className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">Request Application Access</h1>
            <p className="text-xs text-slate-400">
              Submit your credentials and justification for administrative review.
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-300">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Username */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Desired Username
            </label>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <User className="h-4 w-4" />
              </div>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. john_doe"
                minLength={3}
                className="w-full rounded-xl border border-slate-600 bg-slate-900/80 pl-9 pr-3 py-2.5 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                required
              />
            </div>
          </div>

          {/* Password */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Password (Min 12 Chars)
            </label>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <Lock className="h-4 w-4" />
              </div>
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Secure corporate password"
                minLength={12}
                className="w-full rounded-xl border border-slate-600 bg-slate-900/80 pl-9 pr-10 py-2.5 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-200"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* Role Choice */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Requested Role
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label
                className={`cursor-pointer rounded-xl border p-3.5 transition-all ${
                  requestedRole === "tester"
                    ? "border-blue-500 bg-blue-500/10 text-white shadow-sm"
                    : "border-slate-700 bg-slate-900/50 text-slate-400 hover:border-slate-600"
                }`}
              >
                <input
                  type="radio"
                  name="requestedRole"
                  value="tester"
                  checked={requestedRole === "tester"}
                  onChange={() => setRequestedRole("tester")}
                  className="sr-only"
                />
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">Tester</span>
                  <Shield className="h-4 w-4 text-blue-400" />
                </div>
                <p className="mt-1 text-[11px] text-slate-400 leading-tight">
                  Access to Cognos Test Case Studio & report validation.
                </p>
              </label>

              <label
                className={`cursor-pointer rounded-xl border p-3.5 transition-all ${
                  requestedRole === "admin"
                    ? "border-purple-500 bg-purple-500/10 text-white shadow-sm"
                    : "border-slate-700 bg-slate-900/50 text-slate-400 hover:border-slate-600"
                }`}
              >
                <input
                  type="radio"
                  name="requestedRole"
                  value="admin"
                  checked={requestedRole === "admin"}
                  onChange={() => setRequestedRole("admin")}
                  className="sr-only"
                />
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">Admin</span>
                  <Shield className="h-4 w-4 text-purple-400" />
                </div>
                <p className="mt-1 text-[11px] text-slate-400 leading-tight">
                  Approves Testers. Requires Standard Admin review.
                </p>
              </label>
            </div>
          </div>

          {/* Business Justification */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Business Justification / Reason
            </label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="State your department, project, and specific testing responsibilities…"
              className="w-full rounded-xl border border-slate-600 bg-slate-900/80 p-3 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              required
            />
          </div>

          {/* Submit */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-500/20 transition-all hover:from-blue-500 hover:to-blue-600 disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Submitting Request…</span>
                </>
              ) : (
                <>
                  <span>Submit Access Request</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </form>

        <div className="mt-6 flex items-center justify-between border-t border-slate-700/60 pt-4 text-xs text-slate-400">
          <span>Already have an approved account?</span>
          <Link to="/login" className="font-semibold text-blue-400 hover:text-blue-300 underline">
            Sign In
          </Link>
        </div>

      </div>
    </div>
  );
}
