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
  BarChart3
} from "lucide-react";
import {
  getDatabaseTables,
  getTableSchema,
  getTableRows,
  exportTableRows,
  getDatabaseAuditSummary,
  getScenarioLearningSummary,
} from "../services/api";

export default function DatabaseExplorerPage() {
  const [activeTab, setActiveTab] = useState("explorer"); // "explorer" | "learning" | "overview"
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState("cognos_test_cases");
  const [tableMeta, setTableMeta] = useState(null);
  const [columns, setColumns] = useState([]);
  const [rows, setRows] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Pagination & Filters
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sortBy, setSortBy] = useState("");
  const [sortDir, setSortDir] = useState("desc");

  // Overview & Learning Summaries
  const [auditSummary, setAuditSummary] = useState(null);
  const [learningSummary, setLearningSummary] = useState(null);

  // JSON Modal Viewer
  const [modalJson, setModalJson] = useState(null);
  const [modalTitle, setModalTitle] = useState("");
  const [copied, setCopied] = useState(false);

  // Load Table List & Metrics on mount
  useEffect(() => {
    loadTables();
    loadSummaries();
  }, []);

  // Reload rows when table, pagination, or filters change
  useEffect(() => {
    if (selectedTable) {
      loadRows(selectedTable, page, pageSize, search, statusFilter, sortBy, sortDir);
    }
  }, [selectedTable, page, pageSize, statusFilter, sortBy, sortDir]);

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

  const loadSummaries = async () => {
    try {
      const [sumRes, learnRes] = await Promise.all([
        getDatabaseAuditSummary(),
        getScenarioLearningSummary(),
      ]);
      setAuditSummary(sumRes.data);
      setLearningSummary(learnRes.data);
    } catch (err) {
      console.error("Failed to load database summaries:", err);
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
      
      {/* Top Header Strip */}
      <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-200 bg-white px-5 py-3.5 shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white shadow-xs shrink-0">
            <Database className="h-5 w-5 text-blue-400" />
          </div>
          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-slate-900 tracking-tight truncate">
                Database Explorer & Governance
              </h1>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-bold text-emerald-700 tracking-wider">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                READ-ONLY
              </span>
            </div>
            <p className="text-xs text-slate-500 truncate">
              Authoritative Supabase PostgreSQL persistence, audit ledger, and scenario learning
            </p>
          </div>
        </div>

        {/* Tab Switcher & Quick Refresh */}
        <div className="flex items-center gap-2 w-full sm:w-auto justify-between sm:justify-end">
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
              onClick={() => setActiveTab("overview")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
                activeTab === "overview"
                  ? "bg-white text-slate-900 shadow-2xs font-bold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <BarChart3 className="h-3.5 w-3.5 text-indigo-600" />
              <span>Overview Metrics</span>
            </button>
          </div>

          <button
            type="button"
            onClick={() => {
              loadSummaries();
              loadRows(selectedTable, page, pageSize, search, statusFilter, sortBy, sortDir);
            }}
            disabled={loading}
            className="flex items-center justify-center p-2 rounded-xl border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 transition-colors shadow-2xs shrink-0"
            title="Refresh current view"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin text-blue-600" : ""}`} />
          </button>
        </div>
      </header>

      {/* Main View Area */}
      <div className="flex-1 overflow-hidden min-h-0 flex">
        
        {/* ==================================================================== */}
        {/* TAB 1: DATA EXPLORER                                                 */}
        {/* ==================================================================== */}
        {activeTab === "explorer" && (
          <div className="flex flex-1 overflow-hidden">
            
            {/* Left Sidebar: Allowed Table Directory */}
            <aside className="w-64 border-r border-slate-200 bg-white flex flex-col shrink-0 overflow-y-auto">
              <div className="p-3 border-b border-slate-100">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Allowed Tables ({tables.length})
                </span>
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

            {/* Right Pane: Table Data Grid & Controls */}
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
                      placeholder={`Search ${selectedTable}...`}
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

        {/* ==================================================================== */}
        {/* TAB 2: SCENARIO LEARNING & ANALYTICS                                 */}
        {/* ==================================================================== */}
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
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
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
              <div className="rounded-2xl bg-white border border-purple-200 bg-purple-50/20 p-4 shadow-2xs">
                <span className="text-[11px] font-bold uppercase tracking-wider text-purple-700">Learning Candidates</span>
                <div className="text-2xl font-bold text-purple-900 mt-1 font-mono">
                  {learningSummary?.learning_candidates_count || 0}
                </div>
                <span className="text-[10px] text-purple-600">Evaluation qualified</span>
              </div>
            </div>

            {/* Methodology Corrections Table */}
            <div className="rounded-2xl bg-white border border-slate-200 shadow-2xs overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                    Most Frequently Corrected Methodologies
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Pinpoints extraction patterns requiring rule refinement or prompt adjustments
                  </p>
                </div>
              </div>
              <div className="p-4">
                {learningSummary?.methodology_corrections?.length === 0 ? (
                  <div className="py-6 text-center text-xs text-slate-400">
                    No methodology corrections recorded yet.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {learningSummary?.methodology_corrections?.map((m) => (
                      <div key={m.methodology} className="flex items-center justify-between gap-4">
                        <span className="text-xs font-semibold text-slate-800 min-w-[200px] truncate">
                          {m.methodology}
                        </span>
                        <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
                          <div
                            className="bg-amber-500 h-full rounded-full"
                            style={{
                              width: `${Math.min(100, (m.corrected_count / 10) * 100)}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs font-bold font-mono text-slate-700 shrink-0">
                          {m.corrected_count} correction{m.corrected_count === 1 ? "" : "s"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

          </div>
        )}

        {/* ==================================================================== */}
        {/* TAB 3: OVERVIEW METRICS                                              */}
        {/* ==================================================================== */}
        {activeTab === "overview" && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            
            {/* Overview Metric Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
              <div className="rounded-2xl bg-white border border-slate-200 p-4 shadow-2xs">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total Users</span>
                <div className="text-2xl font-bold text-slate-900 mt-1 font-mono">
                  {auditSummary?.summary?.total_users || 0}
                </div>
                <span className="text-[10px] text-slate-500">
                  {auditSummary?.summary?.active_users || 0} active
                </span>
              </div>
              <div className="rounded-2xl bg-white border border-slate-200 p-4 shadow-2xs">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Generation Runs</span>
                <div className="text-2xl font-bold text-slate-900 mt-1 font-mono">
                  {auditSummary?.summary?.total_runs || 0}
                </div>
                <span className="text-[10px] text-slate-500">Pipeline executions</span>
              </div>
              <div className="rounded-2xl bg-white border border-slate-200 p-4 shadow-2xs">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Test Scenarios</span>
                <div className="text-2xl font-bold text-slate-900 mt-1 font-mono">
                  {auditSummary?.summary?.total_scenarios || 0}
                </div>
                <span className="text-[10px] text-slate-500">Generated unit tests</span>
              </div>
              <div className="rounded-2xl bg-white border border-slate-200 p-4 shadow-2xs">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Scenario Versions</span>
                <div className="text-2xl font-bold text-slate-900 mt-1 font-mono">
                  {auditSummary?.summary?.total_versions || 0}
                </div>
                <span className="text-[10px] text-slate-500">Audit snapshots</span>
              </div>
              <div className="rounded-2xl bg-white border border-slate-200 p-4 shadow-2xs">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Audit Events</span>
                <div className="text-2xl font-bold text-slate-900 mt-1 font-mono">
                  {auditSummary?.summary?.total_audit_events || 0}
                </div>
                <span className="text-[10px] text-slate-500">Logged actions</span>
              </div>
            </div>

            {/* Recent Admin Actions Feed */}
            <div className="rounded-2xl bg-white border border-slate-200 shadow-2xs overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                  Recent Governance & Admin Actions
                </h3>
              </div>
              <div className="divide-y divide-slate-100">
                {(auditSummary?.recent_admin_actions || []).length === 0 ? (
                  <div className="py-6 text-center text-xs text-slate-400">
                    No recent administrative actions recorded.
                  </div>
                ) : (
                  auditSummary?.recent_admin_actions?.map((ev) => (
                    <div key={ev.id} className="flex items-center justify-between px-5 py-3 text-xs">
                      <div className="flex items-center gap-3">
                        <span className={`inline-flex rounded-md px-2 py-0.5 text-[10px] font-bold font-mono ${
                          ev.action.includes("VIEW")
                            ? "bg-slate-100 text-slate-700"
                            : ev.action.includes("EXPORT")
                            ? "bg-blue-100 text-blue-800"
                            : ev.action.includes("APPROV")
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-indigo-100 text-indigo-800"
                        }`}>
                          {ev.action}
                        </span>
                        <span className="text-slate-800 font-medium">
                          {ev.actor_username} ({ev.actor_role})
                        </span>
                        {ev.resource_id && (
                          <span className="text-slate-400 font-mono text-[11px]">
                            • {ev.resource_type}: {ev.resource_id}
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-slate-400 font-mono">
                        {ev.occurred_at ? new Date(ev.occurred_at).toLocaleString() : ""}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

          </div>
        )}

      </div>

      {/* JSON Inspection Modal */}
      {modalJson && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-2xl bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 bg-slate-50">
              <div className="flex items-center gap-2 min-w-0">
                <Code className="h-4 w-4 text-blue-600 shrink-0" />
                <span className="font-bold text-xs text-slate-900 truncate">
                  {modalTitle}
                </span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={handleCopyJson}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-white border border-slate-200 rounded-lg text-slate-700 hover:bg-slate-100 transition-colors shadow-2xs"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                  <span>{copied ? "Copied" : "Copy"}</span>
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

    </div>
  );
}
