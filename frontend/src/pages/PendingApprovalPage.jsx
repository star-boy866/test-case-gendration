import { useState, useEffect } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import {
  Clock,
  CheckCircle2,
  XCircle,
  RefreshCw,
  ArrowRight,
  Shield,
  AlertTriangle,
} from "lucide-react";
import { getRequestStatus } from "../services/api";

export default function PendingApprovalPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const username = searchParams.get("username");

  const [statusData, setStatusData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchStatus = async () => {
    setRefreshing(true);
    try {
      const res = await getRequestStatus();
      setStatusData(res.data);
    } catch {
      // If unauthenticated or no request token, display generic pending banner
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000); // Polling every 10s
    return () => clearInterval(interval);
  }, []);

  const isApproved = statusData?.status === "APPROVED";
  const isRejected = statusData?.status === "REJECTED";

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 px-4 py-12 text-slate-100">
      <div className="w-full max-w-lg rounded-2xl border border-slate-700/70 bg-slate-800/90 p-8 shadow-2xl backdrop-blur-md">
        
        {/* Header Icon */}
        <div className="mb-6 text-center">
          <div
            className={`mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-2xl border ${
              isApproved
                ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                : isRejected
                ? "bg-rose-500/20 text-rose-400 border-rose-500/30"
                : "bg-amber-500/20 text-amber-400 border-amber-500/30"
            }`}
          >
            {isApproved ? (
              <CheckCircle2 className="h-8 w-8" />
            ) : isRejected ? (
              <XCircle className="h-8 w-8" />
            ) : (
              <Clock className="h-8 w-8 animate-pulse" />
            )}
          </div>

          <h1 className="text-xl font-bold tracking-tight text-white">
            {isApproved
              ? "Access Request Approved!"
              : isRejected
              ? "Access Request Declined"
              : "Access Request Under Review"}
          </h1>
          <p className="mt-1 text-xs text-slate-400">
            {username ? `Account: ${username}` : "Your registration has been submitted to system administrators."}
          </p>
        </div>

        {/* Status Card */}
        <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400">Application Status</span>
            <span
              className={`rounded-full px-2.5 py-0.5 font-bold uppercase tracking-wider text-[10px] ${
                isApproved
                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                  : isRejected
                  ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                  : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
              }`}
            >
              {statusData?.status || "PENDING"}
            </span>
          </div>

          {statusData?.requested_role && (
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Requested Role</span>
              <span className="font-semibold text-white uppercase">{statusData.requested_role}</span>
            </div>
          )}

          {statusData?.created_at && (
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Submitted</span>
              <span className="text-slate-300">{new Date(statusData.created_at).toLocaleString()}</span>
            </div>
          )}

          {statusData?.reviewer_username && (
            <div className="flex items-center justify-between text-xs border-t border-slate-800 pt-2">
              <span className="text-slate-400">Reviewed By</span>
              <span className="text-slate-300">{statusData.reviewer_username}</span>
            </div>
          )}

          {statusData?.review_reason && (
            <div className="rounded-lg bg-slate-800/80 p-2.5 text-xs text-slate-300 border border-slate-700">
              <span className="font-semibold text-slate-400 block mb-1">Reviewer Note:</span>
              <p className="italic">{statusData.review_reason}</p>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="mt-6 space-y-3">
          {isApproved ? (
            <Link
              to="/login"
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 py-3 text-sm font-semibold text-white shadow-lg shadow-emerald-500/20 hover:from-emerald-500 hover:to-teal-500"
            >
              <span>Sign In to Your Account</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
          ) : isRejected ? (
            <div className="space-y-2">
              <p className="text-center text-xs text-slate-400">
                If you believe this was an error, please reach out to your administrator.
              </p>
              <Link
                to="/request-access"
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-700 py-2.5 text-xs font-semibold text-white hover:bg-slate-600"
              >
                <span>Submit New Request</span>
              </Link>
            </div>
          ) : (
            <button
              type="button"
              onClick={fetchStatus}
              disabled={refreshing}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-600 bg-slate-800/80 py-2.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin text-blue-400" : ""}`} />
              <span>Check Status Now</span>
            </button>
          )}

          <div className="text-center pt-2">
            <Link to="/login" className="text-xs text-slate-400 hover:text-white underline">
              Return to Login Page
            </Link>
          </div>
        </div>

      </div>
    </div>
  );
}
