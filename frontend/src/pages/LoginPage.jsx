import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogIn, UserPlus, AlertTriangle } from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";

export default function LoginPage() {
  const { login, registerFirstAdmin } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState("login"); // "login" | "bootstrap"
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "bootstrap") {
        await registerFirstAdmin(username, password);
      } else {
        await login(username, password);
      }
      navigate("/");
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(
        Array.isArray(detail)
          ? detail.map((d) => d.msg).join("; ")
          : detail || "Something went wrong. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="mb-1 text-lg font-semibold text-brand-700">
          Healthcare NL-to-Test-Case Generation Agent
        </h1>
        <p className="mb-6 text-sm text-slate-500">
          {mode === "login" ? "Sign in to continue." : "Create the first (admin) account."}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Username</span>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              required
              minLength={3}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              required
              minLength={mode === "bootstrap" ? 12 : undefined}
            />
            {mode === "bootstrap" && (
              <span className="mt-1 block text-xs text-slate-400">At least 12 characters.</span>
            )}
          </label>

          {error && (
            <div className="flex items-start gap-2 rounded-md bg-red-50 p-3 text-xs text-red-700">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="flex w-full items-center justify-center gap-2 rounded-md bg-brand-500 px-3 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {mode === "login" ? <LogIn className="h-4 w-4" /> : <UserPlus className="h-4 w-4" />}
            {submitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create admin account"}
          </button>
        </form>

        <button
          onClick={() => {
            setMode(mode === "login" ? "bootstrap" : "login");
            setError(null);
          }}
          className="mt-4 w-full text-center text-xs text-slate-500 underline"
        >
          {mode === "login"
            ? "First time setting this up? Create the initial admin account"
            : "Already have an account? Sign in instead"}
        </button>

        {mode === "bootstrap" && (
          <p className="mt-3 text-xs text-slate-400">
            This only works once — while no accounts exist yet. Every account
            after this one is created by an admin from the Users panel.
          </p>
        )}
      </div>
    </div>
  );
}
