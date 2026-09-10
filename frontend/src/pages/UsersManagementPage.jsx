import { useState, useEffect, useCallback } from "react";
import {
  Users,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Lock,
  UserCheck,
  UserX,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  KeyRound,
  MoreVertical,
  Key,
  Search,
  Filter,
  UserPlus,
  RefreshCw,
  Clock,
  Sparkles,
  SlidersHorizontal,
  X,
  Eye,
  EyeOff,
} from "lucide-react";
import { listAdminUsers, updateUserStatus, updateUserRole, createAdminUser } from "../services/api";
import { useAuth } from "../context/AuthContext.jsx";

export default function UsersManagementPage() {
  const { user: currentUser, isStandardAdmin } = useAuth();

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Search and filter state
  const [searchTerm, setSearchTerm] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  // Modal for changing status or role
  const [targetUser, setTargetUser] = useState(null);
  const [actionType, setActionType] = useState(null); // "STATUS" | "ROLE" | "CREATE" | null
  const [newStatus, setNewStatus] = useState("ACTIVE");
  const [newRole, setNewRole] = useState("tester");
  const [reason, setReason] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState(null);

  // Create User Form State
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [createdRole, setCreatedRole] = useState("tester");

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listAdminUsers();
      setUsers(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load user directory.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const openStatusModal = (u, status) => {
    setTargetUser(u);
    setActionType("STATUS");
    setNewStatus(status);
    setReason(status === "ACTIVE" ? "Reactivating account per compliance review." : "Suspended account pending security audit.");
    setAdminPassword("");
    setMfaCode("");
    setModalError(null);
  };

  const openRoleModal = (u) => {
    setTargetUser(u);
    setActionType("ROLE");
    setNewRole(u.role);
    setReason("Adjusting organizational role authorization.");
    setAdminPassword("");
    setMfaCode("");
    setModalError(null);
  };

  const openCreateModal = () => {
    setActionType("CREATE");
    setNewUsername("");
    setNewPassword("");
    setCreatedRole("tester");
    setModalError(null);
  };

  const closeModal = () => {
    setTargetUser(null);
    setActionType(null);
    setModalError(null);
  };

  const handleActionSubmit = async (e) => {
    e.preventDefault();
    if (!reason.trim()) {
      setModalError("A documented business justification is required for identity modifications.");
      return;
    }
    if (!adminPassword) {
      setModalError("Please enter your current administrator password to authenticate.");
      return;
    }

    setSubmitting(true);
    setModalError(null);

    try {
      if (actionType === "STATUS") {
        await updateUserStatus(targetUser.id, {
          status: newStatus,
          reason: reason.trim(),
          admin_password: adminPassword,
          mfa_code: mfaCode.trim() || undefined,
        });
        setSuccessMsg(`Account status for '${targetUser.username}' updated to ${newStatus}.`);
      } else if (actionType === "ROLE") {
        await updateUserRole(targetUser.id, {
          role: newRole,
          reason: reason.trim(),
          admin_password: adminPassword,
          mfa_code: mfaCode.trim() || undefined,
        });
        setSuccessMsg(`Role for '${targetUser.username}' updated to ${newRole}.`);
      }
      closeModal();
      await fetchUsers();
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setModalError(
        Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail || "Failed to update user."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setModalError(null);

    try {
      const res = await createAdminUser({
        username: newUsername.trim(),
        password: newPassword,
        role: createdRole,
      });
      setSuccessMsg(`Account '${res.data.user.username}' provisioned successfully.`);
      closeModal();
      await fetchUsers();
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setModalError(
        Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail || "Failed to provision user."
      );
    } finally {
      setSubmitting(false);
    }
  };

  // Filtered users list
  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      !searchTerm.trim() ||
      u.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
      String(u.id).includes(searchTerm.trim()) ||
      u.role.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesRole = !roleFilter || u.role === roleFilter;
    const matchesStatus = !statusFilter || u.status === statusFilter;

    return matchesSearch && matchesRole && matchesStatus;
  });

  // KPI Calculations
  const totalCount = users.length;
  const adminCount = users.filter((u) => u.role === "standard_admin" || u.role === "admin").length;
  const testerCount = users.filter((u) => u.role === "tester").length;
  const suspendedCount = users.filter((u) => u.status === "SUSPENDED" || u.status === "REVOKED" || u.is_locked).length;

  const getRoleBadge = (role) => {
    switch (role) {
      case "standard_admin":
        return "bg-purple-100 text-purple-800 border-purple-200/80 shadow-2xs";
      case "admin":
        return "bg-indigo-100 text-indigo-800 border-indigo-200/80 shadow-2xs";
      case "tester":
        return "bg-blue-100 text-blue-800 border-blue-200/80";
      default:
        return "bg-amber-100 text-amber-800 border-amber-200/80";
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case "ACTIVE":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "PENDING":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "SUSPENDED":
        return "bg-orange-50 text-orange-700 border-orange-200";
      default:
        return "bg-rose-50 text-rose-700 border-rose-200";
    }
  };

  return (
    <div className="w-full max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6 pb-20">
      
      {/* Top Banner & Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-0.5 text-[11px] font-bold text-blue-700 border border-blue-200/70">
              <Users className="h-3.5 w-3.5" />
              Directory & RBAC
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-bold text-emerald-700 border border-emerald-200/70">
              <ShieldCheck className="h-3.5 w-3.5" />
              Standard Admin Protection Active
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            User Directory & Access Governance
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Manage enterprise identities, grant or modify roles, and enforce account suspension or revocation with real-time audit trail integration.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={openCreateModal}
            className="flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:from-blue-700 hover:to-indigo-700 transition-all"
          >
            <UserPlus className="h-4 w-4" />
            <span>Provision Account</span>
          </button>

          <button
            type="button"
            onClick={fetchUsers}
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
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Total Directory Accounts</span>
            <Users className="h-4 w-4 text-blue-500" />
          </div>
          <div className="text-2xl font-black text-slate-900">{totalCount}</div>
          <span className="text-[10px] text-slate-400 font-medium">Registered in enterprise system</span>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Administrative Tier</span>
            <Shield className="h-4 w-4 text-purple-500" />
          </div>
          <div className="text-2xl font-black text-purple-700">{adminCount}</div>
          <span className="text-[10px] text-slate-400 font-medium">Standard Admin + Approved Admins</span>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Certified QA Testers</span>
            <Sparkles className="h-4 w-4 text-blue-500" />
          </div>
          <div className="text-2xl font-black text-blue-700">{testerCount}</div>
          <span className="text-[10px] text-slate-400 font-medium">Test Studio Generation Access</span>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Restricted / Suspended</span>
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          </div>
          <div className={`text-2xl font-black ${suspendedCount > 0 ? "text-amber-600" : "text-slate-400"}`}>
            {suspendedCount}
          </div>
          <span className="text-[10px] text-slate-400 font-medium">Suspended, revoked, or locked</span>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <div className="relative sm:col-span-2 lg:col-span-2">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by username, role, or ID…"
              className="w-full rounded-xl border border-slate-200 pl-9 pr-8 py-2 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm("")}
                className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <div>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white"
            >
              <option value="">All Roles</option>
              <option value="standard_admin">Standard Admin</option>
              <option value="admin">Admin</option>
              <option value="tester">Tester</option>
              <option value="pending">Pending</option>
            </select>
          </div>

          <div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white"
            >
              <option value="">All Account Statuses</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="PENDING">PENDING</option>
              <option value="SUSPENDED">SUSPENDED</option>
              <option value="REVOKED">REVOKED</option>
            </select>
          </div>
        </div>
      </div>

      {/* World-Class User Directory Table */}
      <div className="rounded-2xl border border-slate-200/90 bg-white shadow-xs overflow-hidden flex flex-col">
        <div className="overflow-x-auto w-full">
          <table className="w-full text-left text-xs text-slate-600 min-w-[850px]">
            <thead className="border-b border-slate-200 bg-slate-50/90 text-[11px] font-bold uppercase tracking-wider text-slate-500 sticky top-0 backdrop-blur-xs">
              <tr>
                <th className="py-3.5 px-4">Identity & Account</th>
                <th className="py-3.5 px-4">Role Tier</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Security Baseline</th>
                <th className="py-3.5 px-4">Created Date</th>
                <th className="py-3.5 px-4 text-right">Administrative Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-16 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Loader2 className="h-7 w-7 animate-spin text-blue-600" />
                      <span className="text-xs font-semibold">Loading identity directory…</span>
                    </div>
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-16 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center gap-1.5">
                      <Users className="h-8 w-8 text-slate-300" />
                      <span className="text-sm font-bold text-slate-700">No matching user accounts</span>
                      <p className="text-xs text-slate-400 max-w-sm">
                        No identities match the active filter criteria. Try adjusting filters or search query.
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => {
                  const isTargetStandardAdmin = u.role === "standard_admin" || u.username === "obuli";
                  const isCurrentAccount = u.id === currentUser?.id;
                  const canModify = u.can_modify && !isTargetStandardAdmin;

                  return (
                    <tr key={u.id} className="hover:bg-slate-50/70 transition-colors">
                      {/* Identity & Account */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-3">
                          <div className={`flex h-9 w-9 items-center justify-center rounded-xl font-bold text-xs shadow-2xs ${
                            isTargetStandardAdmin
                              ? "bg-gradient-to-br from-purple-500 to-indigo-600 text-white"
                              : u.role === "admin"
                              ? "bg-gradient-to-br from-indigo-500 to-blue-600 text-white"
                              : "bg-slate-100 text-slate-700 border border-slate-200"
                          }`}>
                            {u.username.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-bold text-slate-900 flex items-center gap-1.5 text-sm">
                              <span>{u.username}</span>
                              {isTargetStandardAdmin && (
                                <span className="inline-flex items-center gap-1 rounded-md bg-purple-100 px-1.5 py-0.5 text-[9px] font-black uppercase text-purple-800 border border-purple-200">
                                  <Lock className="h-2.5 w-2.5 text-purple-700" />
                                  Protected Admin
                                </span>
                              )}
                              {isCurrentAccount && (
                                <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[9px] font-semibold text-slate-600">
                                  You
                                </span>
                              )}
                            </div>
                            <span className="text-[11px] text-slate-400 font-mono">
                              ID #{u.id} • {u.last_login_at ? `Active ${new Date(u.last_login_at).toLocaleDateString()}` : "No login record"}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Role Tier */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <span className={`inline-flex items-center rounded-lg border px-2.5 py-1 text-xs font-bold uppercase tracking-wider ${getRoleBadge(u.role)}`}>
                          {u.role.replace("_", " ")}
                        </span>
                      </td>

                      {/* Account Status */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${getStatusBadge(u.status)}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${
                            u.status === "ACTIVE"
                              ? "bg-emerald-500"
                              : u.status === "PENDING"
                              ? "bg-amber-500"
                              : "bg-rose-500"
                          }`} />
                          <span>{u.status}</span>
                        </span>
                      </td>

                      {/* Security Baseline */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex flex-col gap-0.5">
                          {u.mfa_enabled ? (
                            <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-700">
                              <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                              <span>2FA Active</span>
                            </span>
                          ) : (
                            <span className="text-[11px] text-slate-400 flex items-center gap-1">
                              <Key className="h-3 w-3 text-slate-400" />
                              <span>Password Only</span>
                            </span>
                          )}
                          {u.must_change_password ? (
                            <span className="text-[10px] text-amber-600 font-semibold">
                              Must Change PW
                            </span>
                          ) : (
                            <span className="text-[10px] text-slate-400">
                              Established PW
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Created Date */}
                      <td className="py-3.5 px-4 text-slate-400 whitespace-nowrap text-[11px]">
                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                      </td>

                      {/* Administrative Actions */}
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          {isStandardAdmin && !isTargetStandardAdmin && (
                            <button
                              type="button"
                              onClick={() => openRoleModal(u)}
                              className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors"
                              title="Modify account role"
                            >
                              Role
                            </button>
                          )}

                          {canModify ? (
                            u.status === "ACTIVE" ? (
                              <button
                                type="button"
                                onClick={() => openStatusModal(u, "SUSPENDED")}
                                className="rounded-lg border border-amber-200 bg-amber-50/70 px-2.5 py-1 text-xs font-semibold text-amber-700 hover:bg-amber-100 transition-colors"
                                title="Temporarily suspend account"
                              >
                                Suspend
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={() => openStatusModal(u, "ACTIVE")}
                                className="rounded-lg border border-emerald-200 bg-emerald-50/70 px-2.5 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 transition-colors"
                                title="Re-activate account"
                              >
                                Activate
                              </button>
                            )
                          ) : isTargetStandardAdmin ? (
                            <span className="text-[11px] text-slate-400 italic px-2 py-1" title="Standard Admin cannot be suspended or modified">
                              Protected
                            </span>
                          ) : (
                            <span className="text-[11px] text-slate-400 italic px-2 py-1">
                              Restricted
                            </span>
                          )}

                          {canModify && u.status !== "REVOKED" && (
                            <button
                              type="button"
                              onClick={() => openStatusModal(u, "REVOKED")}
                              className="rounded-lg border border-rose-200 bg-rose-50/70 px-2.5 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-100 transition-colors"
                              title="Permanently revoke access"
                            >
                              Revoke
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Provision Account Modal */}
      {actionType === "CREATE" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <UserPlus className="h-5 w-5 text-blue-600" />
                <span>Provision Identity Account</span>
              </h3>
              <button
                type="button"
                onClick={closeModal}
                className="text-slate-400 hover:text-slate-600 text-lg leading-none"
              >
                ✕
              </button>
            </div>

            {modalError && (
              <div className="rounded-xl border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800">
                {modalError}
              </div>
            )}

            <form onSubmit={handleCreateSubmit} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Username <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="e.g. qa_specialist_mark"
                  className="w-full rounded-xl border border-slate-300 p-2.5 text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  required
                  minLength={3}
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Role Assignment <span className="text-rose-500">*</span>
                </label>
                <select
                  value={createdRole}
                  onChange={(e) => setCreatedRole(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 p-2.5 text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white"
                >
                  <option value="tester">Tester (Cognos Test Case Studio)</option>
                  {isStandardAdmin && <option value="admin">Admin (Administrative Access)</option>}
                </select>
                {!isStandardAdmin && (
                  <p className="text-[10px] text-slate-400 mt-1">
                    Only the Standard Administrator can provision Admin accounts.
                  </p>
                )}
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Temporary Password <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type={showNewPassword ? "text" : "password"}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Min 12 characters, uppercase, digit, special"
                    className="w-full rounded-xl border border-slate-300 p-2.5 pr-9 text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    required
                    minLength={12}
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                  >
                    {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <span className="text-[10px] text-slate-400 mt-1 block">
                  The user will be forced to change this password on their initial login.
                </span>
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
                  disabled={submitting}
                  className="rounded-xl bg-blue-600 px-5 py-2 font-bold text-white hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1.5 shadow-xs"
                >
                  {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  <span>Create Account</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Role / Status Modification Modal */}
      {(actionType === "ROLE" || actionType === "STATUS") && targetUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <KeyRound className="h-5 w-5 text-blue-600" />
                {actionType === "ROLE" ? "Modify User Role" : "Update Account Status"}
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
              Target User: <strong className="text-slate-900">'{targetUser.username}'</strong> (Current Role:{" "}
              <span className="font-bold text-slate-800">{targetUser.role}</span>, Status:{" "}
              <span className="font-bold text-slate-800">{targetUser.status}</span>).
            </p>

            {modalError && (
              <div className="rounded-xl border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800">
                {modalError}
              </div>
            )}

            <form onSubmit={handleActionSubmit} className="space-y-3.5 text-xs">
              {actionType === "ROLE" && (
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Select New Role <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={newRole}
                    onChange={(e) => setNewRole(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 p-2.5 text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white"
                  >
                    <option value="tester">Tester (Cognos Test Case Studio)</option>
                    <option value="admin">Admin (Approvals, User Governance)</option>
                  </select>
                </div>
              )}

              {actionType === "STATUS" && (
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    New Status State <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={newStatus}
                    onChange={(e) => setNewStatus(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 p-2.5 text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white"
                  >
                    <option value="ACTIVE">ACTIVE (Normal Access)</option>
                    <option value="SUSPENDED">SUSPENDED (Temporary Lockout)</option>
                    <option value="REVOKED">REVOKED (Permanent Invalidation)</option>
                  </select>
                </div>
              )}

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Documented Justification / Reason <span className="text-rose-500">*</span>
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
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
                  disabled={submitting}
                  className="rounded-xl bg-blue-600 px-5 py-2 font-bold text-white hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1.5 shadow-xs"
                >
                  {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  <span>Confirm Change</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
