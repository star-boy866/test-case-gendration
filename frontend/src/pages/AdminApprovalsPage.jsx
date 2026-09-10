import { useState, useEffect, useCallback } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  User,
  Shield,
  Loader2,
  Lock,
  Search,
  Filter,
  Eye,
  KeyRound,
  PlusCircle,
  RefreshCw,
  Sparkles,
  Inbox,
  UserCheck,
  FileText,
} from "lucide-react";
import { listApprovals, approveRequest, rejectRequest, seedDemoRequest } from "../services/api";
import { useAuth } from "../context/AuthContext.jsx";

export default function AdminApprovalsPage() {
  const { user, isStandardAdmin } = useAuth();

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ pending_requests: [], history: [], all_requests: [] });
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [activeTab, setActiveTab] = useState("PENDING"); // "PENDING" | "ALL" | "HISTORY"
  const [seeding, setSeeding] = useState(false);

  // Approval / Rejection Modal State
  const [modalMode, setModalMode] = useState(null); // "APPROVE" | "REJECT" | null
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [actionReason, setActionReason] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [processing, setProcessing] = useState(false);
  const [modalError, setModalError] = useState(null);

  const fetchApprovals = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listApprovals();
      const raw = res.data;
      if (Array.isArray(raw)) {
        setData({ pending_requests: raw, history: [], all_requests: raw });
      } else {
        setData({
          pending_requests: raw.pending_requests || [],
          history: raw.history || [],
          all_requests: raw.all_requests || raw.pending_requests || [],
        });
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Could not load access approvals pipeline.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  const handleSeedDemo = async () => {
    setSeeding(true);
    setError(null);
    try {
      const res = await seedDemoRequest();
      setSuccessMsg(res.data.message || "Created a test access request for review.");
      await fetchApprovals();
      setActiveTab("PENDING");
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create demo request.");
    } finally {
      setSeeding(false);
    }
  };

  const openModal = (req, mode) => {
    setSelectedRequest(req);
    setModalMode(mode);
    setActionReason(mode === "APPROVE" ? "Approved per enterprise security clearance." : "Role request does not meet department criteria.");
    setAdminPassword("");
    setMfaCode("");
    setModalError(null);
  };

  const closeModal = () => {
    setModalMode(null);
    setSelectedRequest(null);
    setModalError(null);
  };

  const handleActionSubmit = async (e) => {
    e.preventDefault();
    if (!actionReason.trim()) {
      setModalError("Please provide a mandatory justification reason.");
      return;
    }
    if (!adminPassword) {
      setModalError("Please enter your current administrator password to verify identity.");
      return;
    }

    setProcessing(true);
    setModalError(null);

    try {
      if (modalMode === "APPROVE") {
        await approveRequest(selectedRequest.id, {
          reason: actionReason.trim(),
          admin_password: adminPassword,
          mfa_code: mfaCode.trim() || undefined,
        });
        setSuccessMsg(`Successfully approved access request for '${selectedRequest.username}'.`);
      } else {
        await rejectRequest(selectedRequest.id, {
          reason: actionReason.trim(),
          admin_password: adminPassword,
          mfa_code: mfaCode.trim() || undefined,
        });
        setSuccessMsg(`Successfully rejected access request for '${selectedRequest.username}'.`);
      }
      closeModal();
      await fetchApprovals();
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setModalError(
        Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail || "Failed to process request."
      );
    } finally {
      setProcessing(false);
    }
  };

  const pendingList = data.pending_requests || [];
  const historyList = data.history || [];
  const allList = data.all_requests || [];

  const approvedCount = allList.filter((r) => r.status === "APPROVED").length;
  const rejectedCount = allList.filter((r) => r.status === "REJECTED").length;

  return (
    <div className="w-full max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6 pb-20">
      
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-blue-700 border border-blue-200/70">
              <ShieldCheck className="h-3.5 w-3.5" />
              Dual-Control RBAC Governance
            </span>
            {isStandardAdmin && (
              <span className="inline-flex items-center gap-1 rounded-full bg-purple-50 px-2.5 py-0.5 text-[11px] font-bold text-purple-700 border border-purple-200/70">
                Standard Admin Authority
              </span>
            )}
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Access Request Approvals & Governance
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Review applicant identities, business justifications, and govern Tester and Admin role grants with full separation of duties.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleSeedDemo}
            disabled={seeding}
            className="flex items-center gap-1.5 rounded-xl border border-blue-200 bg-blue-50/80 px-3.5 py-2 text-xs font-bold text-blue-700 hover:bg-blue-100 transition-all shadow-2xs disabled:opacity-50"
            title="Create a sample access request to test approval"
          >
            <PlusCircle className={`h-4 w-4 ${seeding ? "animate-spin" : ""}`} />
            <span>Generate Test Request</span>
          </button>

          <button
            type="button"
            onClick={fetchApprovals}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 hover:border-slate-300 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 text-blue-600 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-4 text-xs font-medium text-emerald-800 flex items-center gap-2.5 shadow-xs">
          <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-rose-300 bg-rose-50 p-4 text-xs font-medium text-rose-800 flex items-center gap-2.5 shadow-xs">
          <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Pending Review</span>
            <Clock className="h-4 w-4 text-amber-500" />
          </div>
          <div className="text-2xl font-black text-amber-600">{pendingList.length}</div>
          <span className="text-[10px] text-slate-400 font-medium">Awaiting administrator clearance</span>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Approved Access</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-black text-emerald-700">{approvedCount || (historyList.filter(h => h.decision === "APPROVED").length)}</div>
          <span className="text-[10px] text-slate-400 font-medium">Granted active privileges</span>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Rejected Requests</span>
            <XCircle className="h-4 w-4 text-rose-500" />
          </div>
          <div className="text-2xl font-black text-rose-700">{rejectedCount || (historyList.filter(h => h.decision === "REJECTED").length)}</div>
          <span className="text-[10px] text-slate-400 font-medium">Declined by security policy</span>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Audit History Entries</span>
            <Shield className="h-4 w-4 text-blue-500" />
          </div>
          <div className="text-2xl font-black text-slate-900">{historyList.length}</div>
          <span className="text-[10px] text-slate-400 font-medium">Logged in tamper-evident ledger</span>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-200">
        <button
          type="button"
          onClick={() => setActiveTab("PENDING")}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${
            activeTab === "PENDING"
              ? "border-blue-600 text-blue-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Clock className="h-4 w-4" />
          <span>Pending Queue</span>
          {pendingList.length > 0 && (
            <span className="rounded-full bg-amber-500 text-white px-2 py-0.5 text-[10px] font-extrabold animate-pulse">
              {pendingList.length}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("ALL")}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${
            activeTab === "ALL"
              ? "border-blue-600 text-blue-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Inbox className="h-4 w-4" />
          <span>All Role Requests</span>
          <span className="rounded-full bg-slate-100 text-slate-600 px-2 py-0.5 text-[10px] font-bold">
            {allList.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("HISTORY")}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${
            activeTab === "HISTORY"
              ? "border-blue-600 text-blue-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Shield className="h-4 w-4" />
          <span>Decision History Log</span>
          <span className="rounded-full bg-slate-100 text-slate-600 px-2 py-0.5 text-[10px] font-bold">
            {historyList.length}
          </span>
        </button>
      </div>

      {/* TAB 1: PENDING QUEUE */}
      {activeTab === "PENDING" && (
        <div className="space-y-4">
          {loading ? (
            <div className="flex h-48 items-center justify-center rounded-2xl border border-slate-200 bg-white">
              <Loader2 className="h-7 w-7 animate-spin text-blue-600" />
            </div>
          ) : pendingList.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center shadow-xs">
              <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 border border-emerald-200">
                <CheckCircle2 className="h-7 w-7" />
              </div>
              <h3 className="text-base font-bold text-slate-900">All Access Requests Cleared</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                There are no pending accounts currently waiting for clearance. You can click <strong>Generate Test Request</strong> above to test the review workflow.
              </p>
              <button
                type="button"
                onClick={handleSeedDemo}
                className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-blue-700"
              >
                <PlusCircle className="h-4 w-4" />
                <span>Create Test Applicant</span>
              </button>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {pendingList.map((req) => {
                const isAdminRequest = req.requested_role === "admin";
                const cannotApproveAdmin = isAdminRequest && !isStandardAdmin;
                const isSelf = req.user_id === user?.id;

                return (
                  <div
                    key={req.id}
                    className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs hover:border-slate-300 transition-all flex flex-col justify-between"
                  >
                    <div className="space-y-3">
                      {/* Top Header */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-700 font-bold text-sm border border-blue-100">
                            {req.username.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <span className="font-bold text-slate-900 text-sm">{req.username}</span>
                            <div className="text-[11px] text-slate-400">Request #{req.id}</div>
                          </div>
                        </div>

                        <span
                          className={`rounded-lg px-2.5 py-1 text-[11px] font-extrabold uppercase tracking-wider ${
                            req.requested_role === "admin"
                              ? "bg-purple-100 text-purple-800 border border-purple-200"
                              : "bg-blue-100 text-blue-800 border border-blue-200"
                          }`}
                        >
                          Target: {req.requested_role}
                        </span>
                      </div>

                      {/* Requester Justification Quote */}
                      <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-xs text-slate-700">
                        <span className="block font-bold text-[10px] uppercase tracking-wider text-slate-400 mb-1">
                          Applicant Business Justification
                        </span>
                        <p className="italic text-slate-600">"{req.request_reason}"</p>
                      </div>

                      {/* Timestamp & Flags */}
                      <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                        <span>Submitted: {req.created_at ? new Date(req.created_at).toLocaleString() : "Recently"}</span>
                        <span className="font-semibold text-amber-600 flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-ping" />
                          Pending Review
                        </span>
                      </div>

                      {/* Boundary warnings */}
                      {cannotApproveAdmin && (
                        <div className="rounded-xl border border-amber-200 bg-amber-50 p-2.5 text-[11px] font-medium text-amber-800 flex items-center gap-1.5">
                          <Lock className="h-3.5 w-3.5 shrink-0 text-amber-600" />
                          <span>Admin role requests can be approved exclusively by the Standard Administrator.</span>
                        </div>
                      )}

                      {isSelf && (
                        <div className="rounded-xl border border-rose-200 bg-rose-50 p-2.5 text-[11px] font-medium text-rose-800 flex items-center gap-1.5">
                          <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-rose-600" />
                          <span>Self-approval is forbidden. Another administrator must review your request.</span>
                        </div>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="flex items-center gap-2 pt-4 border-t border-slate-100 mt-4">
                      <button
                        type="button"
                        disabled={cannotApproveAdmin || isSelf}
                        onClick={() => openModal(req, "APPROVE")}
                        className="flex-1 rounded-xl bg-emerald-600 py-2 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed shadow-xs transition-all flex items-center justify-center gap-1.5"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        <span>Approve</span>
                      </button>

                      <button
                        type="button"
                        disabled={cannotApproveAdmin || isSelf}
                        onClick={() => openModal(req, "REJECT")}
                        className="flex-1 rounded-xl border border-rose-200 bg-rose-50 py-2 text-xs font-bold text-rose-700 hover:bg-rose-100 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-1.5"
                      >
                        <XCircle className="h-4 w-4" />
                        <span>Reject</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: ALL ROLE REQUESTS */}
      {activeTab === "ALL" && (
        <div className="rounded-2xl border border-slate-200/90 bg-white shadow-xs overflow-hidden">
          <div className="overflow-x-auto w-full">
            <table className="w-full text-left text-xs text-slate-600 min-w-[700px]">
              <thead className="border-b border-slate-200 bg-slate-50/90 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3.5 px-4">Applicant</th>
                  <th className="py-3.5 px-4">Target Role</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4">Reason / Notes</th>
                  <th className="py-3.5 px-4">Reviewer</th>
                  <th className="py-3.5 px-4">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {allList.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      No access requests recorded yet.
                    </td>
                  </tr>
                ) : (
                  allList.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50/70">
                      <td className="py-3 px-4 font-bold text-slate-900">{r.username}</td>
                      <td className="py-3 px-4">
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-700">
                          {r.requested_role}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                            r.status === "APPROVED"
                              ? "bg-emerald-100 text-emerald-800"
                              : r.status === "PENDING"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-rose-100 text-rose-800"
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 max-w-xs truncate text-slate-600" title={r.request_reason}>
                        {r.request_reason}
                      </td>
                      <td className="py-3 px-4 font-medium text-slate-700">
                        {r.reviewer_username || (r.status === "PENDING" ? "Awaiting Review" : "—")}
                      </td>
                      <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                        {r.created_at ? new Date(r.created_at).toLocaleDateString() : "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: DECISION HISTORY */}
      {activeTab === "HISTORY" && (
        <div className="rounded-2xl border border-slate-200/90 bg-white shadow-xs overflow-hidden">
          <div className="overflow-x-auto w-full">
            <table className="w-full text-left text-xs text-slate-600 min-w-[700px]">
              <thead className="border-b border-slate-200 bg-slate-50/90 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3.5 px-4">Target Identity</th>
                  <th className="py-3.5 px-4">Assigned Role</th>
                  <th className="py-3.5 px-4">Action Taken</th>
                  <th className="py-3.5 px-4">Authorized By</th>
                  <th className="py-3.5 px-4">Documented Justification</th>
                  <th className="py-3.5 px-4">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {historyList.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      No decision records found.
                    </td>
                  </tr>
                ) : (
                  historyList.map((h) => (
                    <tr key={h.id} className="hover:bg-slate-50/70">
                      <td className="py-3 px-4 font-bold text-slate-900">{h.username}</td>
                      <td className="py-3 px-4">
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-700">
                          {h.requested_role}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${
                            h.decision === "APPROVED"
                              ? "bg-emerald-100 text-emerald-800"
                              : h.decision === "REJECTED"
                              ? "bg-rose-100 text-rose-800"
                              : "bg-blue-100 text-blue-800"
                          }`}
                        >
                          {h.decision}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-medium text-slate-800">{h.reviewer_username}</td>
                      <td className="py-3 px-4 max-w-xs truncate text-slate-600" title={h.reason}>
                        {h.reason}
                      </td>
                      <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                        {h.created_at ? new Date(h.created_at).toLocaleString() : "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Step-Up Re-Authentication Approval / Rejection Modal */}
      {modalMode && selectedRequest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                {modalMode === "APPROVE" ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                ) : (
                  <XCircle className="h-5 w-5 text-rose-600" />
                )}
                {modalMode === "APPROVE" ? "Confirm Access Approval" : "Confirm Access Rejection"}
              </h3>
              <button
                type="button"
                onClick={closeModal}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-500">
              You are resolving access request <strong>#{selectedRequest.id}</strong> for user{" "}
              <strong>'{selectedRequest.username}'</strong> (Requested Role:{" "}
              <span className="font-bold text-slate-800">{selectedRequest.requested_role}</span>).
            </p>

            {modalError && (
              <div className="rounded-xl border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800">
                {modalError}
              </div>
            )}

            <form onSubmit={handleActionSubmit} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Documented Justification / Reason <span className="text-rose-500">*</span>
                </label>
                <textarea
                  value={actionReason}
                  onChange={(e) => setActionReason(e.target.value)}
                  rows={2}
                  className="w-full rounded-xl border border-slate-300 p-2.5 text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Administrator Password (Step-Up Re-Auth) <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type="password"
                    value={adminPassword}
                    onChange={(e) => setAdminPassword(e.target.value)}
                    placeholder="Enter your current password"
                    className="w-full rounded-xl border border-slate-300 p-2.5 pr-9 text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    required
                  />
                  <KeyRound className="absolute right-3 top-2.5 h-4 w-4 text-slate-400" />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={closeModal}
                  className="rounded-xl border border-slate-200 px-4 py-2 font-semibold text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={processing}
                  className={`rounded-xl px-5 py-2 font-bold text-white shadow-xs flex items-center gap-1.5 ${
                    modalMode === "APPROVE"
                      ? "bg-emerald-600 hover:bg-emerald-700"
                      : "bg-rose-600 hover:bg-rose-700"
                  } disabled:opacity-50`}
                >
                  {processing && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  <span>{modalMode === "APPROVE" ? "Confirm Approval" : "Confirm Rejection"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
