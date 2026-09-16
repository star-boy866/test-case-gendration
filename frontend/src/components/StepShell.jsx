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
  Shield,
  LayoutDashboard,
  List,
  PlusCircle,
  Image as ImageIcon,
  Database
} from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";
import { clearCognosWorkspaceState } from "../services/api";

export default function StepShell({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, hasAtLeast, isAdmin, isTester, isStandardAdmin } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Collapsed state persisted in localStorage or auto-collapsed on tablet screens (768px - 1023px)
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem("test_case_studio_sidebar_collapsed");
      if (saved !== null) return saved === "true";
      return typeof window !== "undefined" && window.innerWidth >= 768 && window.innerWidth < 1024;
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

  // Close mobile sidebar on route or query param change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname, location.search]);

  // Close mobile sidebar on Escape key press
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && mobileOpen) {
        setMobileOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileOpen]);

  const handleLogout = async () => {
    clearCognosWorkspaceState();
    await logout();
    navigate("/login", { replace: true });
  };

  let projectContext = null;
  try {
    const raw = localStorage.getItem("cognos_project_context");
    if (raw) projectContext = JSON.parse(raw);
  } catch {}

  const searchParams = new URLSearchParams(location.search);
  const currentTab = searchParams.get("tab") || "dashboard";
  const currentRunId = searchParams.get("run_id");
  const storedRunId = localStorage.getItem("cognos_active_run_id");
  const activeRunId = currentRunId || storedRunId;
  const isCognosActive = location.pathname === "/cognos";
  const isDashboardActive = (location.pathname === "/cognos" && (currentTab === "dashboard" || !searchParams.get("tab"))) || (location.pathname === "/tester-dashboard");
  const isScenariosActive = (location.pathname === "/cognos" && currentTab === "scenarios") || (location.pathname === "/tester-dashboard/test-cases");
  const isEvidenceActive = location.pathname === "/cognos" && currentTab === "evidence";
  const isTesterDashboardActive = location.pathname === "/tester-dashboard";
  const isTesterActive = isTesterDashboardActive;

  const isApprovalsActive = location.pathname === "/admin/approvals";
  const isUsersActive = location.pathname === "/admin/users" || location.pathname === "/users";
  const isAuditActive = location.pathname === "/admin/audit-logs";
  const isDatabaseActive = location.pathname === "/admin/database";
  const isSessionsActive = location.pathname === "/sessions";

  const getRoleBadgeStyle = (role) => {
    switch (role) {
      case "standard_admin":
        return "bg-purple-100 text-purple-800 border border-purple-200";
      case "admin":
        return "bg-indigo-100 text-indigo-800 border border-indigo-200";
      case "tester":
        return "bg-blue-100 text-blue-800 border border-blue-200";
      default:
        return "bg-slate-100 text-slate-700 border border-slate-200";
    }
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#f8fafc] text-slate-900">
      
      {/* Mobile Sidebar Backdrop Overlay */}
      {mobileOpen && (
        <div 
          className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-xs md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ================================================================ */}
      {/* SIDEBAR NAVIGATION (Collapsible: 64px collapsed, 240px expanded) */}
      {/* ================================================================ */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex flex-col justify-between border-r border-slate-200 bg-white shadow-xs transition-all duration-300 md:static ${
          collapsed ? "w-16" : "w-60"
        } ${mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}
      >
        {/* Top Branding & Navigation Area */}
        <div className="flex flex-col min-h-0">
          
          {/* Brand Header */}
          <div className={`flex h-[52px] items-center border-b border-slate-100 px-3 ${collapsed ? "justify-center" : "justify-between"}`}>
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-600 text-white shadow-xs font-bold text-xs shrink-0 tracking-wider">
                TC
              </div>
              {!collapsed && (
                <div className="flex flex-col min-w-0">
                  <span className="font-bold text-xs tracking-tight text-slate-900 truncate">
                    Test Case Studio
                  </span>
                  <span className="text-[10px] text-slate-500 truncate">
                    Cognos Test Generation
                  </span>
                </div>
              )}
            </div>

            {/* Desktop Collapse Toggle */}
            {!collapsed && (
              <button
                type="button"
                onClick={toggleCollapse}
                className="hidden rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 md:flex transition-colors"
                title="Collapse sidebar"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Collapsed expander button */}
          {collapsed && (
            <div className="hidden md:flex justify-center pt-2">
              <button
                type="button"
                onClick={toggleCollapse}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
                title="Expand sidebar"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Mobile close bar */}
          {mobileOpen && (
            <div className="flex md:hidden justify-between items-center px-3 py-2 border-b border-slate-100">
              <span className="text-xs font-bold text-slate-600">Menu</span>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                aria-label="Close sidebar"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          )}

          {/* Primary Navigation Menu */}
          <div className={`py-3 space-y-1 ${collapsed ? "px-2" : "px-3"}`}>
            
            {!collapsed && (
              <div className="px-2.5 pb-1 pt-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Core Workspace
              </div>
            )}

            {/* 1. Test Case Studio */}
            <Link
              to={activeRunId ? `/cognos?run_id=${activeRunId}&tab=dashboard` : "/cognos"}
              onClick={() => setMobileOpen(false)}
              title="Test Case Studio"
              aria-label="Test Case Studio"
              className={`group flex items-center rounded-xl transition-all duration-150 ${
                collapsed 
                  ? "justify-center h-10 w-10 mx-auto" 
                  : "justify-between px-3 py-2 text-xs font-semibold"
              } ${
                isCognosActive
                  ? "bg-blue-50/80 text-blue-700 font-bold"
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

            {/* 2. Dashboard */}
            <Link
              to={activeRunId ? `/cognos?run_id=${activeRunId}&tab=dashboard` : (isTester ? "/tester-dashboard" : "/cognos")}
              onClick={() => setMobileOpen(false)}
              title="Dashboard"
              aria-label="Dashboard"
              className={`group flex items-center rounded-xl transition-all duration-150 ${
                collapsed 
                  ? "justify-center h-10 w-10 mx-auto" 
                  : "justify-between px-3 py-2 text-xs font-semibold"
              } ${
                isDashboardActive
                  ? "bg-blue-50/80 text-blue-700 font-bold"
                  : "text-slate-600 hover:bg-slate-100/70 hover:text-slate-900"
              }`}
            >
              <div className={`flex items-center gap-2.5 min-w-0 ${collapsed ? "justify-center" : ""}`}>
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors shrink-0 ${
                    isDashboardActive
                      ? "bg-blue-600 text-white shadow-2xs"
                      : "bg-slate-100 text-slate-500 group-hover:bg-slate-200/80 group-hover:text-slate-700"
                  }`}
                >
                  <LayoutDashboard className="h-3.5 w-3.5" />
                </div>
                {!collapsed && <span className="truncate">Dashboard</span>}
              </div>
              {!collapsed && isDashboardActive && (
                <span className="h-1.5 w-1.5 rounded-full bg-blue-600 shrink-0" />
              )}
            </Link>

            {/* 3. Test Cases */}
            <Link
              to={activeRunId ? `/cognos?run_id=${activeRunId}&tab=scenarios` : "/cognos"}
              onClick={() => setMobileOpen(false)}
              title="Test Cases"
              aria-label="Test Cases"
              className={`group flex items-center rounded-xl transition-all duration-150 ${
                collapsed 
                  ? "justify-center h-10 w-10 mx-auto" 
                  : "justify-between px-3 py-2 text-xs font-semibold"
              } ${
                isScenariosActive
                  ? "bg-blue-50/80 text-blue-700 font-bold"
                  : "text-slate-600 hover:bg-slate-100/70 hover:text-slate-900"
              }`}
            >
              <div className={`flex items-center gap-2.5 min-w-0 ${collapsed ? "justify-center" : ""}`}>
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors shrink-0 ${
                    isScenariosActive
                      ? "bg-blue-600 text-white shadow-2xs"
                      : "bg-slate-100 text-slate-500 group-hover:bg-slate-200/80 group-hover:text-slate-700"
                  }`}
                >
                  <List className="h-3.5 w-3.5" />
                </div>
                {!collapsed && <span className="truncate">Test Cases</span>}
              </div>
              {!collapsed && isScenariosActive && (
                <span className="h-1.5 w-1.5 rounded-full bg-blue-600 shrink-0" />
              )}
            </Link>

            {/* 4. Evidence */}
            <Link
              to={activeRunId ? `/cognos?run_id=${activeRunId}&tab=evidence` : "/cognos"}
              onClick={() => setMobileOpen(false)}
              title="Evidence"
              aria-label="Evidence"
              className={`group flex items-center rounded-xl transition-all duration-150 ${
                collapsed 
                  ? "justify-center h-10 w-10 mx-auto" 
                  : "justify-between px-3 py-2 text-xs font-semibold"
              } ${
                isEvidenceActive
                  ? "bg-blue-50/80 text-blue-700 font-bold"
                  : "text-slate-600 hover:bg-slate-100/70 hover:text-slate-900"
              }`}
            >
              <div className={`flex items-center gap-2.5 min-w-0 ${collapsed ? "justify-center" : ""}`}>
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors shrink-0 ${
                    isEvidenceActive
                      ? "bg-blue-600 text-white shadow-2xs"
                      : "bg-slate-100 text-slate-500 group-hover:bg-slate-200/80 group-hover:text-slate-700"
                  }`}
                >
                  <ImageIcon className="h-3.5 w-3.5" />
                </div>
                {!collapsed && <span className="truncate">Evidence</span>}
              </div>
              {!collapsed && isEvidenceActive && (
                <span className="h-1.5 w-1.5 rounded-full bg-blue-600 shrink-0" />
              )}
            </Link>

            {/* 5. Upload New DSD */}
            <Link
              to="/cognos?new=true"
              onClick={() => {
                clearCognosWorkspaceState();
                setMobileOpen(false);
              }}
              title="Upload New DSD"
              aria-label="Upload New DSD"
              className={`group flex items-center rounded-xl transition-all duration-150 ${
                collapsed 
                  ? "justify-center h-10 w-10 mx-auto" 
                  : "justify-between px-3 py-2 text-xs font-semibold"
              } text-slate-600 hover:bg-slate-100/70 hover:text-slate-900`}
            >
              <div className={`flex items-center gap-2.5 min-w-0 ${collapsed ? "justify-center" : ""}`}>
                <div className="flex h-7 w-7 items-center justify-center rounded-lg transition-colors shrink-0 bg-slate-100 text-slate-500 group-hover:bg-slate-200/80 group-hover:text-slate-700">
                  <PlusCircle className="h-3.5 w-3.5" />
                </div>
                {!collapsed && <span className="truncate">Upload New DSD</span>}
              </div>
            </Link>

            {/* Admin Governance Section */}
            {isAdmin && (
              <>
                {!collapsed && (
                  <div className="px-2.5 pb-1 pt-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Administration
                  </div>
                )}

                {/* 2. Access Approvals */}
                <Link
                  to="/admin/approvals"
                  onClick={() => setMobileOpen(false)}
                  title="Access Approvals"
                  aria-label="Access Approvals"
                  className={`group flex items-center rounded-xl transition-all duration-150 ${
                    collapsed 
                      ? "justify-center h-10 w-10 mx-auto" 
                      : "justify-between px-3 py-2 text-xs font-semibold"
                  } ${
                    isApprovalsActive
                      ? "bg-blue-50/80 text-blue-700 font-bold"
                      : "text-slate-600 hover:bg-slate-100/70 hover:text-slate-900"
                  }`}
                >
                  <div className={`flex items-center gap-2.5 min-w-0 ${collapsed ? "justify-center" : ""}`}>
                    <div
                      className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors shrink-0 ${
                        isApprovalsActive
                          ? "bg-blue-600 text-white shadow-2xs"
                          : "bg-slate-100 text-slate-500 group-hover:bg-slate-200/80 group-hover:text-slate-700"
                      }`}
                    >
                      <Shield className="h-3.5 w-3.5" />
                    </div>
                    {!collapsed && <span className="truncate">Access Approvals</span>}
                  </div>
                  {!collapsed && isApprovalsActive && (
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-600 shrink-0" />
                  )}
                </Link>

                {/* 3. User & Role Management */}
                <Link
                  to="/admin/users"
                  onClick={() => setMobileOpen(false)}
                  title="Users & Roles"
                  aria-label="Users & Roles"
                  className={`group flex items-center rounded-xl transition-all duration-150 ${
                    collapsed 
                      ? "justify-center h-10 w-10 mx-auto" 
                      : "justify-between px-3 py-2 text-xs font-semibold"
                  } ${
                    isUsersActive
                      ? "bg-blue-50/80 text-blue-700 font-bold"
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
                    {!collapsed && <span className="truncate">User Directory</span>}
                  </div>
                  {!collapsed && isUsersActive && (
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-600 shrink-0" />
                  )}
                </Link>

                {/* 4. Audit Log */}
                <Link
                  to="/admin/audit-logs"
                  onClick={() => setMobileOpen(false)}
                  title="Audit Trail"
                  aria-label="Audit Trail"
                  className={`group flex items-center rounded-xl transition-all duration-150 ${
                    collapsed 
                      ? "justify-center h-10 w-10 mx-auto" 
                      : "justify-between px-3 py-2 text-xs font-semibold"
                  } ${
                    isAuditActive
                      ? "bg-blue-50/80 text-blue-700 font-bold"
                      : "text-slate-600 hover:bg-slate-100/70 hover:text-slate-900"
                  }`}
                >
                  <div className={`flex items-center gap-2.5 min-w-0 ${collapsed ? "justify-center" : ""}`}>
                    <div
                      className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors shrink-0 ${
                        isAuditActive
                          ? "bg-blue-600 text-white shadow-2xs"
                          : "bg-slate-100 text-slate-500 group-hover:bg-slate-200/80 group-hover:text-slate-700"
                      }`}
                    >
                      <Activity className="h-3.5 w-3.5" />
                    </div>
                    {!collapsed && <span className="truncate">Security Audit Trail</span>}
                  </div>
                  {!collapsed && isAuditActive && (
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-600 shrink-0" />
                  )}
                </Link>

                {/* 5. Database Explorer (Admin Only) */}
                <Link
                  to="/admin/database"
                  onClick={() => setMobileOpen(false)}
                  title="Database Explorer"
                  aria-label="Database Explorer"
                  className={`group flex items-center rounded-xl transition-all duration-150 ${
                    collapsed 
                      ? "justify-center h-10 w-10 mx-auto" 
                      : "justify-between px-3 py-2 text-xs font-semibold"
                  } ${
                    isDatabaseActive
                      ? "bg-blue-50/80 text-blue-700 font-bold"
                      : "text-slate-600 hover:bg-slate-100/70 hover:text-slate-900"
                  }`}
                >
                  <div className={`flex items-center gap-2.5 min-w-0 ${collapsed ? "justify-center" : ""}`}>
                    <div
                      className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors shrink-0 ${
                        isDatabaseActive
                          ? "bg-blue-600 text-white shadow-2xs"
                          : "bg-slate-100 text-slate-500 group-hover:bg-slate-200/80 group-hover:text-slate-700"
                      }`}
                    >
                      <Database className="h-3.5 w-3.5" />
                    </div>
                    {!collapsed && <span className="truncate">Database Explorer</span>}
                  </div>
                  {!collapsed && isDatabaseActive && (
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-600 shrink-0" />
                  )}
                </Link>

                {/* Security Section (Admin only) */}
                {!collapsed && (
                  <div className="px-2.5 pb-1 pt-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Security
                  </div>
                )}

                {/* 5. Active Sessions */}
                <Link
                  to="/sessions"
                  onClick={() => setMobileOpen(false)}
                  title="Active Sessions"
                  aria-label="Active Sessions"
                  className={`group flex items-center rounded-xl transition-all duration-150 ${
                    collapsed 
                      ? "justify-center h-10 w-10 mx-auto" 
                      : "justify-between px-3 py-2 text-xs font-semibold"
                  } ${
                    isSessionsActive
                      ? "bg-blue-50/80 text-blue-700 font-bold"
                      : "text-slate-600 hover:bg-slate-100/70 hover:text-slate-900"
                  }`}
                >
                  <div className={`flex items-center gap-2.5 min-w-0 ${collapsed ? "justify-center" : ""}`}>
                    <div
                      className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors shrink-0 ${
                        isSessionsActive
                          ? "bg-blue-600 text-white shadow-2xs"
                          : "bg-slate-100 text-slate-500 group-hover:bg-slate-200/80 group-hover:text-slate-700"
                      }`}
                    >
                      <Shield className="h-3.5 w-3.5" />
                    </div>
                    {!collapsed && <span className="truncate">Sessions & Devices</span>}
                  </div>
                  {!collapsed && isSessionsActive && (
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-600 shrink-0" />
                  )}
                </Link>
              </>
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
                    <span className={`inline-block rounded px-1.5 py-0.2 text-[9px] font-bold uppercase tracking-wider ${getRoleBadgeStyle(user.role)}`}>
                      {user.role === "standard_admin" ? "Std Admin" : user.role}
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
            <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
              <span className="text-xs sm:text-sm font-bold text-slate-900 tracking-tight truncate max-w-[150px] xs:max-w-[220px] sm:max-w-none">
                {isTester
                  ? (isTesterDashboardActive
                      ? "Tester Dashboard"
                      : location.pathname === "/tester-dashboard/test-cases"
                      ? "Assigned Test Cases"
                      : isCognosActive
                      ? (isScenariosActive ? "Test Cases & Scenarios" : "Test Case Studio")
                      : "Tester Dashboard")
                  : isAuditActive
                  ? "Security Audit Trail"
                  : isDatabaseActive
                  ? "Database Explorer & Governance"
                  : isApprovalsActive
                  ? "Access Governance & Approvals"
                  : isUsersActive
                  ? "User & Role Management"
                  : isSessionsActive
                  ? "Active Device Sessions"
                  : "Cognos Test Case Studio"}
              </span>
              <span className="hidden xs:inline-flex rounded-md bg-blue-50 border border-blue-200 px-1.5 sm:px-2 py-0.5 text-[10px] sm:text-[11px] font-semibold text-blue-700 font-mono shrink-0">
                {isTesterActive || isTester ? "SIT Testing" : isCognosActive ? "Studio Engine" : "Security & RBAC"}
              </span>
            </div>

            {/* Compact Project Context Strip (Only if optional project context was entered and matches current run) */}
            {isCognosActive && activeRunId && projectContext && String(projectContext?.run_id) === String(activeRunId) && (projectContext?.work_item_id || projectContext?.work_item_title || projectContext?.work_type || projectContext?.report_id) && (
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
        {isCognosActive ? (
          <main className="flex-1 overflow-hidden min-h-0 w-full flex flex-col">
            {children}
          </main>
        ) : (
          <main className="flex-1 overflow-y-auto min-h-0 w-full bg-[#f8fafc]">
            {children}
          </main>
        )}
      </div>

    </div>
  );
}
