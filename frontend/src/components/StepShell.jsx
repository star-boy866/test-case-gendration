import { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { 
  LogOut, 
  Sparkles, 
  Users, 
  Menu, 
  X, 
  Activity, 
  ChevronLeft,
  ChevronRight,
  Shield
} from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";

export default function StepShell({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, hasAtLeast } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Collapsed state persisted in localStorage
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem("test_case_studio_sidebar_collapsed") === "true";
    } catch {
      return false;
    }
  });

  const toggleCollapse = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("test_case_studio_sidebar_collapsed", String(next));
      } catch {}
      return next;
    });
  };

  // Close mobile sidebar on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  let projectContext = null;
  try {
    const raw = localStorage.getItem("cognos_project_context");
    if (raw) projectContext = JSON.parse(raw);
  } catch {}

  const isCognosActive = location.pathname === "/cognos";
  const isUsersActive = location.pathname === "/users";

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#f8fafc] text-slate-900">
      
      {/* Mobile Sidebar Backdrop Overlay */}
      {mobileOpen && (
        <div 
          className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-xs md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ================================================================ */}
      {/* PERSISTENT / COLLAPSIBLE LEFT SIDEBAR                            */}
      {/* ================================================================ */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex flex-col justify-between border-r border-slate-200 bg-white shadow-sm transition-all duration-200 ease-in-out md:static md:translate-x-0 ${
          mobileOpen ? "translate-x-0 w-64" : "-translate-x-full"
        } ${
          collapsed ? "md:w-[72px]" : "md:w-64"
        }`}
      >
        {/* Top Branding & Toggle Section */}
        <div className="flex flex-col">
          {collapsed ? (
            /* Collapsed Desktop Header: Toggle Button Centered */
            <div className="hidden md:flex h-[56px] items-center justify-center border-b border-slate-100 px-2">
              <button
                type="button"
                onClick={toggleCollapse}
                className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-500 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                aria-label="Expand sidebar"
                title="Expand sidebar"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          ) : (
            /* Expanded Header: Logo + Product Title + Collapse Toggle */
            <div className="flex h-[56px] items-center justify-between border-b border-slate-100 px-4">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-700 via-blue-600 to-indigo-600 text-white shadow-sm shadow-blue-500/20 shrink-0">
                  <Activity className="h-4 w-4" />
                </div>
                <div className="flex flex-col min-w-0">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Healthcare AI
                  </span>
                  <span className="text-xs font-extrabold text-slate-900 tracking-tight truncate">
                    Test Case Studio
                  </span>
                </div>
              </div>

              {/* Desktop Collapse Toggle */}
              <button
                type="button"
                onClick={toggleCollapse}
                className="hidden md:flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 shrink-0"
                aria-label="Collapse sidebar"
                title="Collapse sidebar"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>

              {/* Mobile Close Button */}
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 md:hidden"
                aria-label="Close sidebar"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          )}

          {/* Primary Navigation Menu */}
          <div className={`py-4 space-y-1.5 ${collapsed ? "px-2" : "px-3"}`}>
            {!collapsed && (
              <div className="px-2.5 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Workspace
              </div>
            )}

            {/* 1. Test Case Studio (Primary Module) */}
            <Link
              to="/cognos"
              title="Test Case Studio"
              aria-label="Test Case Studio"
              className={`group flex items-center rounded-xl transition-all duration-150 ${
                collapsed 
                  ? "justify-center h-11 w-11 mx-auto" 
                  : "justify-between px-3 py-2.5 text-xs font-semibold"
              } ${
                isCognosActive
                  ? "bg-blue-50/80 text-blue-700 shadow-2xs font-bold"
                  : "text-slate-600 hover:bg-slate-100/70 hover:text-slate-900"
              }`}
            >
              <div className={`flex items-center gap-2.5 min-w-0 ${collapsed ? "justify-center" : ""}`}>
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors shrink-0 ${
                    isCognosActive
                      ? "bg-blue-600 text-white shadow-2xs"
                      : "bg-slate-100 text-slate-500 group-hover:bg-slate-200/80 group-hover:text-slate-700"
                  }`}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                </div>
                {!collapsed && <span className="truncate">Test Case Studio</span>}
              </div>
              {!collapsed && isCognosActive && (
                <span className="h-1.5 w-1.5 rounded-full bg-blue-600 shrink-0" />
              )}
            </Link>

            {/* 2. Users (Admin Only - RBAC Gated) */}
            {hasAtLeast("admin") && (
              <Link
                to="/users"
                title="Users"
                aria-label="Users"
                className={`group flex items-center rounded-xl transition-all duration-150 ${
                  collapsed 
                    ? "justify-center h-11 w-11 mx-auto" 
                    : "justify-between px-3 py-2.5 text-xs font-semibold"
                } ${
                  isUsersActive
                    ? "bg-blue-50/80 text-blue-700 shadow-2xs font-bold"
                    : "text-slate-600 hover:bg-slate-100/70 hover:text-slate-900"
                }`}
              >
                <div className={`flex items-center gap-2.5 min-w-0 ${collapsed ? "justify-center" : ""}`}>
                  <div
                    className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors shrink-0 ${
                      isUsersActive
                        ? "bg-blue-600 text-white shadow-2xs"
                        : "bg-slate-100 text-slate-500 group-hover:bg-slate-200/80 group-hover:text-slate-700"
                    }`}
                  >
                    <Users className="h-3.5 w-3.5" />
                  </div>
                  {!collapsed && <span className="truncate">Users</span>}
                </div>
                {!collapsed && (
                  isUsersActive ? (
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-600 shrink-0" />
                  ) : (
                    <span className="text-[10px] font-medium text-slate-400 uppercase tracking-tight">Admin</span>
                  )
                )}
              </Link>
            )}
          </div>
        </div>

        {/* Bottom User Profile Card & Sign Out */}
        <div className={`border-t border-slate-100 bg-slate-50/50 ${collapsed ? "p-2 space-y-2 flex flex-col items-center" : "p-3 space-y-2.5"}`}>
          {user && (
            collapsed ? (
              <div 
                className="flex h-10 w-10 items-center justify-center rounded-xl bg-white border border-slate-200/80 shadow-2xs font-bold text-xs uppercase text-slate-700 cursor-default"
                title={`Signed in as ${user.username} (${user.role})`}
                aria-label={`Signed in as ${user.username} (${user.role})`}
              >
                {user.username ? user.username.slice(0, 2).toUpperCase() : "U"}
              </div>
            ) : (
              <div className="flex items-center justify-between rounded-xl bg-white border border-slate-200/80 p-2.5 shadow-2xs">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-700 font-bold text-xs uppercase border border-slate-200/60 shrink-0">
                    {user.username ? user.username.slice(0, 2).toUpperCase() : "U"}
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="text-xs font-bold text-slate-900 truncate">
                      {user.username}
                    </span>
                    <span className="text-[10px] text-slate-400 flex items-center gap-1 font-medium">
                      <Shield className="h-2.5 w-2.5 text-blue-600" />
                      <span className="uppercase font-semibold tracking-wider text-slate-600">
                        {user.role}
                      </span>
                    </span>
                  </div>
                </div>
              </div>
            )
          )}

          {/* Sign Out Button */}
          <button
            type="button"
            onClick={handleLogout}
            aria-label="Sign Out"
            title="Sign Out"
            className={`flex items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-700 hover:border-red-200 hover:bg-red-50 hover:text-red-700 transition-all shadow-2xs group focus:outline-none focus:ring-2 focus:ring-red-500/20 ${
              collapsed 
                ? "h-10 w-10" 
                : "w-full gap-2 px-3 py-2 text-xs font-semibold"
            }`}
          >
            <LogOut className="h-3.5 w-3.5 text-slate-400 group-hover:text-red-600 transition-colors shrink-0" />
            {!collapsed && <span>Sign Out</span>}
          </button>
        </div>
      </aside>

      {/* ================================================================ */}
      {/* MAIN VIEWPORT AREA                                               */}
      {/* ================================================================ */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0 min-h-0">
        
        {/* Compact Top Header Bar (52px) */}
        <header className="flex h-[52px] items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-5 shrink-0 shadow-2xs z-30">
          <div className="flex items-center gap-3 min-w-0">
            
            {/* Hamburger Button for Mobile */}
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-100 md:hidden shrink-0"
              aria-label="Open sidebar"
            >
              <Menu className="h-4 w-4" />
            </button>

            {/* Current Module Title & Badge */}
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs sm:text-sm font-bold text-slate-900 tracking-tight">
                {isUsersActive ? "User Management" : "Test Case Studio"}
              </span>
              <span className="rounded-md bg-blue-50 border border-blue-200 px-2 py-0.5 text-[10px] sm:text-[11px] font-semibold text-blue-700 font-mono">
                {isUsersActive ? "Admin Panel" : "Cognos Test Case Studio"}
              </span>
            </div>

            {/* Compact Project Context Strip (Only if optional project context was entered) */}
            {isCognosActive && (projectContext?.work_item_id || projectContext?.work_item_title || projectContext?.work_type) && (
              <div className="hidden xl:flex items-center gap-2 px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-xs ml-2">
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
                  <span className="text-slate-700 font-medium max-w-[200px] 2xl:max-w-[300px] truncate" title={projectContext.work_item_title}>
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

          {/* Right Header Status Strip */}
          {user && (
            <div className="flex items-center gap-2 text-xs shrink-0">
              <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-600 font-medium">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                <span>{user.username}</span>
                <span className="text-slate-300">|</span>
                <span className="uppercase text-[10px] font-bold text-slate-500">
                  {user.role}
                </span>
              </span>
              <button
                type="button"
                onClick={handleLogout}
                className="flex items-center gap-1 text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
                title="Sign Out"
                aria-label="Sign Out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          )}
        </header>

        {/* Content Body */}
        {isUsersActive ? (
          <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 max-w-5xl w-full mx-auto">
            {children}
          </main>
        ) : (
          <main className="flex-1 overflow-hidden min-h-0 w-full flex flex-col">
            {children}
          </main>
        )}
      </div>

    </div>
  );
}
