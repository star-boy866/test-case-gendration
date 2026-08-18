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

      <main className="mx-auto max-w-4xl px-6 py-8">{children}</main>
    </div>
  );
}
