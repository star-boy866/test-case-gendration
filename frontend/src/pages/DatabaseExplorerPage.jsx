import { useState, useEffect, useMemo } from "react";
import {
  Database,
  Search,
  Filter,
  Download,
  Eye,
  RefreshCw,
  Layers,
  Shield,
  Activity,
  Award,
  FileText,
  Clock,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Code,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Copy,
  Check,
  Cpu,
  BarChart3,
  Server,
  Zap,
  Lock,
  GitBranch,
  History,
  Image as ImageIcon,
} from "lucide-react";
import {
  getDatabaseStatus,
  testDatabaseConnection,
  getDatabaseTables,
  getTableSchema,
  getTableRows,
  exportTableRows,
  getDatabaseActivity,
  getSourceSnapshots,
  getScenarioVersions,
  getLearningScenarios,
  getDatabaseAuditSummary,
  getScenarioLearningSummary,
} from "../services/api";

export default function DatabaseExplorerPage() {
  // Navigation tabs: "explorer" | "learning" | "evidence" | "activity"
  const [activeTab, setActiveTab] = useState("explorer");

  // Connection & Health State
  const [connectionInfo, setConnectionInfo] = useState(null);
  const [dbSummary, setDbSummary] = useState(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // Table Explorer State
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState("cognos_test_cases");
  const [tableMeta, setTableMeta] = useState(null);
  const [columns, setColumns] = useState([]);
  const [rows, setRows] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Pagination & Filtering
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sortBy, setSortBy] = useState("");
  const [sortDir, setSortDir] = useState("desc");

  // Scenario Learning State
  const [learningSummary, setLearningSummary] = useState(null);
  const [learningScenarios, setLearningScenarios] = useState([]);
  const [learningLoading, setLearningLoading] = useState(false);
  const [learningFilter, setLearningFilter] = useState({ methodology: "", status: "", search: "" });
  const [selectedScenarioVersions, setSelectedScenarioVersions] = useState(null);
  const [loadingVersions, setLoadingVersions] = useState(false);

  // Source Snapshots State
  const [snapshots, setSnapshots] = useState([]);
  const [snapshotsTotal, setSnapshotsTotal] = useState(0);
  const [snapshotsLoading, setSnapshotsLoading] = useState(false);
  const [snapshotPage, setSnapshotPage] = useState(1);
  const [selectedSnapshotImage, setSelectedSnapshotImage] = useState(null);

  // Database Activity State
  const [activity, setActivity] = useState([]);
  const [activityTotal, setActivityTotal] = useState(0);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityPage, setActivityPage] = useState(1);

  // JSON Modal Viewer
  const [modalJson, setModalJson] = useState(null);
  const [modalTitle, setModalTitle] = useState("");
  const [copied, setCopied] = useState(false);

  // Load Status & Tables on Mount
  useEffect(() => {
    loadDatabaseStatus();
    loadTables();
    loadLearningSummary();
  }, []);

  // Reload rows when table selection, pagination, or sorting changes
  useEffect(() => {
    if (selectedTable && activeTab === "explorer") {
      loadRows(selectedTable, page, pageSize, search, statusFilter, sortBy, sortDir);
    }
  }, [selectedTable, page, pageSize, statusFilter, sortBy, sortDir, activeTab]);

  // Load Tab-specific data
  useEffect(() => {
    if (activeTab === "learning") {
      loadLearningScenarios();
    } else if (activeTab === "evidence") {
      loadSnapshots(snapshotPage);
    } else if (activeTab === "activity") {
      loadActivity(activityPage);
    }
  }, [activeTab, snapshotPage, activityPage]);

  // ── Database Connection & Status ──────────────────────────────────────────
  const loadDatabaseStatus = async () => {
    setRefreshing(true);
    try {
      const res = await getDatabaseStatus();
      if (res.data) {
        setConnectionInfo(res.data.connection || {});
        setDbSummary(res.data.summary || {});
      }
    } catch (err) {
      console.error("Failed to load database status:", err);
    } finally {
      setRefreshing(false);
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setTestResult(null);
    try {
      const res = await testDatabaseConnection();
      setTestResult(res.data);
      if (res.data?.latency_ms !== undefined) {
        setConnectionInfo((prev) => ({
          ...prev,
          status: res.data.status,
          latency_ms: res.data.latency_ms,
          last_tested: res.data.last_tested || new Date().toISOString(),
        }));
      }
    } catch (err) {
      console.error("Test connection failed:", err);
      setTestResult({ status: "FAILED", error: "Connection probe timed out or was rejected." });
    } finally {
      setTestingConnection(false);
    }
  };

  // ── Tables & Data Grid ───────────────────────────────────────────────────
  const loadTables = async () => {
    try {
      const res = await getDatabaseTables();
      const list = res.data?.tables || [];
      setTables(list);
      if (list.length > 0 && !selectedTable) {
        setSelectedTable(list[0].table_name);
      }
    } catch (err) {
      console.error("Failed to load tables:", err);
    }
  };

  const loadRows = async (tableName, p, size, sTerm, sFilter, sBy, sDir) => {
    setLoading(true);
    try {
      const params = {
        page: p,
        page_size: size,
        sort_dir: sDir,
      };
      if (sTerm) params.search = sTerm;
      if (sFilter) params.status = sFilter;
      if (sBy) params.sort_by = sBy;

      const res = await getTableRows(tableName, params);
      setRows(res.data?.rows || []);
      setTotalRows(res.data?.total_rows || 0);
      setColumns(res.data?.columns || []);
      setTableMeta({
        display_name: res.data?.display_name || tableName,
      });
    } catch (err) {
      console.error("Failed to load table rows:", err);
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    loadRows(selectedTable, 1, pageSize, search, statusFilter, sortBy, sortDir);
  };

  const handleSort = (colName) => {
    if (sortBy === colName) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(colName);
      setSortDir("desc");
    }
  };

  const handleExport = async (format) => {
    setExporting(true);
    try {
      await exportTableRows(selectedTable, format);
    } catch (err) {
      console.error("Export failed:", err);
      alert("Failed to export table data.");
    } finally {
      setExporting(false);
    }
  };

  // ── Scenario Learning & Versions ─────────────────────────────────────────
  const loadLearningSummary = async () => {
    try {
      const res = await getScenarioLearningSummary();
      setLearningSummary(res.data);
    } catch (err) {
      console.error("Failed to load scenario learning summary:", err);
    }
  };

  const loadLearningScenarios = async () => {
    setLearningLoading(true);
    try {
      const params = {};
      if (learningFilter.methodology) params.methodology = learningFilter.methodology;
      if (learningFilter.status) params.review_status = learningFilter.status;
      if (learningFilter.search) params.search = learningFilter.search;

      const res = await getLearningScenarios(params);
      setLearningScenarios(res.data?.scenarios || []);
    } catch (err) {
      console.error("Failed to load learning scenarios:", err);
    } finally {
      setLearningLoading(false);
    }
  };

  const handleInspectVersions = async (testCaseId) => {
    setLoadingVersions(true);
    setSelectedScenarioVersions(null);
    try {
      const res = await getScenarioVersions(testCaseId);
      setSelectedScenarioVersions(res.data);
    } catch (err) {
      console.error("Failed to fetch scenario version history:", err);
    } finally {
      setLoadingVersions(false);
    }
  };

  // ── Source Snapshots ─────────────────────────────────────────────────────
  const loadSnapshots = async (p = 1) => {
    setSnapshotsLoading(true);
    try {
      const res = await getSourceSnapshots({ page: p, page_size: 25 });
      setSnapshots(res.data?.snapshots || []);
      setSnapshotsTotal(res.data?.total || 0);
    } catch (err) {
      console.error("Failed to load source snapshots:", err);
    } finally {
      setSnapshotsLoading(false);
    }
  };

  // ── Activity Log ─────────────────────────────────────────────────────────
  const loadActivity = async (p = 1) => {
    setActivityLoading(true);
    try {
      const res = await getDatabaseActivity({ page: p, page_size: 25 });
      setActivity(res.data?.activity || []);
      setActivityTotal(res.data?.total || 0);
    } catch (err) {
      console.error("Failed to load database activity:", err);
    } finally {
      setActivityLoading(false);
    }
  };

  // ── JSON Viewer Modal ────────────────────────────────────────────────────
  const handleOpenJsonModal = (title, data) => {
    setModalTitle(title);
    setModalJson(data);
    setCopied(false);
  };

  const handleCopyJson = () => {
    if (!modalJson) return;
    navigator.clipboard.writeText(JSON.stringify(modalJson, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Group tables by domain category
  const groupedTables = useMemo(() => {
    const groups = {};
    tables.forEach((t) => {
      const cat = t.category || "GENERAL";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(t);
    });
    return groups;
  }, [tables]);

  const totalPages = Math.ceil(totalRows / pageSize) || 1;

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#f8fafc]">

      {/* ==================================================================== */}
      {/* 1. TOP HEADER STRIP                                                  */}
      {/* ==================================================================== */}
      <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-200 bg-white px-5 py-3 shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white shadow-xs shrink-0">
            <Database className="h-5 w-5 text-blue-400" />
          </div>
          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-slate-900 tracking-tight truncate">
                Database Connection & Explorer
              </h1>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-bold text-emerald-700 tracking-wider">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                READ-ONLY
              </span>
            </div>
            <p className="text-xs text-slate-500 truncate">
              Enterprise PostgreSQL / Supabase persistence, table schemas, immutable audit, and scenario learning
            </p>
          </div>
        </div>

        {/* Workspace Tab Switcher */}
        <div className="flex items-center gap-2 w-full sm:w-auto justify-between sm:justify-end overflow-x-auto">
          <div className="flex items-center bg-slate-100 p-0.5 rounded-xl border border-slate-200 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setActiveTab("explorer")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === "explorer"
                  ? "bg-white text-slate-900 shadow-2xs font-bold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Database className="h-3.5 w-3.5 text-blue-600" />
              <span>Data Explorer</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("learning")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === "learning"
                  ? "bg-white text-slate-900 shadow-2xs font-bold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Cpu className="h-3.5 w-3.5 text-purple-600" />
              <span>Scenario Learning</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("evidence")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === "evidence"
                  ? "bg-white text-slate-900 shadow-2xs font-bold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <ImageIcon className="h-3.5 w-3.5 text-amber-600" />
              <span>Source & Evidence</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("activity")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === "activity"
                  ? "bg-white text-slate-900 shadow-2xs font-bold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <History className="h-3.5 w-3.5 text-indigo-600" />
              <span>Database Activity</span>
            </button>
          </div>

          <button
            type="button"
            onClick={() => {
              loadDatabaseStatus();
              if (activeTab === "explorer") loadRows(selectedTable, page, pageSize, search, statusFilter, sortBy, sortDir);
              if (activeTab === "learning") loadLearningScenarios();
              if (activeTab === "evidence") loadSnapshots(snapshotPage);
              if (activeTab === "activity") loadActivity(activityPage);
            }}
            disabled={refreshing || loading}
            className="flex items-center justify-center p-2 rounded-xl border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 transition-colors shadow-2xs shrink-0"
            title="Refresh database view"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing || loading ? "animate-spin text-blue-600" : ""}`} />
          </button>
        </div>
      </header>

      {/* ==================================================================== */}
      {/* 2. TOP CONNECTION & SUMMARY PANELS                                   */}
      {/* ==================================================================== */}
      <div className="border-b border-slate-200 bg-white px-5 py-3 shrink-0">

        {/* Row A: Database Connection Status Bar */}
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-700">Database Connection:</span>
              <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-bold text-[11px] ${
                connectionInfo?.status === "CONNECTED"
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : "bg-rose-50 text-rose-700 border border-rose-200"
              }`}>
                <span className={`h-2 w-2 rounded-full ${connectionInfo?.status === "CONNECTED" ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
                {connectionInfo?.status || "CHECKING..."}
              </span>
            </div>

            <div className="flex items-center gap-1.5 text-slate-600">
              <Server className="h-3.5 w-3.5 text-slate-400" />
              <span>Type:</span>
              <strong className="text-slate-800">{connectionInfo?.database_type || "PostgreSQL"}</strong>
            </div>

            <div className="flex items-center gap-1.5 text-slate-600">
              <span>Host:</span>
              <code className="font-mono text-[11px] bg-slate-100 px-1.5 py-0.5 rounded text-slate-700">
                {connectionInfo?.host_display || "aws-0-...supabase.com"}
              </code>
            </div>

            <div className="flex items-center gap-1.5 text-slate-600">
              <span>Port:</span>
              <span className="font-mono text-[11px] text-slate-800">{connectionInfo?.port || "6543"}</span>
            </div>

            <div className="flex items-center gap-1.5 text-slate-600">
              <span>Database:</span>
              <strong className="text-slate-800">{connectionInfo?.database_name || "postgres"}</strong>
            </div>

            <div className="flex items-center gap-1.5 text-slate-600">
              <span>User:</span>
              <span className="font-mono text-[11px] text-slate-800">{connectionInfo?.username || "postgres"}</span>
            </div>

            <div className="flex items-center gap-1.5 text-slate-600">
              <span>Password:</span>
              <span className="font-mono text-xs tracking-widest text-slate-400 select-none">••••••••••</span>
            </div>

            <div className="flex items-center gap-1.5 text-slate-600">
              <Zap className="h-3.5 w-3.5 text-amber-500" />
              <span>Latency:</span>
              <strong className="text-slate-800 font-mono">{connectionInfo?.latency_ms ?? "--"} ms</strong>
            </div>
          </div>

          {/* Test & Refresh Action Buttons */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={testingConnection}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors shadow-2xs"
            >
              <Zap className={`h-3.5 w-3.5 ${testingConnection ? "animate-spin text-blue-600" : "text-blue-500"}`} />
              <span>{testingConnection ? "Testing Ping..." : "Test Connection"}</span>
            </button>

            <button
              type="button"
              onClick={loadDatabaseStatus}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin text-blue-600" : "text-slate-400"}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Row B: Database Summary Stats Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 pt-2.5 text-xs">
          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-slate-400">Database Engine</span>
            <span className="font-semibold text-slate-800 truncate">{dbSummary?.database_engine || "PostgreSQL"}</span>
          </div>

          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-slate-400">Schemas</span>
            <span className="font-semibold text-slate-800 font-mono">{dbSummary?.schema_count || 1} (public)</span>
          </div>

          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-slate-400">Allowed Tables</span>
            <span className="font-semibold text-slate-800 font-mono">{dbSummary?.allowed_table_count || tables.length || 24} tables</span>
          </div>

          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-slate-400">Total Application Records</span>
            <span className="font-semibold text-blue-700 font-mono font-bold">{(dbSummary?.total_records || 0).toLocaleString()}</span>
          </div>

          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-slate-400">Recent Query Time</span>
            <span className="font-semibold text-slate-800 font-mono">{dbSummary?.recent_query_time_ms ?? "--"} ms</span>
          </div>

          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-slate-400">Latest Audit Event</span>
            <span className="font-semibold text-slate-800 truncate" title={dbSummary?.latest_audit_event?.action || "None"}>
              {dbSummary?.latest_audit_event ? `${dbSummary.latest_audit_event.action} (${dbSummary.latest_audit_event.actor_username})` : "None"}
            </span>
          </div>

          <div className="flex flex-col">
            <span className="text-[10px] uppercase font-bold text-slate-400">Latest Generation Run</span>
            <span className="font-semibold text-slate-800 truncate">
              {dbSummary?.latest_generation_run ? `Run #${dbSummary.latest_generation_run.id} (${dbSummary.latest_generation_run.status})` : "None"}
            </span>
          </div>
        </div>

        {/* Probe feedback banner if test was triggered */}
        {testResult && (
          <div className={`mt-2 p-2 rounded-lg text-xs flex items-center justify-between border ${
            testResult.status === "CONNECTED"
              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
              : "bg-rose-50 text-rose-800 border-rose-200"
          }`}>
            <div className="flex items-center gap-2">
              {testResult.status === "CONNECTED" ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0" />
              )}
              <span>
                <strong>Probe {testResult.status}:</strong> Roundtrip latency: {testResult.latency_ms} ms. Server: {testResult.database_type} {testResult.server_version_major ? `(v${testResult.server_version_major})` : ""}. Handshake verified.
              </span>
            </div>
            <button
              type="button"
              onClick={() => setTestResult(null)}
              className="text-slate-400 hover:text-slate-700 font-bold px-1"
            >
              ✕
            </button>
          </div>
        )}

      </div>

      {/* ==================================================================== */}
      {/* 3. MAIN WORKSPACE AREA                                               */}
      {/* ==================================================================== */}
      <div className="flex-1 overflow-hidden min-h-0 flex">

        {/* ── TAB 1: DATA EXPLORER ─────────────────────────────────────────── */}
        {activeTab === "explorer" && (
          <div className="flex flex-1 overflow-hidden">

            {/* Left Sidebar: Allowed Table Directory */}
            <aside className="w-64 border-r border-slate-200 bg-white flex flex-col shrink-0 overflow-y-auto">
              <div className="p-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Allowed Tables ({tables.length})
                </span>
                <span className="text-[10px] text-slate-400 font-mono">public</span>
              </div>
              <div className="flex-1 p-2 space-y-4">
                {Object.entries(groupedTables).map(([category, catTables]) => (
                  <div key={category} className="space-y-1">
                    <div className="px-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      {category}
                    </div>
                    {catTables.map((t) => (
                      <button
                        key={t.table_name}
                        type="button"
                        onClick={() => {
                          setSelectedTable(t.table_name);
                          setPage(1);
                          setSearch("");
                          setStatusFilter("");
                          setSortBy("");
                        }}
                        className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                          selectedTable === t.table_name
                            ? "bg-blue-50 text-blue-700 font-bold border border-blue-200/80 shadow-2xs"
                            : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Layers className="h-3.5 w-3.5 shrink-0 opacity-70" />
                          <span className="truncate">{t.display_name}</span>
                        </div>
                        <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full font-bold ${
                          selectedTable === t.table_name ? "bg-blue-200/80 text-blue-900" : "bg-slate-100 text-slate-500"
                        }`}>
                          {t.row_count}
                        </span>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            </aside>

            {/* Center/Right: Table Data Grid & Controls */}
            <main className="flex-1 flex flex-col overflow-hidden min-w-0 bg-[#f8fafc]">

              {/* Filter & Action Toolbar */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 p-3.5 bg-white border-b border-slate-200 shrink-0">
                <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 flex-1 max-w-md">
                  <div className="relative flex-1">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                    <input
                      type="text"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder={`Search ${selectedTable} columns...`}
                      className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white text-slate-900"
                    />
                  </div>
                  <button
                    type="submit"
                    className="px-3 py-1.5 text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors"
                  >
                    Search
                  </button>
                </form>

                <div className="flex items-center gap-2">
                  {/* Export Options */}
                  <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
                    <button
                      type="button"
                      onClick={() => handleExport("csv")}
                      disabled={exporting || rows.length === 0}
                      className="flex items-center gap-1 px-2.5 py-1 text-slate-700 hover:bg-white hover:shadow-2xs rounded-md transition-colors"
                      title="Export table as CSV"
                    >
                      <Download className="h-3 w-3" />
                      <span>CSV</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleExport("json")}
                      disabled={exporting || rows.length === 0}
                      className="flex items-center gap-1 px-2.5 py-1 text-slate-700 hover:bg-white hover:shadow-2xs rounded-md transition-colors"
                      title="Export table as JSON"
                    >
                      <Code className="h-3 w-3" />
                      <span>JSON</span>
                    </button>
                  </div>

                  {/* Page Size */}
                  <select
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value));
                      setPage(1);
                    }}
                    className="text-xs bg-white border border-slate-200 rounded-lg px-2 py-1.5 text-slate-700 focus:outline-none"
                  >
                    <option value="10">10 / page</option>
                    <option value="25">25 / page</option>
                    <option value="50">50 / page</option>
                    <option value="100">100 / page</option>
                  </select>
                </div>
              </div>

              {/* Data Table */}
              <div className="flex-1 overflow-auto min-h-0">
                {loading ? (
                  <div className="flex h-full items-center justify-center text-slate-400 text-xs">
                    <RefreshCw className="h-5 w-5 animate-spin mr-2 text-blue-600" />
                    Loading records from database...
                  </div>
                ) : rows.length === 0 ? (
                  <div className="flex flex-col h-full items-center justify-center text-slate-400 text-xs p-8 text-center">
                    <Database className="h-8 w-8 mb-2 opacity-40 text-slate-500" />
                    <span className="font-semibold text-slate-600">No records found</span>
                    <span className="text-slate-400 mt-0.5">Table '{selectedTable}' is currently empty or query filters matched 0 rows.</span>
                  </div>
                ) : (
                  <table className="w-full text-left text-xs border-collapse">
                    <thead className="sticky top-0 z-10 bg-slate-50 border-b border-slate-200 text-slate-600">
                      <tr>
                        {columns.map((col) => (
                          <th
                            key={col.name}
                            onClick={() => handleSort(col.name)}
                            className="px-3.5 py-2.5 font-bold uppercase tracking-wider text-[10px] text-slate-500 cursor-pointer hover:bg-slate-100/80 transition-colors whitespace-nowrap"
                          >
                            <div className="flex items-center gap-1">
                              <span>{col.name}</span>
                              <ArrowUpDown className="h-3 w-3 opacity-40" />
                            </div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white text-slate-700">
                      {rows.map((row, idx) => (
                        <tr key={row.id || idx} className="hover:bg-blue-50/40 transition-colors">
                          {columns.map((col) => {
                            const val = row[col.name];
                            const isJson = val !== null && typeof val === "object";
                            return (
                              <td
                                key={col.name}
                                className="px-3.5 py-2 whitespace-nowrap max-w-[240px] truncate text-slate-800 font-mono text-[11px]"
                              >
                                {isJson ? (
                                  <button
                                    type="button"
                                    onClick={() => handleOpenJsonModal(`${selectedTable}.${col.name} (Row #${row.id || idx + 1})`, val)}
                                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-100 text-blue-700 hover:bg-blue-100 transition-colors font-sans text-[10px] font-bold"
                                  >
                                    <Code className="h-3 w-3" />
                                    <span>View JSON</span>
                                  </button>
                                ) : val === null || val === undefined ? (
                                  <span className="text-slate-300 italic font-sans">NULL</span>
                                ) : typeof val === "boolean" ? (
                                  <span className={`font-bold font-sans ${val ? "text-emerald-600" : "text-slate-400"}`}>
                                    {val ? "TRUE" : "FALSE"}
                                  </span>
                                ) : (
                                  <span title={String(val)}>{String(val)}</span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Pagination Footer */}
              <div className="flex items-center justify-between px-4 py-2.5 bg-white border-t border-slate-200 text-xs text-slate-600 shrink-0">
                <span className="text-slate-500">
                  Showing <strong className="text-slate-800">{rows.length}</strong> of{" "}
                  <strong className="text-slate-800">{totalRows}</strong> rows
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="p-1 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:pointer-events-none"
                    title="Previous page"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <span className="px-2 font-medium">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    className="p-1 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:pointer-events-none"
                    title="Next page"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>

            </main>
          </div>
        )}

        {/* ── TAB 2: SCENARIO LEARNING VIEW ────────────────────────────────── */}
        {activeTab === "learning" && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">

            {/* Governance Policy Notice */}
            <div className="rounded-2xl border border-purple-200 bg-purple-50/50 p-4.5 flex items-start gap-3.5">
              <div className="p-2 bg-purple-600 text-white rounded-xl shadow-xs shrink-0">
                <Cpu className="h-5 w-5" />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="font-bold text-sm text-purple-950">
                  Scenario Evaluation & Learning Governance
                </span>
                <p className="text-xs text-purple-900/80 mt-0.5">
                  {learningSummary?.governance_rule || "Only scenarios verified and approved by SIT/QA testers qualify as learning candidates. No unverified output is fed into model evaluation datasets."}
                </p>
              </div>
            </div>

            {/* Status Breakdown Metric Cards */}
            <div className="grid grid-cols-2 md:grid-cols-6 gap-3.5">
              <div className="rounded-2xl bg-white border border-slate-200 p-4 shadow-2xs">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">AI Generated</span>
                <div className="text-2xl font-bold text-slate-900 mt-1 font-mono">
                  {learningSummary?.status_distribution?.ai_generated || 0}
                </div>
                <span className="text-[10px] text-slate-500">Baseline models</span>
              </div>
              <div className="rounded-2xl bg-white border border-amber-200 bg-amber-50/20 p-4 shadow-2xs">
                <span className="text-[11px] font-bold uppercase tracking-wider text-amber-700">Tester Corrected</span>
                <div className="text-2xl font-bold text-amber-900 mt-1 font-mono">
                  {learningSummary?.status_distribution?.tester_corrected || 0}
                </div>
                <span className="text-[10px] text-amber-600">Human revisions</span>
              </div>
              <div className="rounded-2xl bg-white border border-emerald-200 bg-emerald-50/20 p-4 shadow-2xs">
                <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700">Approved</span>
                <div className="text-2xl font-bold text-emerald-900 mt-1 font-mono">
                  {learningSummary?.status_distribution?.approved || 0}
                </div>
                <span className="text-[10px] text-emerald-600">Locked specifications</span>
              </div>
              <div className="rounded-2xl bg-white border border-rose-200 bg-rose-50/20 p-4 shadow-2xs">
                <span className="text-[11px] font-bold uppercase tracking-wider text-rose-700">Rejected</span>
                <div className="text-2xl font-bold text-rose-900 mt-1 font-mono">
                  {learningSummary?.status_distribution?.rejected || 0}
                </div>
                <span className="text-[10px] text-rose-600">Flagged non-compliant</span>
              </div>
              <div className="rounded-2xl bg-white border border-blue-200 bg-blue-50/20 p-4 shadow-2xs">
                <span className="text-[11px] font-bold uppercase tracking-wider text-blue-700">Regenerated</span>
                <div className="text-2xl font-bold text-blue-900 mt-1 font-mono">
                  {learningSummary?.status_distribution?.regenerated || 0}
                </div>
                <span className="text-[10px] text-blue-600">Iterated pipeline</span>
              </div>
              <div className="rounded-2xl bg-white border border-purple-200 bg-purple-50/20 p-4 shadow-2xs">
                <span className="text-[11px] font-bold uppercase tracking-wider text-purple-700">Learning Candidates</span>
                <div className="text-2xl font-bold text-purple-900 mt-1 font-mono">
                  {learningSummary?.learning_candidates_count || 0}
                </div>
                <span className="text-[10px] text-purple-600">Evaluation qualified</span>
              </div>
            </div>

            {/* Filterable Scenarios Table */}
            <div className="rounded-2xl bg-white border border-slate-200 shadow-2xs overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-100 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                    Governed Scenarios & Version Provenance
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Click any test case ID to inspect immutable version evolution and human correction logs
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={learningFilter.search}
                    onChange={(e) => setLearningFilter((prev) => ({ ...prev, search: e.target.value }))}
                    onKeyDown={(e) => { if (e.key === "Enter") loadLearningScenarios(); }}
                    placeholder="Search test case ID or title..."
                    className="px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-800"
                  />
                  <select
                    value={learningFilter.status}
                    onChange={(e) => {
                      setLearningFilter((prev) => ({ ...prev, status: e.target.value }));
                      loadLearningScenarios();
                    }}
                    className="px-2 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-800"
                  >
                    <option value="">All Review Statuses</option>
                    <option value="APPROVED">APPROVED</option>
                    <option value="CORRECTED">CORRECTED</option>
                    <option value="GENERATED">GENERATED</option>
                    <option value="REJECTED">REJECTED</option>
                  </select>
                </div>
              </div>

              <div className="divide-y divide-slate-100">
                {learningLoading ? (
                  <div className="p-8 text-center text-xs text-slate-400">Loading learning scenarios...</div>
                ) : learningScenarios.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-400">No scenarios found matching filter.</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 text-slate-500 font-bold uppercase text-[10px]">
                        <tr>
                          <th className="px-4 py-2.5">Test Case ID</th>
                          <th className="px-4 py-2.5">Scenario Name</th>
                          <th className="px-4 py-2.5">Methodology</th>
                          <th className="px-4 py-2.5">Status</th>
                          <th className="px-4 py-2.5">Versions</th>
                          <th className="px-4 py-2.5">Learning Candidate</th>
                          <th className="px-4 py-2.5">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-slate-700">
                        {learningScenarios.map((s) => (
                          <tr key={s.id} className="hover:bg-slate-50/50">
                            <td className="px-4 py-2 font-mono font-bold text-blue-700">{s.test_case_id}</td>
                            <td className="px-4 py-2 max-w-[280px] truncate" title={s.scenario_name}>{s.scenario_name}</td>
                            <td className="px-4 py-2">{s.methodology || "General"}</td>
                            <td className="px-4 py-2">
                              <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                s.review_status === "APPROVED"
                                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                  : s.review_status === "CORRECTED"
                                  ? "bg-amber-50 text-amber-700 border border-amber-200"
                                  : "bg-slate-100 text-slate-700"
                              }`}>
                                {s.review_status}
                              </span>
                            </td>
                            <td className="px-4 py-2 font-mono">{s.version_count}</td>
                            <td className="px-4 py-2">
                              {s.is_learning_candidate ? (
                                <span className="text-purple-700 font-bold flex items-center gap-1 text-[11px]">
                                  <Check className="h-3.5 w-3.5" /> Qualified
                                </span>
                              ) : (
                                <span className="text-slate-400 text-[11px]">Pending Review</span>
                              )}
                            </td>
                            <td className="px-4 py-2">
                              <button
                                type="button"
                                onClick={() => handleInspectVersions(s.test_case_id)}
                                className="flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800"
                              >
                                <History className="h-3 w-3" />
                                <span>Version History</span>
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>

            {/* Methodology Corrections Frequency Bar */}
            <div className="rounded-2xl bg-white border border-slate-200 shadow-2xs overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-100">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                  Most Frequently Corrected Methodologies
                </h3>
                <p className="text-[11px] text-slate-500">
                  Pinpoints extraction patterns requiring prompt or schema adjustments
                </p>
              </div>
              <div className="p-4 space-y-3">
                {(learningSummary?.methodology_corrections || []).map((m) => (
                  <div key={m.methodology} className="flex items-center justify-between gap-4 text-xs">
                    <span className="font-semibold text-slate-800 min-w-[200px] truncate">{m.methodology}</span>
                    <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-amber-500 h-full rounded-full"
                        style={{ width: `${Math.min(100, (m.corrected_count / 10) * 100)}%` }}
                      />
                    </div>
                    <span className="font-bold font-mono text-slate-700 shrink-0">{m.corrected_count} corrections</span>
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}

        {/* ── TAB 3: SOURCE & EVIDENCE INSPECTION ──────────────────────────── */}
        {activeTab === "evidence" && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Source Document & Evidence Snapshot Provenance</h2>
                <p className="text-xs text-slate-500">Inspect exact crops, physical PDF page numbers, and semantic coordinates</p>
              </div>
              <span className="text-xs font-mono font-bold text-slate-600">{snapshotsTotal} snapshots recorded</span>
            </div>

            <div className="rounded-2xl bg-white border border-slate-200 shadow-2xs overflow-hidden">
              {snapshotsLoading ? (
                <div className="p-8 text-center text-xs text-slate-400">Loading evidence snapshots...</div>
              ) : snapshots.length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-400">No source snapshots recorded yet.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 font-bold uppercase text-[10px]">
                      <tr>
                        <th className="px-4 py-2.5">Evidence ID</th>
                        <th className="px-4 py-2.5">Scenario / Run</th>
                        <th className="px-4 py-2.5">Document</th>
                        <th className="px-4 py-2.5">Page</th>
                        <th className="px-4 py-2.5">Semantic Target</th>
                        <th className="px-4 py-2.5">Crop Box</th>
                        <th className="px-4 py-2.5">Renderer & Version</th>
                        <th className="px-4 py-2.5">Preview</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-700">
                      {snapshots.map((s) => (
                        <tr key={s.id} className="hover:bg-slate-50/50">
                          <td className="px-4 py-2 font-mono font-bold text-blue-700">{s.evidence_id}</td>
                          <td className="px-4 py-2">
                            <div className="font-mono text-[11px]">{s.scenario}</div>
                            <span className="text-[10px] text-slate-400">Run #{s.run_id}</span>
                          </td>
                          <td className="px-4 py-2 max-w-[200px] truncate" title={s.document}>{s.document}</td>
                          <td className="px-4 py-2 font-mono">{s.page ? `Page ${s.page}` : "--"}</td>
                          <td className="px-4 py-2 max-w-[180px] truncate" title={s.semantic_target || ""}>{s.semantic_target || "--"}</td>
                          <td className="px-4 py-2 font-mono text-[10px] max-w-[160px] truncate">
                            {s.crop_box ? JSON.stringify(s.crop_box) : "--"}
                          </td>
                          <td className="px-4 py-2 font-mono text-[10px]">
                            <div>{s.renderer || "--"}</div>
                            <div className="text-slate-400">{s.crop_version || ""}</div>
                          </td>
                          <td className="px-4 py-2">
                            {s.preview_url ? (
                              <button
                                type="button"
                                onClick={() => setSelectedSnapshotImage({ url: s.preview_url, title: `${s.evidence_id} (${s.scenario})` })}
                                className="flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800"
                              >
                                <Eye className="h-3 w-3" />
                                <span>Preview</span>
                              </button>
                            ) : (
                              <span className="text-slate-300">N/A</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── TAB 4: DATABASE ACTIVITY LOG ─────────────────────────────────── */}
        {activeTab === "activity" && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Database Activity & Audit Trail</h2>
                <p className="text-xs text-slate-500">Immutable ledger tracking table views, connection tests, and CSV exports</p>
              </div>
              <span className="text-xs font-mono font-bold text-slate-600">{activityTotal} audit records</span>
            </div>

            <div className="rounded-2xl bg-white border border-slate-200 shadow-2xs overflow-hidden">
              {activityLoading ? (
                <div className="p-8 text-center text-xs text-slate-400">Loading database activity log...</div>
              ) : activity.length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-400">No database activity events recorded yet.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 font-bold uppercase text-[10px]">
                      <tr>
                        <th className="px-4 py-2.5">Timestamp</th>
                        <th className="px-4 py-2.5">Admin User</th>
                        <th className="px-4 py-2.5">Action</th>
                        <th className="px-4 py-2.5">Target Table</th>
                        <th className="px-4 py-2.5">Filter Summary</th>
                        <th className="px-4 py-2.5">Rows Returned</th>
                        <th className="px-4 py-2.5">Result</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-700">
                      {activity.map((a) => (
                        <tr key={a.id} className="hover:bg-slate-50/50">
                          <td className="px-4 py-2 font-mono text-[11px] text-slate-500">
                            {a.timestamp ? new Date(a.timestamp).toLocaleString() : "--"}
                          </td>
                          <td className="px-4 py-2 font-medium text-slate-900">
                            {a.admin} <span className="text-slate-400 text-[10px]">({a.role})</span>
                          </td>
                          <td className="px-4 py-2">
                            <span className={`inline-flex rounded-md px-2 py-0.5 text-[10px] font-bold font-mono ${
                              a.action.includes("TABLE_VIEW")
                                ? "bg-slate-100 text-slate-700"
                                : a.action.includes("CONNECTION_TEST")
                                ? "bg-amber-100 text-amber-800"
                                : a.action.includes("EXPORT")
                                ? "bg-blue-100 text-blue-800"
                                : "bg-indigo-100 text-indigo-800"
                            }`}>
                              {a.action}
                            </span>
                          </td>
                          <td className="px-4 py-2 font-mono font-bold text-slate-800">{a.table}</td>
                          <td className="px-4 py-2 font-mono text-[10px] text-slate-500 max-w-[200px] truncate" title={a.filter}>
                            {a.filter}
                          </td>
                          <td className="px-4 py-2 font-mono">{a.rows_returned}</td>
                          <td className="px-4 py-2">
                            <span className={`font-bold text-[10px] ${a.result === "SUCCESS" ? "text-emerald-600" : "text-rose-600"}`}>
                              {a.result}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

      </div>

      {/* ==================================================================== */}
      {/* 4. MODALS (JSON, VERSIONS, IMAGE PREVIEWS)                            */}
      {/* ==================================================================== */}

      {/* A. JSON Inspection Modal */}
      {modalJson && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-2xl bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 bg-slate-50">
              <div className="flex items-center gap-2 min-w-0">
                <Code className="h-4 w-4 text-blue-600 shrink-0" />
                <span className="font-bold text-xs text-slate-900 truncate">{modalTitle}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={handleCopyJson}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-white border border-slate-200 rounded-lg text-slate-700 hover:bg-slate-100 transition-colors shadow-2xs"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                  <span>{copied ? "Copied" : "Copy JSON"}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setModalJson(null)}
                  className="text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100 transition-colors"
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4 bg-slate-900 text-emerald-400 font-mono text-xs leading-relaxed">
              <pre>{JSON.stringify(modalJson, null, 2)}</pre>
            </div>
          </div>
        </div>
      )}

      {/* B. Scenario Version History Modal */}
      {selectedScenarioVersions && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-3xl bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 bg-slate-50">
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-purple-600" />
                <span className="font-bold text-xs text-slate-900">
                  Version History: {selectedScenarioVersions.test_case_id}
                </span>
                <span className="rounded-full bg-purple-100 text-purple-800 text-[10px] font-bold px-2 py-0.5">
                  {selectedScenarioVersions.total_versions} version{selectedScenarioVersions.total_versions === 1 ? "" : "s"}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedScenarioVersions(null)}
                className="text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {selectedScenarioVersions.versions.map((ver) => (
                <div key={ver.version_number} className="rounded-xl border border-slate-200 p-4 space-y-2 bg-white shadow-2xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs text-slate-900">Version {ver.version_number}</span>
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-mono font-bold text-slate-700">
                        {ver.source}
                      </span>
                    </div>
                    <span className="text-[11px] text-slate-400 font-mono">
                      {ver.timestamp ? new Date(ver.timestamp).toLocaleString() : ""}
                    </span>
                  </div>
                  <div className="text-xs text-slate-600">
                    <strong>Actor:</strong> {ver.actor} • <strong>Reason:</strong> {ver.change_reason}
                  </div>
                  {ver.diff && (
                    <div className="mt-2 rounded bg-slate-50 p-2 text-[11px] font-mono border border-slate-100">
                      <strong className="text-slate-500 font-sans">Content Difference:</strong>
                      <pre className="mt-1 text-slate-800 overflow-x-auto">{JSON.stringify(ver.diff, null, 2)}</pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* C. Source Snapshot Image Preview Modal */}
      {selectedSnapshotImage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-4xl bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 bg-slate-50">
              <span className="font-bold text-xs text-slate-900 truncate">
                Snapshot Preview: {selectedSnapshotImage.title}
              </span>
              <button
                type="button"
                onClick={() => setSelectedSnapshotImage(null)}
                className="text-slate-400 hover:text-slate-700 p-1 rounded-lg hover:bg-slate-100"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-slate-100">
              <img
                src={selectedSnapshotImage.url}
                alt="Source Snapshot Preview"
                className="max-h-full max-w-full object-contain rounded border border-slate-300 shadow-sm"
              />
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
