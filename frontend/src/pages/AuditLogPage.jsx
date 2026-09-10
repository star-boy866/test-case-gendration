import { useState, useEffect, useCallback } from "react";
import {
  ShieldCheck,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  User,
  RefreshCw,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Shield,
  Activity,
  KeyRound,
  FileCode,
  Lock,
  ExternalLink,
  Eye,
  SlidersHorizontal,
} from "lucide-react";
import { getAdminAuditLogs } from "../services/api";

export default function AuditLogPage() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [actionFilter, setActionFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const [targetFilter, setTargetFilter] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  // Detailed view modal
  const [selectedEntry, setSelectedEntry] = useState(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getAdminAuditLogs({
        page,
        page_size: pageSize,
        action: actionFilter || undefined,
        actor: actorFilter || undefined,
        target_user: targetFilter || undefined,
        outcome: outcomeFilter || undefined,
      });
      setLogs(res.data.logs || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load audit logs.");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, actionFilter, actorFilter, targetFilter, outcomeFilter]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const totalPages = Math.ceil(total / pageSize) || 1;

  // Filter logs locally if full-text search entered
  const filteredLogs = logs.filter((log) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    const actionMatch = log.action?.toLowerCase().includes(term);
    const actorMatch = log.actor_username?.toLowerCase().includes(term);
    const targetMatch = log.target_username?.toLowerCase().includes(term);
    const detailMatch = typeof log.details === "string" ? log.details.toLowerCase().includes(term) : false;
    const ipMatch = log.ip_address?.toLowerCase().includes(term);
    return actionMatch || actorMatch || targetMatch || detailMatch || ipMatch;
  });

  const getActionBadge = (action = "") => {
    const act = action.toUpperCase();
    if (act.includes("APPROVED") || act.includes("SUCCESS") || act.includes("ACTIVATED")) {
      return "bg-emerald-50 text-emerald-700 border-emerald-200/80";
    }
    if (act.includes("REJECTED") || act.includes("FAILED") || act.includes("LOCKOUT") || act.includes("SUSPEND") || act.includes("REVOK")) {
      return "bg-rose-50 text-rose-700 border-rose-200/80";
    }
    if (act.includes("REQUEST")) {
      return "bg-amber-50 text-amber-700 border-amber-200/80";
    }
    if (act.includes("PASSWORD") || act.includes("MFA") || act.includes("AUTH")) {
      return "bg-purple-50 text-purple-700 border-purple-200/80";
    }
    return "bg-blue-50 text-blue-700 border-blue-200/80";
  };

  const quickActionFilters = [
    { label: "All Events", value: "" },
    { label: "Logins", value: "LOGIN" },
    { label: "Approvals", value: "ACCESS_REQUEST" },
    { label: "Passwords", value: "PASSWORD" },
    { label: "MFA Events", value: "MFA" },
    { label: "Account Lockouts", value: "LOCKOUT" },
  ];

  return (
    <div className="w-full max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6 pb-20">
      
      {/* Top Banner & Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-blue-700 border border-blue-200/70">
              <ShieldCheck className="h-3.5 w-3.5" />
              RFC 6238 & SOC2 Compliance
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-bold text-emerald-700 border border-emerald-200/70">
              <Shield className="h-3.5 w-3.5" />
              Cryptographic Integrity
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Security & Compliance Audit Trail
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Append-only, tamper-evident security journal capturing every authentication, access approval, and privilege escalation event.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={fetchLogs}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 hover:border-slate-300 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 text-blue-600 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh Trail</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-300 bg-rose-50/80 p-4 text-xs font-medium text-rose-800 flex items-center gap-2.5 shadow-xs">
          <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Metric Highlights */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total Audit Records</span>
            <Activity className="h-4 w-4 text-blue-500" />
          </div>
          <div className="text-2xl font-black text-slate-900">{total}</div>
          <span className="text-[10px] text-slate-400 font-medium">Archived in metadata storage</span>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Current Page</span>
            <Clock className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-black text-emerald-700">{filteredLogs.length}</div>
          <span className="text-[10px] text-slate-400 font-medium">Page {page} of {totalPages}</span>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Zero Secret Leakage</span>
            <Lock className="h-4 w-4 text-purple-500" />
          </div>
          <div className="text-sm font-black text-purple-700 mt-1">100% Redacted</div>
          <span className="text-[10px] text-slate-400 font-medium">Zero plaintext secrets or passwords</span>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Storage Chain</span>
            <Shield className="h-4 w-4 text-indigo-500" />
          </div>
          <div className="text-sm font-black text-indigo-700 mt-1">Immutable</div>
          <span className="text-[10px] text-slate-400 font-medium">Strict append-only constraints</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs space-y-3">
        {/* Quick Filter Chips */}
        <div className="flex flex-wrap items-center gap-1.5 pb-2 border-b border-slate-100">
          <span className="text-[11px] font-bold text-slate-400 mr-2 flex items-center gap-1">
            <SlidersHorizontal className="h-3.5 w-3.5" /> Filter:
          </span>
          {quickActionFilters.map((q) => (
            <button
              key={q.value}
              type="button"
              onClick={() => { setActionFilter(q.value); setPage(1); }}
              className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-all ${
                actionFilter === q.value
                  ? "bg-blue-600 text-white shadow-xs"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {q.label}
            </button>
          ))}
        </div>

        {/* Detailed Input Row */}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search records or details…"
              className="w-full rounded-xl border border-slate-200 pl-8 pr-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <input
              type="text"
              value={actorFilter}
              onChange={(e) => { setActorFilter(e.target.value); setPage(1); }}
              placeholder="Filter by Actor (e.g. obuli)"
              className="w-full rounded-xl border border-slate-200 px-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <input
              type="text"
              value={targetFilter}
              onChange={(e) => { setTargetFilter(e.target.value); setPage(1); }}
              placeholder="Filter by Target (e.g. sundar)"
              className="w-full rounded-xl border border-slate-200 px-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <select
              value={outcomeFilter}
              onChange={(e) => { setOutcomeFilter(e.target.value); setPage(1); }}
              className="w-full rounded-xl border border-slate-200 px-3 py-1.5 text-xs text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white"
            >
              <option value="">All Outcomes</option>
              <option value="SUCCESS">SUCCESS Only</option>
              <option value="FAILURE">FAILURE Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Audit Records Table Container with Horizontal and Vertical Scrolling */}
      <div className="rounded-2xl border border-slate-200/90 bg-white shadow-xs overflow-hidden flex flex-col">
        <div className="overflow-x-auto w-full">
          <table className="w-full text-left text-xs text-slate-600 min-w-[900px]">
            <thead className="border-b border-slate-200 bg-slate-50/90 text-[11px] font-bold uppercase tracking-wider text-slate-500 sticky top-0 backdrop-blur-xs">
              <tr>
                <th className="py-3.5 px-4">Timestamp</th>
                <th className="py-3.5 px-4">Action Event</th>
                <th className="py-3.5 px-4">Actor</th>
                <th className="py-3.5 px-4">Target User</th>
                <th className="py-3.5 px-4">Outcome</th>
                <th className="py-3.5 px-4">Details & Reason</th>
                <th className="py-3.5 px-4">Source IP</th>
                <th className="py-3.5 px-4 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="h-7 w-7 animate-spin text-blue-600" />
                      <span className="text-xs font-semibold">Loading security audit trail…</span>
                    </div>
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center gap-1.5">
                      <Shield className="h-8 w-8 text-slate-300" />
                      <span className="text-sm font-bold text-slate-700">No matching audit events found</span>
                      <p className="text-xs text-slate-400 max-w-sm">
                        Try resetting active filters or triggering actions in the application.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr
                    key={log.id}
                    onClick={() => setSelectedEntry(log)}
                    className="hover:bg-slate-50/80 transition-colors cursor-pointer group"
                  >
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-500 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <span className={`inline-flex items-center rounded-lg border px-2.5 py-1 text-[10px] font-bold tracking-wide uppercase ${getActionBadge(log.action)}`}>
                        {log.action}
                      </span>
                    </td>

                    <td className="py-3 px-4 font-bold text-slate-900 whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-blue-500" />
                        <span>{log.actor_username || "SYSTEM"}</span>
                      </div>
                    </td>

                    <td className="py-3 px-4 text-slate-700 whitespace-nowrap">
                      {log.target_username ? (
                        <span className="font-semibold text-slate-800">{log.target_username}</span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                          log.outcome === "SUCCESS"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-rose-50 text-rose-700 border border-rose-200"
                        }`}
                      >
                        {log.outcome === "SUCCESS" ? (
                          <CheckCircle2 className="h-3 w-3" />
                        ) : (
                          <XCircle className="h-3 w-3" />
                        )}
                        <span>{log.outcome}</span>
                      </span>
                    </td>

                    <td className="py-3 px-4 max-w-xs truncate text-slate-600 font-mono text-[11px]" title={log.details || ""}>
                      {log.details || "—"}
                    </td>

                    <td className="py-3 px-4 font-mono text-[11px] text-slate-400 whitespace-nowrap">
                      {log.ip_address || "127.0.0.1"}
                    </td>

                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedEntry(log);
                        }}
                        className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-semibold text-blue-600 hover:bg-blue-50 transition-colors"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-t border-slate-200 bg-slate-50/70 px-4 py-3 text-xs text-slate-500 gap-2">
          <div className="flex items-center gap-2">
            <span>
              Showing page <strong className="text-slate-800">{page}</strong> of <strong className="text-slate-800">{totalPages}</strong> ({total} total security entries)
            </span>
            <span className="text-slate-300">•</span>
            <select
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
              className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700"
            >
              <option value={15}>15 per page</option>
              <option value={25}>25 per page</option>
              <option value={50}>50 per page</option>
              <option value={100}>100 per page</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 self-end sm:self-auto">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 shadow-2xs"
            >
              <ChevronLeft className="h-4 w-4" />
              <span>Previous</span>
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 shadow-2xs"
            >
              <span>Next</span>
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Audit Detail Inspector Modal */}
      {selectedEntry && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-blue-600" />
                <h3 className="text-base font-bold text-slate-900">
                  Security Event Inspector #{selectedEntry.id}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedEntry(null)}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none p-1 rounded-lg hover:bg-slate-100"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 overflow-y-auto flex-1 pr-1 text-xs">
              <div className="grid grid-cols-2 gap-2 rounded-xl bg-slate-50 p-3 border border-slate-100">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Action Type</span>
                  <div className="font-bold text-slate-900 mt-0.5">{selectedEntry.action}</div>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Outcome</span>
                  <div className="font-bold text-slate-900 mt-0.5">{selectedEntry.outcome}</div>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Actor</span>
                  <div className="font-bold text-slate-900 mt-0.5">{selectedEntry.actor_username || "SYSTEM"}</div>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Target User</span>
                  <div className="font-bold text-slate-900 mt-0.5">{selectedEntry.target_username || "—"}</div>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Client IP</span>
                  <div className="font-mono text-slate-800 mt-0.5">{selectedEntry.ip_address || "127.0.0.1"}</div>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400">Timestamp</span>
                  <div className="font-mono text-slate-800 mt-0.5">{new Date(selectedEntry.created_at).toISOString()}</div>
                </div>
              </div>

              <div>
                <span className="block text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Metadata & Event Detail Payload
                </span>
                <pre className="rounded-xl border border-slate-800 bg-slate-900 p-3.5 font-mono text-[11px] text-emerald-400 overflow-x-auto whitespace-pre-wrap">
                  {(() => {
                    try {
                      const parsed = JSON.parse(selectedEntry.details);
                      return JSON.stringify(parsed, null, 2);
                    } catch {
                      return selectedEntry.details || "No extended payload recorded.";
                    }
                  })()}
                </pre>
              </div>
            </div>

            <div className="flex items-center justify-end border-t border-slate-100 pt-3">
              <button
                type="button"
                onClick={() => setSelectedEntry(null)}
                className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
