import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Lock,
  User,
  Eye,
  EyeOff,
  Sparkles,
  ShieldCheck,
  Zap,
  Workflow,
  Activity,
  ArrowRight,
  Loader2,
  FileText,
  CheckCircle2,
  Cpu,
  Layers,
} from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";

export default function LoginPage() {
  const { login, registerFirstAdmin } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState("login"); // "login" | "bootstrap"
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
      if (import.meta.env.DEV) {
        console.error("Login failed:", {
          status: err.response?.status,
          endpoint: err.config?.url,
          response: err.response?.data,
          error: err.message,
        });
      }
      const detail = err.response?.data?.detail;
      setError(
        Array.isArray(detail)
          ? detail.map((d) => d.msg).join("; ")
          : detail || (err.message === "Network Error" ? "Network error: unable to reach the authentication server." : "Something went wrong. Please try again.")
      );
    } finally {
      setSubmitting(false);
    }
  };

  const featureCards = [
    {
      icon: Sparkles,
      title: "AI-Powered",
      description: "Advanced NLP parses complex report & DSD requirements",
      accent: "from-blue-500/10 to-cyan-500/10 text-blue-600 border-blue-200/60",
    },
    {
      icon: ShieldCheck,
      title: "Secure",
      description: "Enterprise healthcare data protection & granular RBAC",
      accent: "from-emerald-500/10 to-teal-500/10 text-emerald-600 border-emerald-200/60",
    },
    {
      icon: Zap,
      title: "Fast",
      description: "Automated generation of complete test scenarios",
      accent: "from-amber-500/10 to-orange-500/10 text-amber-600 border-amber-200/60",
    },
    {
      icon: Workflow,
      title: "Traceable",
      description: "Requirements → scenarios → verifiable test evidence",
      accent: "from-indigo-500/10 to-purple-500/10 text-indigo-600 border-indigo-200/60",
    },
  ];

  const capabilities = [
    "DSD / RDD Ingestion",
    "Gatekeeper Structural QA",
    "Cognos Semantic Proof",
    "ALM / Excel Export",
  ];

  return (
    <div className="relative h-screen max-h-screen min-h-0 w-full overflow-hidden bg-gradient-to-br from-slate-50 via-[#f0f6ff] to-[#eaf2ff] text-slate-900 selection:bg-blue-500 selection:text-white max-md:h-auto max-md:min-h-screen max-md:overflow-y-auto">
      {/* Decorative ambient lighting elements (contained absolutely so zero scroll is created) */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div className="absolute -top-24 left-1/4 h-80 w-80 rounded-full bg-blue-400/15 blur-3xl animate-float-slow" />
        <div className="absolute -bottom-24 right-1/4 h-80 w-80 rounded-full bg-indigo-400/15 blur-3xl animate-float-slow-reverse" />
        <div className="absolute top-1/2 left-10 h-64 w-64 rounded-full bg-cyan-400/10 blur-3xl animate-pulse-slow" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#3b82f608_1px,transparent_1px),linear-gradient(to_bottom,#3b82f608_1px,transparent_1px)] bg-[size:3.5rem_3.5rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)]" />
      </div>

      {/* Viewport content shell */}
      <div className="relative z-10 flex h-full flex-col justify-between px-4 py-3 sm:px-6 sm:py-4 md:px-8 md:py-4 lg:px-10 xl:px-14 min-h-0">
        
        {/* Main Grid Content Area */}
        <div className="mx-auto my-auto grid w-full max-w-7xl items-center gap-6 lg:grid-cols-12 lg:gap-8 xl:gap-12 min-h-0">
          
          {/* ========================================================== */}
          {/* LEFT SIDE: PRODUCT BRANDING / HEALTHCARE AI VALUE PROP    */}
          {/* ========================================================== */}
          <div className="order-2 flex flex-col justify-center space-y-3.5 xl:space-y-4 lg:order-1 lg:col-span-7 xl:col-span-7 min-h-0">
            
            {/* Header Badge */}
            <div className="flex items-center gap-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-200/80 bg-white/85 px-3 py-1 text-xs font-semibold text-blue-700 shadow-xs backdrop-blur-md">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75"></span>
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-600"></span>
                </span>
                <Activity className="h-3.5 w-3.5 text-blue-600" />
                <span>HealthCare AI</span>
                <span className="text-slate-300">|</span>
                <span className="text-slate-600 font-medium">Intelligent Test Automation</span>
              </div>
            </div>

            {/* Main Heading & Short Supporting Text */}
            <div className="space-y-1.5">
              <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl lg:text-3xl xl:text-4xl leading-tight">
                Healthcare{" "}
                <span className="bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 bg-clip-text text-transparent">
                  NL-to-Test-Case
                </span>{" "}
                Generation Agent
              </h1>
              <p className="max-w-xl text-xs sm:text-sm font-normal text-slate-600 leading-relaxed">
                Transform natural language requirements into comprehensive, traceable,
                and automated test cases with clinical-grade precision.
              </p>
            </div>

            {/* Futuristic Healthcare/AI Vector Concept (Compact Height) */}
            <div className="relative hidden overflow-hidden rounded-xl border border-blue-100/90 bg-gradient-to-r from-white/90 via-blue-50/30 to-white/90 px-4 py-2.5 shadow-xs backdrop-blur-md md:block">
              <div className="flex items-center justify-between gap-3">
                
                {/* Node 1: Requirements Ingestion */}
                <div className="flex flex-col items-center text-center">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-blue-200 bg-white text-blue-600 shadow-xs">
                    <FileText className="h-4 w-4" />
                  </div>
                  <span className="mt-1 text-[11px] font-semibold text-slate-700">DSD / RDD Input</span>
                  <span className="text-[10px] text-slate-400">Natural Language</span>
                </div>

                {/* Connecting Stream 1 */}
                <div className="relative flex-1">
                  <div className="h-[2px] w-full bg-gradient-to-r from-blue-200 via-indigo-300 to-blue-400" />
                  <div className="absolute -top-2 left-1/2 -translate-x-1/2 rounded-full bg-blue-100 px-1.5 py-0.25 text-[9px] font-semibold text-blue-700">
                    NLP Parse
                  </div>
                </div>

                {/* Node 2: Central Healthcare AI Engine */}
                <div className="relative flex flex-col items-center text-center">
                  <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 text-white shadow-sm shadow-blue-500/25">
                    <Cpu className="h-5 w-5 animate-pulse-slow" />
                    <div className="absolute -top-1 -right-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-emerald-500 text-[8px] font-bold text-white">
                      ✓
                    </div>
                  </div>
                  <span className="mt-1 text-[11px] font-bold text-blue-900">Healthcare AI Engine</span>
                  <span className="text-[10px] text-slate-400">Semantic Gatekeeper</span>
                </div>

                {/* Connecting Stream 2 */}
                <div className="relative flex-1">
                  <div className="h-[2px] w-full bg-gradient-to-r from-blue-400 via-indigo-300 to-emerald-300" />
                  <div className="absolute -top-2 left-1/2 -translate-x-1/2 rounded-full bg-indigo-100 px-1.5 py-0.25 text-[9px] font-semibold text-indigo-700">
                    Verify & Map
                  </div>
                </div>

                {/* Node 3: Traceable Test Cases */}
                <div className="flex flex-col items-center text-center">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-emerald-200 bg-white text-emerald-600 shadow-xs">
                    <CheckCircle2 className="h-4 w-4" />
                  </div>
                  <span className="mt-1 text-[11px] font-semibold text-slate-700">Traceable Tests</span>
                  <span className="text-[10px] text-slate-400">ALM / Excel Evidence</span>
                </div>
              </div>
            </div>

            {/* Four Compact Feature Cards */}
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              {featureCards.map((feat) => {
                const IconComponent = feat.icon;
                return (
                  <div
                    key={feat.title}
                    className="group relative flex items-start gap-2.5 rounded-xl border border-slate-200/80 bg-white/85 p-2.5 shadow-xs backdrop-blur-xs transition-all duration-200 hover:border-blue-300 hover:shadow-xs"
                  >
                    <div
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border bg-gradient-to-br ${feat.accent}`}
                    >
                      <IconComponent className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <h2 className="text-xs font-semibold text-slate-800">
                        {feat.title}
                      </h2>
                      <p className="text-[11px] text-slate-500 leading-tight">
                        {feat.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Enterprise Architecture Capabilities Strip */}
            <div className="flex flex-wrap items-center gap-1.5 pt-0.5 text-[11px] text-slate-500">
              <span className="font-semibold text-slate-700 flex items-center gap-1">
                <Layers className="h-3 w-3 text-blue-600" /> Platform Architecture:
              </span>
              {capabilities.map((cap, idx) => (
                <span
                  key={cap}
                  className="inline-flex items-center gap-1 rounded-md border border-slate-200/90 bg-white/80 px-2 py-0.5 text-slate-600 shadow-2xs"
                >
                  <span className="h-1 w-1 rounded-full bg-blue-500" />
                  {cap}
                  {idx < capabilities.length - 1 && (
                    <span className="text-slate-300 ml-0.5">·</span>
                  )}
                </span>
              ))}
            </div>

          </div>

          {/* ========================================================== */}
          {/* RIGHT SIDE: PREMIUM GLASSMORPHISM LOGIN CARD             */}
          {/* ========================================================== */}
          <div className="order-1 flex justify-center lg:order-2 lg:col-span-5 xl:col-span-5">
            <div className="w-full max-w-md rounded-2xl border border-slate-200/90 bg-white/95 p-5 sm:p-6 shadow-xl shadow-blue-900/5 backdrop-blur-xl transition-all">
              
              {/* Card Top Branding Icon & Titles */}
              <div className="mb-4 text-center">
                <div className="mx-auto mb-2 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-blue-500 text-white shadow-md shadow-blue-500/25">
                  <Activity className="h-5 w-5" />
                </div>
                <h2 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
                  {mode === "login" ? "Welcome Back!" : "Initial Admin Setup"}
                </h2>
                <p className="mt-0.5 text-xs text-slate-500">
                  {mode === "login"
                    ? "Sign in to continue to your dashboard"
                    : "Create the primary administrator account"}
                </p>
              </div>

              {/* Error State Banner */}
              {error && (
                <div
                  role="alert"
                  className="mb-3.5 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50/90 p-2.5 text-xs text-red-800 shadow-2xs animate-in fade-in duration-150"
                >
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-600" />
                  <span className="font-medium">{error}</span>
                </div>
              )}

              {/* Login / Bootstrap Form */}
              <form onSubmit={handleSubmit} className="space-y-3">
                
                {/* Username Input Field */}
                <div>
                  <label
                    htmlFor="login-username"
                    className="block text-[11px] font-semibold uppercase tracking-wider text-slate-600 mb-1"
                  >
                    Username
                  </label>
                  <div className="relative rounded-lg shadow-2xs">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                      <User className="h-4 w-4" />
                    </div>
                    <input
                      id="login-username"
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="Enter your username"
                      className="block w-full rounded-lg border border-slate-200 bg-slate-50/50 py-2 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 transition-all focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-3 focus:ring-blue-500/10"
                      required
                      minLength={3}
                      autoComplete="username"
                    />
                  </div>
                </div>

                {/* Password Input Field */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label
                      htmlFor="login-password"
                      className="block text-[11px] font-semibold uppercase tracking-wider text-slate-600"
                    >
                      Password
                    </label>
                  </div>
                  <div className="relative rounded-lg shadow-2xs">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                      <Lock className="h-4 w-4" />
                    </div>
                    <input
                      id="login-password"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      className="block w-full rounded-lg border border-slate-200 bg-slate-50/50 py-2 pl-9 pr-9 text-sm text-slate-900 placeholder:text-slate-400 transition-all focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-3 focus:ring-blue-500/10"
                      required
                      minLength={mode === "bootstrap" ? 12 : undefined}
                      autoComplete={mode === "bootstrap" ? "new-password" : "current-password"}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600 focus:text-blue-600 focus:outline-none"
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>

                  {mode === "bootstrap" && (
                    <p className="mt-1 text-[11px] text-slate-500">
                      Password must be at least 12 characters.
                    </p>
                  )}
                </div>

                {/* Submit Button */}
                <div className="pt-1">
                  <button
                    type="submit"
                    disabled={submitting}
                    className="group relative flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 py-2.5 px-4 text-sm font-semibold text-white shadow-md shadow-blue-500/20 transition-all duration-200 hover:from-blue-500 hover:via-indigo-500 hover:to-blue-600 hover:shadow-lg hover:shadow-blue-500/30 focus:outline-none focus:ring-3 focus:ring-blue-500/20 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60 disabled:shadow-none"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin text-white" />
                        <span>Signing in…</span>
                      </>
                    ) : (
                      <>
                        <span>{mode === "login" ? "Sign in" : "Create admin account"}</span>
                        <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                      </>
                    )}
                  </button>
                </div>
              </form>

              {/* Mode Toggle Link */}
              <div className="mt-4 border-t border-slate-100 pt-3 text-center">
                <button
                  type="button"
                  onClick={() => {
                    setMode(mode === "login" ? "bootstrap" : "login");
                    setError(null);
                  }}
                  className="text-xs font-medium text-blue-600 hover:text-indigo-700 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500/20 rounded-md p-0.5"
                >
                  {mode === "login"
                    ? "First time setting this up? Create initial admin"
                    : "Already have an account? Sign in instead"}
                </button>

                {mode === "bootstrap" && (
                  <p className="mt-2 rounded-lg bg-slate-50 p-2 text-left text-[11px] text-slate-500 leading-relaxed border border-slate-200/60">
                    <span className="font-semibold text-slate-700">Notice:</span> This only works once while no accounts exist. Subsequent accounts are provisioned in the Users panel.
                  </p>
                )}
              </div>

              {/* Security Footnote */}
              <div className="mt-3 flex items-center justify-center gap-1.5 text-[10px] text-slate-400">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                <span>Protected by HIPAA-compliant role-based access control</span>
              </div>

            </div>
          </div>

        </div>

        {/* Footer info strip */}
        <footer className="py-1 text-center text-[11px] text-slate-400">
          <p>© {new Date().getFullYear()} Healthcare NL-to-Test-Case Generation Agent. Enterprise Edition.</p>
        </footer>
      </div>
    </div>
  );
}
