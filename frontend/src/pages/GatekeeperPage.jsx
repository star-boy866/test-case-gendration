import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, AlertTriangle, CheckCircle2, ArrowRight } from "lucide-react";
import { getGatekeeperScope, confirmGatekeeper } from "../services/api";
import { useWorkflow } from "../context/WorkflowContext.jsx";
import { useAuth } from "../context/AuthContext.jsx";

export default function GatekeeperPage() {
  const { reportId, crId, setCrId, setSessionId } = useWorkflow();
  const { hasAtLeast } = useAuth();
  const [scope, setScope] = useState(null);
  const [crDescription, setCrDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState(null);
  const [confirmed, setConfirmed] = useState(null);

  useEffect(() => {
    if (!reportId.trim()) return;
    setLoading(true);
    setError(null);
    getGatekeeperScope(reportId)
      .then((res) => {
        setScope(res.data);
        if (res.data.cr_description) setCrDescription(res.data.cr_description);
        if (res.data.is_confirmed) {
          setConfirmed(res.data);
          if (res.data.session_id) setSessionId(res.data.session_id);
        }
      })
      .catch((err) => {
        setError(
          err.response?.data?.detail ||
            "Could not load scope summary — is the backend running?"
        );
      })
      .finally(() => setLoading(false));
  }, [reportId]);

  const handleConfirm = async () => {
    setConfirming(true);
    setError(null);
    try {
      const res = await confirmGatekeeper({ reportId, crId, crDescription });
      setConfirmed(res.data);
      setSessionId(res.data.session_id);
    } catch (err) {
      setError(err.response?.data?.detail || "Confirmation failed.");
    } finally {
      setConfirming(false);
    }
  };

  if (!reportId.trim()) {
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Step 2 — Gatekeeper Confirmation</h2>
        <div className="flex items-start gap-2 rounded-md bg-amber-50 p-4 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            No Report ID set yet. Go back to{" "}
            <Link to="/" className="underline">
              Step 1 — Ingestion
            </Link>{" "}
            and upload a document first.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Step 2 — Gatekeeper Confirmation</h2>
        <p className="text-sm text-slate-500">
          Strict blocking step — generation cannot run until scope is
          explicitly confirmed here.
        </p>
      </div>

      {loading && <p className="text-sm text-slate-500">Loading extracted scope…</p>}

      {error && (
        <div className="flex items-start gap-2 rounded-md bg-red-50 p-3 text-sm text-red-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {scope && !confirmed && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
          <div className="mb-4 flex items-center gap-2 text-amber-800">
            <ShieldCheck className="h-5 w-5" />
            <span className="font-medium">Scope confirmation required</span>
          </div>

          <dl className="mb-4 grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-slate-500">CR ID</dt>
              <dd>
                <input
                  type="text"
                  value={crId}
                  onChange={(e) => setCrId(e.target.value)}
                  placeholder="Required"
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
                />
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-slate-500">CR Description</dt>
              <dd>
                <input
                  type="text"
                  value={crDescription}
                  onChange={(e) => setCrDescription(e.target.value)}
                  placeholder="Required — what is this change request for?"
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
                />
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Report ID / Functional Area</dt>
              <dd className="mt-1 font-medium text-slate-800">{scope.report_id}</dd>
            </div>
          </dl>

          <div className="mb-4 rounded-md bg-white p-3 text-sm">
            <p className="mb-2 font-medium text-slate-700">Extracted scope</p>
            <ul className="grid grid-cols-2 gap-1 text-slate-600 sm:grid-cols-3">
              <li>Tables: {scope.counts.tables}</li>
              <li>Columns: {scope.counts.columns}</li>
              <li>Joins: {scope.counts.joins}</li>
              <li>Valid values: {scope.counts.valid_values}</li>
              <li>Business rules: {scope.counts.business_rules}</li>
              <li className="text-slate-400">
                Pending review: {scope.counts.unstructured_notes}
              </li>
            </ul>
          </div>

          {!scope.can_confirm && (
            <div className="mb-4 flex items-start gap-2 rounded-md bg-red-50 p-3 text-sm text-red-700">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Insufficient metadata available. Additional documentation is
                required before generation can continue.
              </span>
            </div>
          )}

          {!hasAtLeast("approver") && (
            <div className="mb-4 flex items-start gap-2 rounded-md bg-slate-100 p-3 text-xs text-slate-600">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                Confirming scope requires the 'approver' role or higher — your
                account is a 'tester'. Ask an admin to grant approver access,
                or have an approver confirm this scope.
              </span>
            </div>
          )}

          <button
            onClick={handleConfirm}
            disabled={!scope.can_confirm || !crId.trim() || !crDescription.trim() || confirming || !hasAtLeast("approver")}
            className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500"
          >
            {confirming ? "Confirming…" : "Confirm & Continue"}
          </button>
        </div>
      )}

      {confirmed && (
        <div className="space-y-4 rounded-lg border border-emerald-200 bg-emerald-50 p-6">
          <div className="flex items-center gap-2 text-emerald-800">
            <CheckCircle2 className="h-5 w-5" />
            <span className="font-medium">Scope confirmed</span>
          </div>
          <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-slate-500">CR ID</dt>
              <dd className="font-medium text-slate-800">{confirmed.cr_id}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-slate-500">CR Description</dt>
              <dd className="font-medium text-slate-800">{confirmed.cr_description}</dd>
            </div>
          </dl>
          <p className="text-xs text-emerald-700">
            Confirmed by {confirmed.confirmed_by} at{" "}
            {new Date(confirmed.confirmed_at).toLocaleString()}
          </p>
          <Link
            to="/refinement"
            className="inline-flex items-center gap-1 rounded-md bg-brand-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-600"
          >
            Continue to Refinement <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      )}
    </div>
  );
}
