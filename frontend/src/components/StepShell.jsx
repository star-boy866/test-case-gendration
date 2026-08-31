import { Link, useLocation, useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";

const STEPS = [
  { path: "/", label: "1. Ingestion" },
  { path: "/gatekeeper", label: "2. Gatekeeper" },
  { path: "/refinement", label: "3. Refinement" },
  { path: "/export", label: "4. Export" },
  { path: "/cognos", label: "Cognos Generation" },
];

export default function StepShell({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, hasAtLeast } = useAuth();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const steps = hasAtLeast("admin")
    ? [...STEPS, { path: "/users", label: "Users" }]
    : STEPS;

  let projectContext = null;
  try {
    const raw = localStorage.getItem("cognos_project_context");
    if (raw) projectContext = JSON.parse(raw);
  } catch {}

  if (location.pathname === "/cognos") {
    return (
      <div className="flex h-screen flex-col overflow-hidden bg-[#f8fafc] text-slate-900">
        {/* Compact Workspace Header (52px) */}
        <header className="flex h-[52px] items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-5 shrink-0 shadow-2xs z-30">
          <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
            <Link
              to="/"
              className="text-xs font-semibold text-slate-500 hover:text-blue-600 flex items-center gap-1.5 transition-colors shrink-0"
            >
              ← Back to Workflow
            </Link>
            <span className="text-slate-300 font-light hidden sm:inline">|</span>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs sm:text-sm font-bold text-slate-900 tracking-tight hidden md:inline">
                Healthcare NL-to-Test-Case Generation Agent
              </span>
              <span className="rounded-md bg-blue-50 border border-blue-200 px-2 py-0.5 text-[11px] font-semibold text-blue-700 font-mono">
                Cognos Workspace
              </span>
            </div>

            {/* Compact Project Context Strip (Only if optional project context was entered) */}
            {(projectContext?.work_item_id || projectContext?.work_item_title || projectContext?.work_type) && (
              <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-xs ml-2">
                {projectContext.work_type && (
                  <span className={`px-1.5 py-0.5 rounded font-mono font-bold text-[10px] ${
                    projectContext.work_type === "DEFECT" ? "bg-amber-100 text-amber-800" : "bg-blue-100 text-blue-800"
                  }`}>
                    {projectContext.work_type === "DEFECT" ? "DEFECT" : "CR"}
                  </span>
                )}
                {projectContext.work_item_id && (
                  <span className="font-mono font-bold text-slate-800">
                    {projectContext.work_item_id}
                  </span>
                )}
                {projectContext.work_item_title && (
                  <span className="text-slate-700 font-medium max-w-[200px] xl:max-w-[280px] truncate" title={projectContext.work_item_title}>
                    {projectContext.work_item_title}
                  </span>
                )}
                {projectContext.report_id && (
                  <>
                    <span className="text-slate-300">•</span>
                    <span className="font-mono font-bold text-slate-800">{projectContext.report_id}</span>
                  </>
                )}
                {projectContext.state && (
                  <>
                    <span className="text-slate-300">•</span>
                    <span className="font-semibold text-slate-600">{projectContext.state}</span>
                  </>
                )}
              </div>
            )}
          </div>

          {user && (
            <div className="flex items-center gap-3 text-xs shrink-0">
              <span className="text-slate-600 font-medium">
                {user.username}{" "}
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-slate-500">
                  {user.role}
                </span>
              </span>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1 text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
                title="Log out"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </header>

        {/* Full-Height Cognos Workspace */}
        <main className="flex-1 overflow-hidden min-h-0 w-full">
          {children}
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="flex items-start justify-between border-b border-slate-200 bg-white px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold text-brand-700">
            Healthcare NL-to-Test-Case Generation Agent
          </h1>
          <p className="text-sm text-slate-500">
            All 4 steps are live end-to-end, including optional SharePoint
            sync and email notification on export.
          </p>
        </div>
        {user && (
          <div className="flex items-center gap-3 text-sm">
            <span className="text-slate-600">
              {user.username}{" "}
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium uppercase text-slate-500">
                {user.role}
              </span>
            </span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1 text-slate-400 hover:text-slate-700"
              title="Log out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        )}
      </header>

      <nav className="flex gap-2 border-b border-slate-200 bg-white px-6 py-3">
        {steps.map((step) => {
          const active = location.pathname === step.path;
          return (
            <Link
              key={step.path}
              to={step.path}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                active
                  ? "bg-brand-500 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {step.label}
            </Link>
          );
        })}
      </nav>

      <main className="mx-auto max-w-4xl px-6 py-8">
        {children}
      </main>
    </div>
  );
}
