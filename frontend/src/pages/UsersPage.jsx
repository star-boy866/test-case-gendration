import { useEffect, useState, useCallback } from "react";
import { Navigate } from "react-router-dom";
import { UserPlus, AlertTriangle, CheckCircle2 } from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";
import { listUsers, createUser } from "../services/api";

const ROLES = ["tester", "approver", "admin"];

export default function UsersPage() {
  const { user, hasAtLeast } = useAuth();

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("tester");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [createdMessage, setCreatedMessage] = useState(null);

  const refresh = useCallback(() => {
    setLoading(true);
    listUsers()
      .then((res) => setUsers(res.data))
      .catch((err) => setLoadError(err.response?.data?.detail || "Could not load users."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (hasAtLeast("admin")) refresh();
  }, [hasAtLeast, refresh]);

  // Client-side gate is a UX convenience only — POST /api/auth/users and
  // GET /api/auth/users both independently require 'admin' server-side
  // (see core/rbac.py), so this page can't actually leak anything even if
  // someone bypassed this check entirely.
  if (!hasAtLeast("admin")) {
    return <Navigate to="/" replace />;
  }

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    setCreatedMessage(null);
    try {
      const res = await createUser({ username, password, role });
      setCreatedMessage(`Account '${res.data.username}' created with role '${res.data.role}'.`);
      setUsername("");
      setPassword("");
      setRole("tester");
      refresh();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setCreateError(
        Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail || "Could not create user."
      );
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">User Management</h2>
        <p className="text-sm text-slate-500">
          Admin-only. Create accounts for testers/approvers/admins — see
          core/rbac.py for what each role can do.
        </p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-700">
          <UserPlus className="h-4 w-4" />
          Create account
        </h3>
        <form onSubmit={handleCreate} className="grid gap-3 sm:grid-cols-4 sm:items-end">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Username</span>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              required
              minLength={3}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              required
              minLength={12}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={creating}
            className="rounded-md bg-brand-500 px-3 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {creating ? "Creating…" : "Create"}
          </button>
        </form>

        {createError && (
          <div className="mt-3 flex items-start gap-2 rounded-md bg-red-50 p-3 text-xs text-red-700">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{createError}</span>
          </div>
        )}
        {createdMessage && (
          <div className="mt-3 flex items-start gap-2 rounded-md bg-emerald-50 p-3 text-xs text-emerald-800">
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{createdMessage}</span>
          </div>
        )}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h3 className="mb-3 text-sm font-medium text-slate-700">Existing accounts</h3>

        {loadError && (
          <div className="flex items-start gap-2 rounded-md bg-red-50 p-3 text-xs text-red-700">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{loadError}</span>
          </div>
        )}

        {!loading && !loadError && (
          <table className="w-full text-left text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="pb-2 font-medium">Username</th>
                <th className="pb-2 font-medium">Role</th>
                <th className="pb-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-slate-100">
                  <td className="py-2">
                    {u.username}
                    {u.username === user?.username && (
                      <span className="ml-2 text-xs text-slate-400">(you)</span>
                    )}
                  </td>
                  <td className="py-2 uppercase text-xs text-slate-500">{u.role}</td>
                  <td className="py-2">
                    {u.is_active ? (
                      <span className="text-emerald-600">Active</span>
                    ) : (
                      <span className="text-slate-400">Inactive</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
