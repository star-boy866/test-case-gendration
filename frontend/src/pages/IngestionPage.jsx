import { useState } from "react";
import { Link } from "react-router-dom";
import { UploadCloud, AlertTriangle, CheckCircle2, ArrowRight } from "lucide-react";
import { uploadDocument } from "../services/api";
import { useWorkflow } from "../context/WorkflowContext.jsx";

export default function IngestionPage() {
  const { reportId, setReportId, crId, setCrId } = useWorkflow();
  const [fileName, setFileName] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!reportId.trim()) {
      setError("Enter a Report ID / Functional Area before uploading.");
      e.target.value = "";
      return;
    }

    setFileName(file.name);
    setUploading(true);
    setError(null);
    setResult(null);

    try {
      const res = await uploadDocument({ file, reportId, crId });
      setResult(res.data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Upload failed — is the backend running on :8000?"
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Step 1 — Ingestion</h2>
        <p className="text-sm text-slate-500">
          Upload an RDD or LDM (.xlsx, .csv, .docx, .pdf). SharePoint import
          lands in Phase 8.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">
            Report ID / Functional Area *
          </span>
          <input
            type="text"
            value={reportId}
            onChange={(e) => setReportId(e.target.value)}
            placeholder="e.g. RPT-Swipe-Card-Tracking"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-slate-700">
            CR ID (optional)
          </span>
          <input
            type="text"
            value={crId}
            onChange={(e) => setCrId(e.target.value)}
            placeholder="e.g. CR-2026-0142"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
      </div>

      <label
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 text-center ${
          reportId.trim()
            ? "border-slate-300 bg-white hover:border-brand-500"
            : "border-slate-200 bg-slate-100 opacity-60"
        }`}
      >
        <UploadCloud className="mb-2 h-8 w-8 text-slate-400" />
        <span className="text-sm text-slate-600">
          {reportId.trim()
            ? "Click to select a file to parse"
            : "Enter a Report ID above to enable upload"}
        </span>
        <input
          type="file"
          className="hidden"
          onChange={handleFileChange}
          disabled={!reportId.trim() || uploading}
          accept=".xlsx,.xls,.csv,.docx,.pdf"
        />
      </label>

      {fileName && (
        <div className="rounded-md bg-white p-4 text-sm shadow-sm">
          <p className="mb-2">
            <span className="font-medium">File:</span> {fileName}
          </p>

          {uploading && <p className="text-slate-500">Parsing…</p>}

          {error && (
            <div className="flex items-start gap-2 rounded-md bg-red-50 p-3 text-red-700">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {result && result.parse_status === "insufficient_metadata" && (
            <div className="flex items-start gap-2 rounded-md bg-amber-50 p-3 text-amber-800">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{result.message}</span>
            </div>
          )}

          {result && result.parse_status === "parsed" && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 rounded-md bg-emerald-50 p-3 text-emerald-800">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>
                  Extracted {result.counts.tables} tables,{" "}
                  {result.counts.columns} columns, {result.counts.joins}{" "}
                  joins, {result.counts.valid_values} valid values,{" "}
                  {result.counts.business_rules} business rules.
                </span>
              </div>
              {result.counts.unstructured_notes > 0 && (
                <p className="text-xs text-slate-500">
                  {result.counts.unstructured_notes} block(s) of free-form
                  text were captured for manual review — not auto-converted
                  into business rules.
                </p>
              )}
              {result.kb_invalidated_prior_version && (
                <p className="text-xs text-amber-700">
                  Note: this file replaced a previous version of the
                  Knowledge Base for this Report ID — old data (and any
                  prior Gatekeeper confirmation) was invalidated.
                </p>
              )}
              {result.warnings?.length > 0 && (
                <ul className="list-inside list-disc text-xs text-slate-500">
                  {result.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              )}

              <Link
                to="/gatekeeper"
                className="inline-flex items-center gap-1 rounded-md bg-brand-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-600"
              >
                Continue to Gatekeeper <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
