import { useState, useRef } from "react";
import { UploadCloud, FileText, CheckCircle2, Download, Loader2, AlertTriangle } from "lucide-react";
import { uploadCognosDocument, downloadCognosExport } from "../services/api";

export default function CognosDashboard() {
  const [file, setFile] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const [isDownloading, setIsDownloading] = useState(false);

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      if (!selected.name.toLowerCase().endsWith(".docx")) {
        setError("Please upload a standard Word Document (.docx).");
        setFile(null);
      } else {
        setError("");
        setFile(selected);
        setResult(null);
      }
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsProcessing(true);
    setError("");
    try {
      const response = await uploadCognosDocument({ file });
      setResult(response.data);
    } catch (err) {
      setError(
        err.response?.data?.detail || "An error occurred during generation."
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownload = async () => {
    if (!result?.run_id) return;
    setIsDownloading(true);
    try {
      await downloadCognosExport(result.run_id);
    } catch (err) {
      setError("Failed to download export. Please try again.");
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-900">
          Cognos Report Test Generator
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Upload a Cognos Report Definition (DOCX) to automatically extract requirements
          and generate traceable manual test cases.
        </p>
      </div>

      {/* Upload Zone */}
      {!result && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div
            className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 ${
              file ? "border-brand-300 bg-brand-50" : "border-slate-300 bg-slate-50"
            }`}
          >
            <input
              type="file"
              accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="hidden"
              ref={fileInputRef}
              onChange={handleFileChange}
            />

            {!file ? (
              <>
                <UploadCloud className="h-10 w-10 text-slate-400 mb-4" />
                <p className="text-sm font-medium text-slate-900">
                  Select a Cognos DOCX file to upload
                </p>
                <p className="text-xs text-slate-500 mt-1 mb-4">
                  or drag and drop it here
                </p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-md bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50"
                >
                  Browse Files
                </button>
              </>
            ) : (
              <>
                <FileText className="h-10 w-10 text-brand-600 mb-4" />
                <p className="text-sm font-medium text-slate-900">{file.name}</p>
                <p className="text-xs text-slate-500 mt-1 mb-4">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => setFile(null)}
                    className="rounded-md bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50"
                  >
                    Change File
                  </button>
                  <button
                    onClick={handleUpload}
                    disabled={isProcessing}
                    className="inline-flex items-center gap-2 rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-500 disabled:opacity-70"
                  >
                    {isProcessing ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Processing Pipeline...
                      </>
                    ) : (
                      "Generate Test Cases"
                    )}
                  </button>
                </div>
              </>
            )}
          </div>

          {error && (
            <div className="mt-4 flex items-start gap-2 rounded-md bg-red-50 p-3 text-sm text-red-700">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>{error}</p>
            </div>
          )}
        </div>
      )}

      {/* Results View */}
      {result && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 text-green-700 font-medium mb-1">
                <CheckCircle2 className="h-5 w-5" />
                Pipeline Completed Successfully
              </div>
              <h3 className="text-lg font-bold text-slate-900 mt-2">
                {result.report_id}
              </h3>
              <p className="text-sm text-slate-500 mt-1">
                Parsed {result.summary?.total_requirements || 0} requirements and generated {result.summary?.test_cases_generated || 0} test cases in {(result.summary?.execution_time_seconds || 0).toFixed(1)} seconds.
              </p>
            </div>
            
            <button
              onClick={handleDownload}
              disabled={isDownloading}
              className="inline-flex items-center gap-2 rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-green-500 disabled:opacity-70"
            >
              {isDownloading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Download Excel Workbook
            </button>
          </div>

          {/* Test Case Data Grid */}
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="border-b border-slate-200 bg-slate-50 px-4 py-3 font-semibold text-slate-900 flex justify-between items-center">
              <span>Generated Test Suite ({result.summary?.test_cases_generated || 0} Cases)</span>
              <button 
                onClick={() => {setResult(null); setFile(null);}}
                className="text-sm text-brand-600 hover:text-brand-800"
              >
                Upload Another Report
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm text-left">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-3 font-medium text-slate-500">Test Case ID</th>
                    <th className="px-4 py-3 font-medium text-slate-500">Category</th>
                    <th className="px-4 py-3 font-medium text-slate-500">Requirement ID</th>
                    <th className="px-4 py-3 font-medium text-slate-500">Title</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {result.test_cases?.map((tc) => (
                    <tr key={tc.test_case_id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-medium text-slate-900">{tc.test_case_id}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
                          {tc.category}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-500">{tc.requirement_id}</td>
                      <td className="px-4 py-3 text-slate-700 line-clamp-1">{tc.test_case_title}</td>
                    </tr>
                  ))}
                  {(!result.test_cases || result.test_cases.length === 0) && (
                    <tr>
                      <td colSpan="4" className="px-4 py-8 text-center text-slate-500">
                        No test cases generated.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
