import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { FileSpreadsheet, Share2, Mail, AlertTriangle, Download, CheckCircle2, XCircle } from "lucide-react";
import { useWorkflow } from "../context/WorkflowContext.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { getRefinementGrid, finalizeExport, downloadExport } from "../services/api";

export default function ExportPage() {
  const { sessionId } = useWorkflow();
  const { hasAtLeast } = useAuth();

  const [grid, setGrid] = useState([]);
  const [gridLoading, setGridLoading] = useState(false);
  const [gridError, setGridError] = useState(null);

  const [syncToSharePoint, setSyncToSharePoint] = useState(false);
  const [emailInput, setEmailInput] = useState("");

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);
  const [exportResult, setExportResult] = useState(null);
  const [downloadError, setDownloadError] = useState(null);

  const refreshGrid = useCallback(() => {
    if (!sessionId) return;
    setGridLoading(true);
    getRefinementGrid(sessionId)
      .then((res) => setGrid(res.data))
      .catch((err) => setGridError(err.response?.data?.detail || "Could not load the grid."))
      .finally(() => setGridLoading(false));
  }, [sessionId]);

  useEffect(() => {
    refreshGrid();
  }, [refreshGrid]);

  const parsedEmails = emailInput
    .split(/[,\s]+/)
    .map((e) => e.trim())
    .filter(Boolean);

  const handleExport = async () => {
    setExporting(true);
    setExportError(null);
    try {
      const res = await finalizeExport({
        sessionId,
        syncToSharePoint,
        emailDistributionList: parsedEmails,
      });
      setExportResult(res.data);
    } catch (err) {
      setExportError(err.response?.data?.detail || "Export failed.");
    } finally {
      setExporting(false);
    }
  };

  const handleDownload = async () => {
    setDownloadError(null);
    try {
      await downloadExport(sessionId);
    } catch (err) {
      setDownloadError(err.response?.data?.detail || "Download failed.");
    }
  };

  if (!sessionId) {
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Step 4 — Export, Sync &amp; Notify</h2>
        <div className="flex items-start gap-2 rounded-md bg-amber-50 p-4 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            No confirmed session yet. Go back to{" "}
            <Link to="/gatekeeper" className="underline">
              Step 2 — Gatekeeper
            </Link>{" "}
            and confirm scope first.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Step 4 — Export, Sync &amp; Notify</h2>
        <p className="text-sm text-slate-500">
          Compile the Refinement Grid into a downloadable Excel workbook,
          optionally syncing to SharePoint and emailing a summary.
        </p>
      </div>

      {gridError && (
        <div className="flex items-start gap-2 rounded-md bg-red-50 p-3 text-sm text-red-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{gridError}</span>
        </div>
      )}

      {!gridLoading && grid.length === 0 && !gridError && (
        <div className="flex items-start gap-2 rounded-md bg-amber-50 p-4 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            The Refinement Grid is empty for this session. Go back to{" "}
            <Link to="/refinement" className="underline">
              Step 3 — Refinement
            </Link>{" "}
            and generate or add at least one scenario before exporting.
          </span>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        {/* --- Excel Export --- */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <FileSpreadsheet className="mb-2 h-6 w-6 text-emerald-600" />
          <p className="font-medium">Excel Export</p>
          <p className="mb-3 text-sm text-slate-500">
            {grid.length > 0
              ? `${grid.length} scenario${grid.length === 1 ? "" : "s"} ready to compile.`
              : "No scenarios yet."}
          </p>

          <button
            onClick={handleExport}
            disabled={exporting || grid.length === 0 || !hasAtLeast("approver")}
            className="w-full rounded-md bg-brand-500 px-3 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {exporting ? "Compiling…" : "Generate Excel workbook"}
          </button>

          {!hasAtLeast("approver") && (
            <p className="mt-2 text-xs text-slate-400">
              Exporting requires the 'approver' role or higher.
            </p>
          )}

          {exportError && (
            <div className="mt-3 flex items-start gap-2 rounded-md bg-red-50 p-3 text-xs text-red-700">
              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
              <span>{exportError}</span>
            </div>
          )}

          {exportResult && (
            <div className="mt-3 space-y-2 rounded-md bg-emerald-50 p-3 text-xs text-emerald-800">
              <div className="flex items-start gap-2">
                <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0" />
                <span>{exportResult.message}</span>
              </div>
              <p className="truncate text-slate-500" title={exportResult.filename}>
                {exportResult.filename}
              </p>
              <button
                onClick={handleDownload}
                className="flex w-full items-center justify-center gap-1 rounded-md border border-emerald-300 bg-white px-3 py-1.5 font-medium text-emerald-700 hover:bg-emerald-50"
              >
                <Download className="h-3 w-3" />
                Download workbook
              </button>
              {downloadError && (
                <p className="text-red-600">{downloadError}</p>
              )}
            </div>
          )}
        </div>

        {/* --- SharePoint Sync --- */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <Share2 className="mb-2 h-6 w-6 text-brand-600" />
          <p className="font-medium">SharePoint Sync</p>
          <label className="mt-2 flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={syncToSharePoint}
              onChange={(e) => setSyncToSharePoint(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300"
            />
            Sync workbook to SharePoint on export
          </label>
          <p className="mt-2 text-xs text-slate-400">
            Requires SHAREPOINT_TENANT_ID/CLIENT_ID/CLIENT_SECRET/SITE_URL
            configured on the backend. If sync fails, the Excel file is
            still generated and downloadable — only the sync step is
            affected.
          </p>

          {exportResult && syncToSharePoint && (
            <div className="mt-3 text-xs">
              {exportResult.sharepoint_url ? (
                <div className="flex items-start gap-2 rounded-md bg-emerald-50 p-3 text-emerald-800">
                  <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0" />
                  <a href={exportResult.sharepoint_url} className="underline" target="_blank" rel="noreferrer">
                    View in SharePoint
                  </a>
                </div>
              ) : exportResult.sharepoint_error ? (
                <div className="flex items-start gap-2 rounded-md bg-red-50 p-3 text-red-700">
                  <XCircle className="mt-0.5 h-3 w-3 shrink-0" />
                  <span>{exportResult.sharepoint_error}</span>
                </div>
              ) : null}
            </div>
          )}
        </div>

        {/* --- Email Notification --- */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <Mail className="mb-2 h-6 w-6 text-orange-600" />
          <p className="font-medium">Email Notification</p>
          <input
            type="text"
            value={emailInput}
            onChange={(e) => setEmailInput(e.target.value)}
            placeholder="jane@example.com, sam@example.com"
            className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs"
          />
          <p className="mt-2 text-xs text-slate-400">
            Comma or space separated. Leave blank to skip. Requires
            SMTP_HOST configured on the backend.
          </p>

          {exportResult && parsedEmails.length > 0 && (
            <div className="mt-3 text-xs">
              {exportResult.email_sent ? (
                <div className="flex items-start gap-2 rounded-md bg-emerald-50 p-3 text-emerald-800">
                  <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0" />
                  <span>Sent to {parsedEmails.length} recipient(s).</span>
                </div>
              ) : exportResult.email_error ? (
                <div className="flex items-start gap-2 rounded-md bg-red-50 p-3 text-red-700">
                  <XCircle className="mt-0.5 h-3 w-3 shrink-0" />
                  <span>{exportResult.email_error}</span>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
