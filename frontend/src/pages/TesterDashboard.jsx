import { useState, useEffect, useMemo } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { 
  FileSpreadsheet, Download, Eye, Clock, CheckCircle2, 
  Search, Shield, AlertCircle, LogOut, RefreshCw,
  FileText, ArrowRight, Layers, X, ChevronRight, Tag, Sparkles,
  LayoutDashboard, Briefcase, Filter, ExternalLink, CheckSquare
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { getTesterAssignedFiles, viewAssignedFileTestCases, downloadAssignedFile, clearCognosWorkspaceState } from "../services/api";

export default function TesterDashboard() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();


  // Determine current view based on URL route
  const isTestCasesView = location.pathname === "/tester-dashboard/test-cases";

  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloadingId, setDownloadingId] = useState(null);

  // Search and filter state for Test Cases view
  const [tableSearch, setTableSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  // Modal / drawer state for viewing test cases
  const [viewingFile, setViewingFile] = useState(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [testCasesData, setTestCasesData] = useState(null);
  const [selectedTestCase, setSelectedTestCase] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");

  const handleLogout = async () => {
    clearCognosWorkspaceState();
    await logout();
    navigate("/login", { replace: true });
  };

  const fetchAssignedFiles = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getTesterAssignedFiles();
      const fileList = Array.isArray(res.data) ? res.data : [];
      setFiles(fileList);
    } catch (err) {
      console.error("Failed to load assigned test cases:", err);
      setError(
        err.response?.data?.detail || "Unable to load your assigned test case files. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssignedFiles();
  }, []);

  const handleDownload = async (file) => {
    setDownloadingId(file.file_id);
    try {
      await downloadAssignedFile(file.file_id, file.file_name);
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to download test case file.");
    } finally {
      setDownloadingId(null);
    }
  };

  const handleNavigateToStudio = (targetFile) => {
    try {
      if (targetFile?.run_id) {
        localStorage.setItem("cognos_active_run_id", String(targetFile.run_id));
        const projectCtx = {
          run_id: targetFile.run_id,
          report_id: targetFile.report_id || "",
          report_title: targetFile.report_title || targetFile.project_name || "Cognos Report",
          work_item_title: targetFile.project_name || targetFile.report_title || "",
          work_item_id: targetFile.file_id || "",
          work_type: targetFile.work_type || "CR",
          state: targetFile.status || "Ready",
        };
        localStorage.setItem("cognos_project_context", JSON.stringify(projectCtx));
        sessionStorage.removeItem("cognos_active_result");
      }
    } catch {}
  };

  const handleView = async (file) => {
    setViewingFile(file);
    setViewLoading(true);
    setSearchTerm("");
    setCategoryFilter("ALL");
    try {
      const res = await viewAssignedFileTestCases(file.file_id);
      setTestCasesData(res.data);
      if (res.data.test_cases?.length > 0) {
        setSelectedTestCase(res.data.test_cases[0]);
      } else {
        setSelectedTestCase(null);
      }
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to load test cases.");
      setViewingFile(null);
    } finally {
      setViewLoading(false);
    }
  };

  // Extract categories for modal filter
  const categories = useMemo(() => {
    if (!testCasesData?.test_cases) return ["ALL"];
    const cats = new Set(testCasesData.test_cases.map((t) => t.category).filter(Boolean));
    return ["ALL", ...Array.from(cats).sort()];
  }, [testCasesData]);

  // Filtered test scenarios inside the modal viewer
  const filteredScenarios = useMemo(() => {
    if (!testCasesData?.test_cases) return [];
    return testCasesData.test_cases.filter((tc) => {
      const matchesSearch =
        !searchTerm ||
        tc.test_case_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        tc.test_case_title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        tc.objective?.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCategory =
        categoryFilter === "ALL" || tc.category === categoryFilter;
      return matchesSearch && matchesCategory;
    });
  }, [testCasesData, searchTerm, categoryFilter]);

  // Filtered files for Test Cases table view
  const filteredFiles = useMemo(() => {
    return files.filter((f) => {
      const q = tableSearch.toLowerCase().trim();
      const matchesSearch =
        !q ||
        (f.file_name && f.file_name.toLowerCase().includes(q)) ||
        (f.file_id && f.file_id.toLowerCase().includes(q)) ||
        (f.project_name && f.project_name.toLowerCase().includes(q)) ||
        (f.report_id && f.report_id.toLowerCase().includes(q)) ||
        (f.dsd_name && f.dsd_name.toLowerCase().includes(q));

      const matchesStatus =
        statusFilter === "ALL" ||
        (f.status || "Ready").toUpperCase() === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [files, tableSearch, statusFilter]);

  // KPI Metrics calculation for Dashboard overview
  const totalScenarios = useMemo(() => {
    return files.reduce((acc, f) => acc + (Number(f.test_case_count) || 0), 0);
  }, [files]);

  const uniqueProjectsCount = useMemo(() => {
    const projects = new Set(files.map((f) => f.project_name || f.report_id).filter(Boolean));
    return projects.size;
  }, [files]);

  const activeRunId = typeof window !== "undefined" ? localStorage.getItem("cognos_active_run_id") : null;
  const activeFile = activeRunId ? files.find((f) => String(f.run_id) === String(activeRunId)) : null;
  const activeProject = activeFile ? activeFile.project_name || activeFile.report_id : null;
  const activeDsd = activeFile ? activeFile.dsd_name || activeFile.report_id : null;

  return (
    <div className="min-h-full flex flex-col bg-slate-50 text-slate-900 pb-6 sm:pb-8 overflow-x-hidden">
      {/* ── 1. Top Executive Welcome & Status Header ───────────────────────── */}
      <div className="border-b border-slate-200/80 bg-white px-4 py-3 sm:px-6 sm:py-3.5 shadow-2xs">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4">
          <div className="space-y-0.5 min-w-0">
            {/* Breadcrumb / Category Tag */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-200/70">
                <Shield className="h-3 w-3 text-blue-600" />
                Tester Workspace
              </span>
              {isTestCasesView ? (
                <>
                  <span className="text-slate-300">•</span>
                  <div className="flex items-center gap-1 text-xs text-slate-500 font-medium">
                    <Link to="/tester-dashboard" className="hover:text-blue-600 transition-colors">
                      Dashboard
                    </Link>
                    <ChevronRight className="h-3 w-3 text-slate-400" />
                    <span className="text-slate-800 font-semibold">Assigned Test Cases</span>
                  </div>
                </>
              ) : (
                <>
                  {activeProject && (
                    <>
                      <span className="text-slate-300">•</span>
                      <span className="text-xs font-medium text-slate-600 flex items-center gap-1.5 truncate">
                        <span className="font-semibold text-slate-800">Project:</span> {activeProject}
                      </span>
                    </>
                  )}
                  {activeDsd && activeDsd !== activeProject && (
                    <>
                      <span className="text-slate-300">•</span>
                      <span className="text-xs font-medium text-slate-600 truncate">
                        <span className="font-semibold text-slate-800">DSD:</span> {activeDsd}
                      </span>
                    </>
                  )}
                </>
              )}
            </div>

            <h1 className="text-lg sm:text-xl md:text-2xl font-extrabold text-slate-900 tracking-tight">
              {isTestCasesView ? (
                <>Assigned <span className="text-blue-700">Test Cases</span></>
              ) : (
                <>Welcome back, <span className="text-blue-700">{user?.username || "Tester"}</span></>
              )}
            </h1>
            <p className="text-xs text-slate-500 font-normal">
              {isTestCasesView 
                ? "Authoritative Cognos test cases assigned to your account. Select any test case to open the full Cognos Scenario workspace."
                : "Executive testing dashboard. Track your assigned test suites, scenario coverage, and execution readiness."}
            </p>
          </div>

          {/* User Controls & Logout Action */}
          <div className="flex items-center gap-2 shrink-0 self-start sm:self-auto">
            <Link
              to={localStorage.getItem("cognos_active_run_id") ? `/cognos?run_id=${localStorage.getItem("cognos_active_run_id")}&tab=dashboard` : "/cognos"}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-xs transition-colors cursor-pointer"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Test Case Studio
            </Link>
            <button
              type="button"
              onClick={fetchAssignedFiles}
              disabled={loading}
              title="Refresh assigned files"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 shadow-xs transition-colors cursor-pointer"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-blue-600" : "text-slate-500"}`} />
              Refresh
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 shadow-xs transition-colors cursor-pointer"
            >
              <LogOut className="h-3.5 w-3.5 text-red-600" />
              Sign Out
            </button>
          </div>
        </div>
      </div>

      {/* ── 2. VIEW A: TESTER DASHBOARD OVERVIEW (/tester-dashboard) ────────── */}
      {!isTestCasesView && (
        <div className="max-w-7xl mx-auto w-full px-3 sm:px-6 pt-3.5 sm:pt-4 flex-1 flex flex-col gap-3.5 sm:gap-4 min-h-0">
          
          {/* KPI Stat Cards Grid (4-grid) */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3">
            {/* KPI 1: Assigned Files */}
            <div className="rounded-xl border border-slate-200 bg-white p-3 sm:p-3.5 shadow-2xs flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 shrink-0 shadow-2xs">
                <FileSpreadsheet className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="text-xl font-bold text-slate-900 font-mono tracking-tight">
                  {loading ? "..." : files.length}
                </div>
                <div className="text-[11px] font-medium text-slate-500 truncate">
                  Assigned Files
                </div>
              </div>
            </div>

            {/* KPI 2: Total Test Scenarios */}
            <div className="rounded-xl border border-slate-200 bg-white p-3 sm:p-3.5 shadow-2xs flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shrink-0 shadow-2xs">
                <Layers className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="text-xl font-bold text-slate-900 font-mono tracking-tight">
                  {loading ? "..." : totalScenarios}
                </div>
                <div className="text-[11px] font-medium text-slate-500 truncate">
                  Total Scenarios
                </div>
              </div>
            </div>

            {/* KPI 3: Active Projects */}
            <div className="rounded-xl border border-slate-200 bg-white p-3 sm:p-3.5 shadow-2xs flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600 shrink-0 shadow-2xs">
                <Briefcase className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="text-xl font-bold text-slate-900 font-mono tracking-tight">
                  {loading ? "..." : uniqueProjectsCount}
                </div>
                <div className="text-[11px] font-medium text-slate-500 truncate">
                  Active Projects
                </div>
              </div>
            </div>

            {/* KPI 4: SIT Execution Status */}
            <div className="rounded-xl border border-slate-200 bg-white p-3 sm:p-3.5 shadow-2xs flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 shrink-0 shadow-2xs">
                <CheckCircle2 className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold text-emerald-700 font-mono tracking-tight uppercase">
                  {loading ? "..." : files.length > 0 ? "Ready for Testing" : "Awaiting Files"}
                </div>
                <div className="text-[11px] font-medium text-slate-500 truncate">
                  SIT Role Status
                </div>
              </div>
            </div>
          </div>

          {/* Quick-Action Banner to Test Cases */}
          <div className="rounded-xl border border-blue-200 bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 p-3.5 sm:p-4 text-white shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="space-y-0.5 max-w-2xl">
              <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-500/30 text-blue-200 text-[10px] font-semibold tracking-wide border border-blue-400/20">
                <Sparkles className="h-3 w-3 text-blue-300" />
                Tester Test Cases Workspace
              </div>
              <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                Review & Execute Your Assigned Cognos Test Scenarios
              </h3>
              <p className="text-xs text-slate-300 leading-normal">
                Filter test suites by report or DSD, inspect detailed Test Steps and Test Data, verify DSD Evidence, and review SQL & Source Mappings.
              </p>
            </div>
            <Link
              to="/tester-dashboard/test-cases"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs shadow-xs transition-all shrink-0 hover:scale-102 cursor-pointer"
            >
              <span>Go to Test Cases</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          {/* Active Assignments Overview */}
          <div className="rounded-2xl border border-slate-200 bg-white shadow-xs overflow-hidden flex flex-col">
            <div className="border-b border-slate-100 px-4 py-3 sm:px-5 sm:py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h2 className="text-sm sm:text-base font-bold text-slate-900 flex items-center gap-2">
                  <FileSpreadsheet className="h-4 w-4 text-blue-600" />
                  Active Assigned Test Suites
                </h2>
                <p className="text-[11px] sm:text-xs text-slate-500 mt-0.5">
                  Direct access to verify and execute test scenarios provisioned for your account.
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Link
                  to="/tester-dashboard/test-cases"
                  className="inline-flex items-center gap-1 text-xs font-bold text-blue-700 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-2.5 py-1 rounded-lg border border-blue-200 transition-colors"
                >
                  <span>View All in Test Cases Workspace</span>
                  <ChevronRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>

            {/* List / Table Content or Empty State */}
            {loading ? (
              <div className="flex flex-col items-center justify-center py-20 text-slate-400">
                <RefreshCw className="h-8 w-8 animate-spin text-blue-600 mb-3" />
                <p className="text-sm font-medium text-slate-600">Loading your assigned files…</p>
              </div>
            ) : error ? (
              <div className="p-8 text-center">
                <div className="inline-flex p-3 rounded-full bg-red-50 text-red-600 mb-3">
                  <AlertCircle className="h-6 w-6" />
                </div>
                <h3 className="text-base font-bold text-slate-900">Unable to load assigned files</h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-4">{error}</p>
                <button
                  type="button"
                  onClick={fetchAssignedFiles}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700 shadow-xs cursor-pointer"
                >
                  Try Again
                </button>
              </div>
            ) : files.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 px-6 text-center">
                <div className="h-16 w-16 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 mb-4 shadow-xs">
                  <FileText className="h-8 w-8" />
                </div>
                <h3 className="text-lg font-bold text-slate-900">No Test Cases Assigned Yet</h3>
                <p className="text-xs sm:text-sm text-slate-500 max-w-md mt-1.5 leading-relaxed mb-4">
                  Your assigned test cases files will appear here as soon as they are provisioned by an administrator.
                  Contact your test lead or administrator for assignment.
                </p>
              </div>
            ) : (
              <>
                {/* Mobile & Tablet Card List (< lg) */}
                <div className="lg:hidden divide-y divide-slate-100">
                  {files.slice(0, 5).map((file) => (
                    <div key={file.file_id || file.run_id} className="p-3.5 space-y-2.5 bg-white">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="h-8 w-8 rounded-lg bg-emerald-50 border border-emerald-200/80 text-emerald-700 flex items-center justify-center shrink-0">
                            <FileSpreadsheet className="h-4 w-4" />
                          </div>
                          <div className="min-w-0">
                            <Link
                              to={`/cognos?run_id=${file.run_id}&tab=scenarios`}
                              onClick={() => handleNavigateToStudio(file)}
                              className="font-bold text-slate-900 hover:text-blue-600 font-mono text-xs truncate block"
                            >
                              {file.file_name}
                            </Link>
                            <div className="text-[10px] text-slate-500 truncate">
                              {file.project_name || file.report_id}
                            </div>
                          </div>
                        </div>
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-800 border border-blue-200 font-mono shrink-0">
                          {file.test_case_count} Scenarios
                        </span>
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-50">
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded border border-emerald-200">
                          <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                          {file.status || "Ready"}
                        </span>
                        <span className="font-mono text-[10px]">
                          {file.assigned_date ? new Date(file.assigned_date).toLocaleDateString() : "—"}
                        </span>
                      </div>

                      <div className="grid grid-cols-3 gap-1.5 pt-1">
                        <Link
                          to={`/cognos?run_id=${file.run_id}&tab=scenarios`}
                          onClick={() => handleNavigateToStudio(file)}
                          className="inline-flex items-center justify-center gap-1 py-1.5 px-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-2xs"
                        >
                          <Sparkles className="h-3 w-3" /> View Scenarios
                        </Link>
                        <button
                          type="button"
                          onClick={() => handleView(file)}
                          className="inline-flex items-center justify-center gap-1 py-1.5 px-2 rounded-lg bg-blue-50 text-blue-700 text-xs font-bold border border-blue-200 cursor-pointer"
                        >
                          <Eye className="h-3 w-3" /> Quick View
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDownload(file)}
                          disabled={downloadingId === file.file_id}
                          className="inline-flex items-center justify-center gap-1 py-1.5 px-2 rounded-lg bg-slate-900 text-white text-xs font-bold disabled:opacity-60 cursor-pointer"
                        >
                          <Download className="h-3 w-3" />
                          {downloadingId === file.file_id ? "..." : "Export"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Authoritative Files Table (>= lg) */}
                <div className="hidden lg:block overflow-x-auto">
                  <table className="w-full table-fixed text-left text-xs text-slate-700">
                    <thead className="bg-slate-50/80 border-b border-slate-100 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                      <tr>
                        <th scope="col" className="px-3.5 py-2.5 sm:px-4 sm:py-3 min-w-0">Test Cases File</th>
                        <th scope="col" className="px-3.5 py-2.5 sm:px-4 sm:py-3 min-w-0">Assigned Project / DSD</th>
                        <th scope="col" className="px-2 py-2.5 sm:py-3 text-center w-[75px] min-w-[75px] shrink-0">Scenarios</th>
                        <th scope="col" className="px-2 py-2.5 sm:py-3 text-center w-[90px] min-w-[90px] shrink-0">Status</th>
                        <th scope="col" className="px-2 py-2.5 sm:py-3 text-center w-[105px] min-w-[105px] shrink-0">Assigned Date</th>
                        <th scope="col" className="px-2.5 py-2.5 sm:py-3 text-right w-[280px] min-w-[280px] shrink-0">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {files.slice(0, 5).map((file) => (
                        <tr key={file.file_id || file.run_id} className="hover:bg-slate-50/60 transition-colors">
                          <td className="px-3.5 py-2.5 sm:px-4 sm:py-3 min-w-0">
                            <div className="flex items-center gap-2.5 min-w-0">
                              <div className="h-8 w-8 rounded-lg bg-emerald-50 border border-emerald-200/80 text-emerald-700 flex items-center justify-center shrink-0 shadow-2xs">
                                <FileSpreadsheet className="h-4 w-4" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <Link
                                  to={`/cognos?run_id=${file.run_id}&tab=scenarios`}
                                  onClick={() => handleNavigateToStudio(file)}
                                  className="font-bold text-slate-900 hover:text-blue-600 font-mono text-xs truncate block transition-colors"
                                  title={file.file_name}
                                >
                                  {file.file_name}
                                </Link>
                                <div className="text-[10px] font-mono text-slate-400 mt-0.5 truncate" title={`ID: ${file.file_id}`}>
                                  ID: {file.file_id}
                                </div>
                              </div>
                            </div>
                          </td>

                          <td className="px-3.5 py-2.5 sm:px-4 sm:py-3 min-w-0">
                            <div className="font-semibold text-slate-900 truncate text-xs" title={file.project_name || file.report_id}>
                              {file.project_name || file.report_id}
                            </div>
                            <div className="text-[11px] text-slate-500 truncate mt-0.5" title={file.dsd_name}>
                              {file.dsd_name}
                            </div>
                          </td>

                          <td className="px-2 py-2.5 sm:py-3 text-center w-[75px] min-w-[75px]">
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-extrabold bg-blue-50 text-blue-800 border border-blue-200/70 font-mono">
                              {file.test_case_count}
                            </span>
                          </td>

                          <td className="px-2 py-2.5 sm:py-3 text-center w-[90px] min-w-[90px]">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                              {file.status || "Ready"}
                            </span>
                          </td>

                          <td className="px-2 py-2.5 sm:py-3 text-center font-mono text-slate-500 whitespace-nowrap text-[11px] w-[105px] min-w-[105px]">
                            {file.assigned_date ? new Date(file.assigned_date).toLocaleDateString() : "—"}
                          </td>

                          <td className="px-2.5 py-2.5 sm:py-3 text-right whitespace-nowrap w-[280px] min-w-[280px]">
                            <div className="flex items-center justify-end gap-1.5">
                              <Link
                                to={`/cognos?run_id=${file.run_id}&tab=scenarios`}
                                onClick={() => handleNavigateToStudio(file)}
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 text-xs font-semibold shadow-2xs transition-colors cursor-pointer"
                                title="Open Test Cases Workspace"
                              >
                                <Sparkles className="h-3.5 w-3.5" />
                                <span>View Scenarios</span>
                              </Link>

                              <button
                                type="button"
                                onClick={() => handleView(file)}
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 text-xs font-semibold border border-blue-200 transition-colors shadow-2xs cursor-pointer"
                                title="Quick View Test Cases"
                              >
                                <Eye className="h-3.5 w-3.5" />
                                <span>Quick View</span>
                              </button>

                              <button
                                type="button"
                                onClick={() => handleDownload(file)}
                                disabled={downloadingId === file.file_id}
                                className="inline-flex items-center justify-center p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors shadow-2xs disabled:opacity-60 cursor-pointer"
                                title="Export Excel (.xlsx)"
                              >
                                <Download className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>

          {/* Healthcare SIT Testing Guidelines Card */}
          <div className="rounded-xl border border-slate-200 bg-white p-3 sm:p-3.5 shadow-2xs flex items-start gap-3">
            <div className="p-1.5 rounded-lg bg-blue-50 text-blue-600 shrink-0 border border-blue-100">
              <Shield className="h-5 w-5" />
            </div>
            <div className="space-y-1 text-xs">
              <h4 className="font-bold text-slate-900 text-sm">
                Healthcare SIT Testing & Isolation Protocol
              </h4>
              <p className="text-slate-600 leading-relaxed">
                As an authorized Tester, your account is scoped strictly to assigned test suites with cryptographically enforced access control. When executing test scenarios, you have full access to inspect <strong>Test Steps</strong>, <strong>Test Data</strong>, <strong>DSD Source Evidence</strong>, and <strong>SQL & Source Mappings</strong>.
              </p>
            </div>
          </div>

        </div>
      )}

      {/* ── 3. VIEW B: TESTER TEST CASES WORKSPACE (/tester-dashboard/test-cases) ── */}
      {isTestCasesView && (
        <div className="max-w-7xl mx-auto w-full px-3 sm:px-6 pt-4 sm:pt-6 flex-1 flex flex-col min-h-0">
          <div className="rounded-2xl border border-slate-200 bg-white shadow-xs overflow-hidden flex flex-col flex-1">
            
            {/* Header & Search Toolbar */}
            <div className="border-b border-slate-100 px-4 py-3.5 sm:px-6 sm:py-4 flex flex-col gap-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <Layers className="h-4 w-4 text-blue-600" />
                    Assigned Test Cases & Scenarios
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Select any assigned test case to open the full Cognos Scenario workspace with Test Steps, Data, Evidence, and SQL.
                  </p>
                </div>
                <div className="text-xs font-semibold text-slate-600 bg-slate-50 px-3 py-1 rounded-full border border-slate-200 shrink-0 self-start sm:self-auto">
                  {filteredFiles.length} of {files.length} {files.length === 1 ? "File" : "Files"}
                </div>
              </div>

              {/* Search & Filter Toolbar */}
              <div className="flex flex-col sm:flex-row items-center gap-2.5 pt-1">
                <div className="relative flex-1 w-full">
                  <Search className="h-3.5 w-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search by test case name, ID, project, or DSD..."
                    value={tableSearch}
                    onChange={(e) => setTableSearch(e.target.value)}
                    className="w-full pl-8 pr-3 py-2 text-xs rounded-lg border border-slate-200 bg-slate-50/50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-slate-800 placeholder-slate-400"
                  />
                  {tableSearch && (
                    <button
                      type="button"
                      onClick={() => setTableSearch("")}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="py-2 px-3 text-xs rounded-lg border border-slate-200 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-blue-500/20 w-full sm:w-auto"
                  >
                    <option value="ALL">All Statuses</option>
                    <option value="READY">Ready</option>
                    <option value="ASSIGNED">Assigned</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Table Content or Empty State */}
            {loading ? (
              <div className="flex flex-col items-center justify-center py-20 text-slate-400">
                <RefreshCw className="h-8 w-8 animate-spin text-blue-600 mb-3" />
                <p className="text-sm font-medium text-slate-600">Loading your assigned test cases…</p>
              </div>
            ) : error ? (
              <div className="p-8 text-center">
                <div className="inline-flex p-3 rounded-full bg-red-50 text-red-600 mb-3">
                  <AlertCircle className="h-6 w-6" />
                </div>
                <h3 className="text-base font-bold text-slate-900">Unable to load assigned files</h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-4">{error}</p>
                <button
                  type="button"
                  onClick={fetchAssignedFiles}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700 shadow-xs cursor-pointer"
                >
                  Try Again
                </button>
              </div>
            ) : filteredFiles.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-24 px-6 text-center">
                <div className="h-16 w-16 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 mb-4 shadow-xs">
                  <FileText className="h-8 w-8" />
                </div>
                <h3 className="text-lg font-bold text-slate-900">
                  {files.length === 0 ? "No Test Cases Assigned Yet" : "No Matching Test Cases Found"}
                </h3>
                <p className="text-xs sm:text-sm text-slate-500 max-w-md mt-1.5 leading-relaxed mb-4">
                  {files.length === 0 
                    ? "Your assigned test cases files will appear here as soon as they are provisioned by an administrator."
                    : "No test case files match your current search query. Clear the search input to view all assigned files."}
                </p>
                {files.length > 0 && tableSearch && (
                  <button
                    type="button"
                    onClick={() => {
                      setTableSearch("");
                      setStatusFilter("ALL");
                    }}
                    className="inline-flex items-center gap-1.5 px-4 py-2 bg-slate-100 text-slate-700 text-xs font-bold rounded-lg hover:bg-slate-200 transition-colors"
                  >
                    Reset Filters
                  </button>
                )}
              </div>
            ) : (
              <>
                {/* Mobile & Tablet Card List (< lg) */}
                <div className="lg:hidden divide-y divide-slate-100">
                  {filteredFiles.map((file) => (
                    <div key={file.file_id || file.run_id} className="p-4 space-y-3 bg-white">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="h-9 w-9 rounded-xl bg-emerald-50 border border-emerald-200/80 text-emerald-700 flex items-center justify-center shrink-0">
                            <FileSpreadsheet className="h-4.5 w-4.5" />
                          </div>
                          <div className="min-w-0">
                            <Link
                              to={`/cognos?run_id=${file.run_id}&tab=scenarios`}
                              onClick={() => handleNavigateToStudio(file)}
                              className="font-bold text-slate-900 hover:text-blue-600 font-mono text-xs truncate block"
                              title="Open Cognos Test Case Scenario Workspace"
                            >
                              {file.file_name}
                            </Link>
                            <div className="text-[10px] text-slate-500 truncate">
                              {file.project_name || file.report_id}
                            </div>
                            <div className="text-[10px] font-mono text-slate-400">
                              ID: {file.file_id}
                            </div>
                          </div>
                        </div>
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-800 border border-blue-200 font-mono shrink-0">
                          {file.test_case_count} Scenarios
                        </span>
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-50">
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded border border-emerald-200">
                          <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                          {file.status || "Ready"}
                        </span>
                        <span className="font-mono text-[10px]">
                          Assigned: {file.assigned_date ? new Date(file.assigned_date).toLocaleDateString() : "—"}
                        </span>
                      </div>

                      <div className="grid grid-cols-3 gap-1.5 pt-1">
                        <Link
                          to={`/cognos?run_id=${file.run_id}&tab=scenarios`}
                          onClick={() => handleNavigateToStudio(file)}
                          className="inline-flex items-center justify-center gap-1 py-2 px-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-2xs cursor-pointer"
                        >
                          <Sparkles className="h-3.5 w-3.5" /> View Scenarios
                        </Link>
                        <button
                          type="button"
                          onClick={() => handleView(file)}
                          className="inline-flex items-center justify-center gap-1 py-2 px-2 rounded-lg bg-blue-50 text-blue-700 text-xs font-bold border border-blue-200 cursor-pointer"
                        >
                          <Eye className="h-3.5 w-3.5" /> Quick View
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDownload(file)}
                          disabled={downloadingId === file.file_id}
                          className="inline-flex items-center justify-center gap-1 py-2 px-2 rounded-lg bg-slate-900 text-white text-xs font-bold disabled:opacity-60 cursor-pointer"
                        >
                          <Download className="h-3.5 w-3.5" />
                          {downloadingId === file.file_id ? "..." : "Export"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Authoritative Files Table (>= lg) */}
                <div className="hidden lg:block overflow-x-auto">
                  <table className="w-full table-fixed text-left text-xs text-slate-700">
                    <thead className="bg-slate-50/80 border-b border-slate-100 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                      <tr>
                        <th scope="col" className="px-3.5 py-2.5 sm:px-4 sm:py-3 min-w-0">Test Cases File</th>
                        <th scope="col" className="px-3.5 py-2.5 sm:px-4 sm:py-3 min-w-0">Assigned Project / DSD</th>
                        <th scope="col" className="px-2 py-2.5 sm:py-3 text-center w-[75px] min-w-[75px] shrink-0">Scenarios</th>
                        <th scope="col" className="px-2 py-2.5 sm:py-3 text-center w-[90px] min-w-[90px] shrink-0">Status</th>
                        <th scope="col" className="px-2 py-2.5 sm:py-3 text-center w-[105px] min-w-[105px] shrink-0">Assigned Date</th>
                        <th scope="col" className="px-2 py-2.5 sm:py-3 text-center w-[105px] min-w-[105px] shrink-0">Updated Date</th>
                        <th scope="col" className="px-2.5 py-2.5 sm:py-3 text-right w-[280px] min-w-[280px] shrink-0">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredFiles.map((file) => (
                        <tr key={file.file_id || file.run_id} className="hover:bg-slate-50/60 transition-colors">
                          <td className="px-3.5 py-2.5 sm:px-4 sm:py-3 min-w-0">
                            <div className="flex items-center gap-2.5 min-w-0">
                              <div className="h-8 w-8 rounded-lg bg-emerald-50 border border-emerald-200/80 text-emerald-700 flex items-center justify-center shrink-0 shadow-2xs">
                                <FileSpreadsheet className="h-4 w-4" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <Link
                                  to={`/cognos?run_id=${file.run_id}&tab=scenarios`}
                                  onClick={() => handleNavigateToStudio(file)}
                                  className="font-bold text-slate-900 hover:text-blue-600 font-mono text-xs truncate block transition-colors"
                                  title={file.file_name}
                                >
                                  {file.file_name}
                                </Link>
                                <div className="text-[10px] font-mono text-slate-400 mt-0.5 truncate" title={`ID: ${file.file_id}`}>
                                  ID: {file.file_id}
                                </div>
                              </div>
                            </div>
                          </td>

                          <td className="px-3.5 py-2.5 sm:px-4 sm:py-3 min-w-0">
                            <div className="font-semibold text-slate-900 truncate text-xs" title={file.project_name || file.report_id}>
                              {file.project_name || file.report_id}
                            </div>
                            <div className="text-[11px] text-slate-500 truncate mt-0.5" title={file.dsd_name}>
                              {file.dsd_name}
                            </div>
                          </td>

                          <td className="px-2 py-2.5 sm:py-3 text-center w-[75px] min-w-[75px]">
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-extrabold bg-blue-50 text-blue-800 border border-blue-200/70 font-mono">
                              {file.test_case_count}
                            </span>
                          </td>

                          <td className="px-2 py-2.5 sm:py-3 text-center w-[90px] min-w-[90px]">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                              {file.status || "Ready"}
                            </span>
                          </td>

                          <td className="px-2 py-2.5 sm:py-3 text-center font-mono text-slate-500 whitespace-nowrap text-[11px] w-[105px] min-w-[105px]">
                            {file.assigned_date ? new Date(file.assigned_date).toLocaleDateString() : "—"}
                          </td>

                          <td className="px-2 py-2.5 sm:py-3 text-center font-mono text-slate-500 whitespace-nowrap text-[11px] w-[105px] min-w-[105px]">
                            {file.updated_date ? new Date(file.updated_date).toLocaleDateString() : "—"}
                          </td>

                          <td className="px-2.5 py-2.5 sm:py-3 text-right whitespace-nowrap w-[280px] min-w-[280px]">
                            <div className="flex items-center justify-end gap-1.5">
                              <Link
                                to={`/cognos?run_id=${file.run_id}&tab=scenarios`}
                                onClick={() => handleNavigateToStudio(file)}
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 text-xs font-semibold shadow-2xs transition-colors cursor-pointer"
                                title="Open Test Cases Workspace"
                              >
                                <Sparkles className="h-3.5 w-3.5" />
                                <span>View Scenarios</span>
                              </Link>

                              <button
                                type="button"
                                onClick={() => handleView(file)}
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 text-xs font-semibold border border-blue-200 transition-colors shadow-2xs cursor-pointer"
                                title="Quick View Test Cases"
                              >
                                <Eye className="h-3.5 w-3.5" />
                                <span>Quick View</span>
                              </button>

                              <button
                                type="button"
                                onClick={() => handleDownload(file)}
                                disabled={downloadingId === file.file_id}
                                className="inline-flex items-center justify-center p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors shadow-2xs disabled:opacity-60 cursor-pointer"
                                title="Export Excel (.xlsx)"
                              >
                                <Download className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ── 4. TEST CASES VIEWER MODAL (Strictly Sanitized) ────────────────── */}
      {viewingFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-6xl h-[88vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="relative px-4 py-3 sm:px-6 sm:py-4 border-b border-slate-100 flex flex-wrap items-center justify-between gap-3 bg-slate-50/70 pr-12 sm:pr-14">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="h-9 w-9 sm:h-10 sm:w-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                  <Layers className="h-4 w-4 sm:h-5 sm:w-5" />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <h3 className="text-sm sm:text-base font-bold text-slate-900 truncate">
                      {viewingFile.file_name}
                    </h3>
                    <span className="text-[10px] sm:text-[11px] font-mono font-semibold bg-blue-100 text-blue-800 px-2 py-0.5 rounded border border-blue-200">
                      {testCasesData?.test_cases?.length || 0} Tests
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 truncate">
                    {viewingFile.project_name} • DSD: {viewingFile.dsd_name}
                  </p>
                </div>
              </div>

              {/* Action Button Group (Studio & Excel) */}
              <div className="flex items-center gap-2 shrink-0">
                <Link
                  to={`/cognos?run_id=${viewingFile.run_id}&tab=scenarios`}
                  onClick={() => handleNavigateToStudio(viewingFile)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs cursor-pointer"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span className="hidden xs:inline">Open in</span> Studio
                </Link>
                <button
                  type="button"
                  onClick={() => handleDownload(viewingFile)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs cursor-pointer"
                >
                  <Download className="h-3.5 w-3.5" />
                  <span className="hidden xs:inline">Download</span> Excel
                </button>
              </div>

              {/* Independent Top-Right Close Button */}
              <button
                type="button"
                onClick={() => setViewingFile(null)}
                aria-label="Close"
                title="Close"
                className="absolute top-3 right-3 sm:top-4 sm:right-4 p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 rounded-lg transition-colors cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body: Split Explorer View */}
            {viewLoading ? (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
                <RefreshCw className="h-8 w-8 animate-spin text-blue-600 mb-3" />
                <p className="text-sm font-medium text-slate-600">Loading test cases…</p>
              </div>
            ) : (
              <div className="flex-1 flex flex-col md:flex-row min-h-0 divide-y md:divide-y-0 md:divide-x divide-slate-100">
                {/* Left: Test Case List & Search */}
                <div className="w-full md:w-80 lg:w-96 flex flex-col min-h-0 bg-slate-50/40 max-h-[260px] md:max-h-none shrink-0">
                  {/* Search and Category Filter Toolbar */}
                  <div className="p-3 border-b border-slate-100 space-y-2 bg-white">
                    <div className="relative">
                      <Search className="h-3.5 w-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="text"
                        placeholder="Search test cases..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                      />
                    </div>
                    {categories.length > 2 && (
                      <select
                        value={categoryFilter}
                        onChange={(e) => setCategoryFilter(e.target.value)}
                        className="w-full py-1 px-2 text-xs rounded-lg border border-slate-200 bg-white text-slate-700"
                      >
                        {categories.map((c) => (
                          <option key={c} value={c}>
                            {c === "ALL" ? "All Categories" : c}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  {/* Test Cases Scrollable List */}
                  <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {filteredScenarios.length === 0 ? (
                      <div className="p-6 text-center text-xs text-slate-400">
                        No test cases match your search.
                      </div>
                    ) : (
                      filteredScenarios.map((tc) => {
                        const isSelected = selectedTestCase?.id === tc.id;
                        return (
                          <button
                            key={tc.id}
                            type="button"
                            onClick={() => setSelectedTestCase(tc)}
                            className={`w-full text-left p-3 rounded-xl border transition-all text-xs flex flex-col gap-1 cursor-pointer ${
                              isSelected
                                ? "bg-blue-50/80 border-blue-200 shadow-xs"
                                : "bg-white border-slate-200/80 hover:bg-slate-50"
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-mono font-bold text-slate-900">
                                {tc.test_case_id}
                              </span>
                              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                                {tc.priority || "Medium"}
                              </span>
                            </div>
                            <div className="font-medium text-slate-800 truncate">
                              {tc.test_case_title}
                            </div>
                            <div className="text-[10px] text-slate-500 truncate">
                              {tc.category}
                            </div>
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>

                {/* Right: Selected Scenario Detail */}
                <div className="flex-1 overflow-y-auto p-6 bg-white">
                  {selectedTestCase ? (
                    <div className="space-y-5 max-w-3xl">
                      {/* Scenario Meta Banner */}
                      <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-mono font-bold text-base text-blue-700">
                              {selectedTestCase.test_case_id}
                            </span>
                            <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-200/70 text-slate-800">
                              {selectedTestCase.category}
                            </span>
                          </div>
                          <h4 className="text-base font-extrabold text-slate-900">
                            {selectedTestCase.test_case_title}
                          </h4>
                        </div>
                        <span className="px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-200">
                          {selectedTestCase.status || "Ready"}
                        </span>
                      </div>

                      {/* Objective */}
                      <div>
                        <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">
                          Test Objective
                        </h5>
                        <p className="text-xs sm:text-sm text-slate-800 leading-relaxed bg-slate-50/60 p-3 rounded-lg border border-slate-100">
                          {selectedTestCase.objective || "No objective provided."}
                        </p>
                      </div>

                      {/* Preconditions & Test Data */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">
                            Preconditions
                          </h5>
                          <div className="text-xs text-slate-700 bg-slate-50/60 p-3 rounded-lg border border-slate-100 whitespace-pre-line">
                            {selectedTestCase.preconditions || "Standard system readiness."}
                          </div>
                        </div>
                        <div>
                          <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">
                            Test Data Setup
                          </h5>
                          <div className="text-xs text-slate-700 bg-slate-50/60 p-3 rounded-lg border border-slate-100 whitespace-pre-line">
                            {selectedTestCase.test_data || "Use standard SIT test claims."}
                          </div>
                        </div>
                      </div>

                      {/* Test Execution Steps */}
                      <div>
                        <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">
                          Test Execution Steps
                        </h5>
                        <div className="text-xs sm:text-sm text-slate-800 bg-slate-50/60 p-4 rounded-xl border border-slate-100 font-mono whitespace-pre-wrap leading-relaxed">
                          {selectedTestCase.test_steps || "1. Execute test scenario."}
                        </div>
                      </div>

                      {/* Expected Result */}
                      <div>
                        <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">
                          Expected Result
                        </h5>
                        <div className="text-xs sm:text-sm text-emerald-900 bg-emerald-50/50 p-4 rounded-xl border border-emerald-200/60 leading-relaxed font-medium">
                          {selectedTestCase.expected_result || "Report outputs and fields match specifications."}
                        </div>
                      </div>

                      {/* Execution Method & Tool Metadata */}
                      <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                        <span>Execution Method: <strong className="text-slate-800 font-semibold">{selectedTestCase.execution_method || "Scheduled"}</strong></span>
                        <span>Execution Tool: <strong className="text-slate-800 font-semibold">{selectedTestCase.execution_tool || "IWA"}</strong></span>
                        <span>Priority: <strong className="text-slate-800 font-semibold">{selectedTestCase.priority || "Medium"}</strong></span>
                      </div>
                    </div>
                  ) : (
                    <div className="h-full flex items-center justify-center text-slate-400 text-xs">
                      Select a test scenario from the left to view details.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
