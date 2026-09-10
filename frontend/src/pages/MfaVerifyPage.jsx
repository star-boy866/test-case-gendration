import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ShieldCheck,
  KeyRound,
  ArrowRight,
  Loader2,
  AlertCircle,
  HelpCircle,
} from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";

export default function MfaVerifyPage() {
  const { verifyMfaCode, userHint, logout } = useAuth();
  const navigate = useNavigate();

  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [useBackupCode, setUseBackupCode] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!code.trim()) return;

    setSubmitting(true);
    setError(null);

    try {
      await verifyMfaCode(code.trim());
      navigate("/cognos", { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail || "Invalid verification code. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 px-4 py-12 text-slate-100">
      <div className="w-full max-w-md rounded-2xl border border-slate-700/70 bg-slate-800/90 p-8 shadow-2xl backdrop-blur-md">
        
        {/* Header */}
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-500/20 text-blue-400 border border-blue-500/30">
            <ShieldCheck className="h-7 w-7" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-white">Two-Factor Verification</h1>
          <p className="mt-1 text-xs text-slate-400">
            {userHint ? `Authenticating as ${userHint}` : "Enter your security code to proceed."}
          </p>
        </div>

        {error && (
          <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-300">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
              {useBackupCode ? "8-Character Recovery Code" : "6-Digit Authenticator Code"}
            </label>
            <input
              type="text"
              maxLength={useBackupCode ? 10 : 6}
              value={code}
              onChange={(e) => setCode(e.target.value.trim())}
              placeholder={useBackupCode ? "ABCD1234" : "000000"}
              autoFocus
              className="w-full rounded-xl border border-slate-600 bg-slate-900/90 px-4 py-3 text-center font-mono text-xl font-bold tracking-widest text-white placeholder-slate-600 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              required
            />
          </div>

          <button
            type="submit"
            disabled={submitting || !code.trim()}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-500/20 transition-all hover:from-blue-500 hover:to-blue-600 disabled:opacity-50"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Verifying…</span>
              </>
            ) : (
              <>
                <span>Authenticate Session</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>

        <div className="mt-6 flex flex-col items-center gap-3 border-t border-slate-700/60 pt-4 text-xs text-slate-400">
          <button
            type="button"
            onClick={() => {
              setUseBackupCode(!useBackupCode);
              setCode("");
              setError(null);
            }}
            className="text-blue-400 hover:text-blue-300 underline"
          >
            {useBackupCode ? "Use Authenticator App (TOTP)" : "Lost phone? Use an emergency recovery code"}
          </button>

          <button
            type="button"
            onClick={() => logout().then(() => navigate("/login"))}
            className="text-slate-500 hover:text-slate-300"
          >
            Cancel & Return to Login
          </button>
        </div>

      </div>
    </div>
  );
}
