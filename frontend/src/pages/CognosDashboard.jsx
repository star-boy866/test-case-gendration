import { useState, useRef, useEffect } from "react";
import { UploadCloud, FileText, CheckCircle2, Download, Loader2, AlertTriangle, Image as ImageIcon } from "lucide-react";
import { uploadCognosDocument, downloadCognosExport, api } from "../services/api";

function EvidenceImage({ url, alt, className, onClick }) {
  const [objectUrl, setObjectUrl] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    if (!url) return;

    // Use axios to fetch the image to include the Authorization header automatically
    // Strip "/api" from url since baseURL is "/api"
    const apiPath = url.startsWith("/api") ? url.substring(4) : url;

    api.get(apiPath, { responseType: 'blob' })
      .then((res) => {
        if (!active) return;
        const blobUrl = URL.createObjectURL(res.data);
        setObjectUrl(blobUrl);
      })
      .catch((err) => {
        if (!active) return;
        console.error(`Failed to load evidence image (${url}):`, err.response?.status || err.message);
        setError(true);
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-slate-50 border border-slate-200 rounded-md text-slate-400">
        <AlertTriangle className="h-6 w-6 mb-2 text-amber-500" />
        <span className="text-sm font-medium">Evidence unavailable</span>
      </div>
    );
  }

  if (!objectUrl) {
    return (
      <div className="flex items-center justify-center h-32 bg-slate-50 rounded-md animate-pulse">
        <ImageIcon className="h-6 w-6 text-slate-300" />
      </div>
    );
  }

  return <img src={objectUrl} alt={alt} className={className} onClick={onClick} />;
}

function SemanticProofCard({ ev, onZoom }) {
  return (
    <div className="border border-blue-200 rounded-lg overflow-hidden shadow-sm">
      <div className="flex items-center justify-between px-3 py-2 bg-blue-700 text-white">
        <span className="text-xs font-bold uppercase tracking-widest opacity-90">Semantic DSD Proof</span>
        <span className="text-xs font-medium bg-blue-900/40 px-2 py-0.5 rounded-full">
          {ev.page_number ? `Page ${ev.page_number} \u2022 ` : ""}{ev.section}
        </span>
      </div>
      <div className="p-2 bg-white">
        {ev.snapshot_url ? (
          <EvidenceImage
            url={ev.snapshot_url}
            alt={ev.description}
            className="w-full h-auto border border-blue-100 rounded cursor-zoom-in hover:opacity-90 transition-opacity"
            onClick={(e) => { e.stopPropagation(); onZoom(ev.snapshot_url); }}
          />
        ) : (
          <div className="text-xs text-slate-400 italic p-4 text-center">Image not available</div>
        )}
      </div>
      <div className="flex items-center justify-between px-3 py-2 border-t border-blue-100 bg-blue-50">
        <p className="text-xs text-slate-600">{ev.description}</p>
        {ev.snapshot_url && (
          <button
            className="text-xs font-medium text-blue-700 hover:text-blue-900 underline ml-3 shrink-0"
            onClick={(e) => { e.stopPropagation(); onZoom(ev.snapshot_url); }}
          >
            Open Full Size
          </button>
        )}
      </div>
    </div>
  );
}

function SourceDsdSnapshotCard({ ev }) {
  const [loading, setLoading] = useState(false);
  const blobUrlRef = useRef(null);
  const [snapshotObjectUrl, setSnapshotObjectUrl] = useState(null);
  const [snapshotFailed, setSnapshotFailed] = useState(false);

  useEffect(() => {
    let active = true;
    const runIdMatch = ev.source_document_url ? ev.source_document_url.match(/runs\/(\d+)/) : null;
    const runId = ev.run_id || (runIdMatch ? runIdMatch[1] : null);
    
    if (!runId) {
      setSnapshotFailed(true);
      return;
    }

    api.get(`/cognos/runs/${runId}/source-snapshot`, { 
      responseType: 'blob',
      params: {
        evidence_id: ev.evidence_id || '',
        section: ev.section || ''
      }
    })
      .then((res) => {
        if (!active) return;
        setSnapshotObjectUrl(URL.createObjectURL(res.data));
      })
      .catch((err) => {
        if (!active) return;
        setSnapshotFailed(true);
      });
    
    return () => {
      active = false;
    };
  }, [ev.run_id, ev.source_document_url]);

  useEffect(() => {
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
      }
      if (snapshotObjectUrl) {
        URL.revokeObjectURL(snapshotObjectUrl);
      }
    };
  }, [snapshotObjectUrl]);

  const handleOpenSourceDoc = async (e) => {
    e.stopPropagation();
    if (!ev.source_document_url) {
      alert("Source document download is not available yet.");
      return;
    }

    if (blobUrlRef.current) {
      window.open(blobUrlRef.current, "_blank");
      return;
    }

    setLoading(true);
    try {
      const apiPath = ev.source_document_url.startsWith("/api") ? ev.source_document_url.substring(4) : ev.source_document_url;
      const res = await api.get(apiPath, { responseType: 'blob' });
      
      const blobUrl = URL.createObjectURL(res.data);
      blobUrlRef.current = blobUrl;
      window.open(blobUrl, "_blank");
    } catch (err) {
      console.error("Failed to fetch source document:", err);
      alert("Failed to load source document.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border border-emerald-200 rounded-lg overflow-hidden shadow-sm">
      <div className="flex items-center justify-between px-3 py-2 bg-emerald-700 text-white">
        <span className="text-xs font-bold uppercase tracking-widest opacity-90">Source DSD Snapshot</span>
        <span className="text-xs font-medium bg-emerald-900/40 px-2 py-0.5 rounded-full">
          {ev.page_number ? `Page ${ev.page_number} \u2022 ` : ""}{ev.section}
        </span>
      </div>
      <div className="p-6 bg-slate-50 flex flex-col items-center justify-center border-b border-emerald-100">
        {snapshotObjectUrl ? (
          <div className="w-full mb-4">
            <img 
              src={snapshotObjectUrl} 
              alt="Source DSD Snapshot" 
              className="w-full h-auto border border-slate-200 rounded shadow-sm"
            />
          </div>
        ) : (
          <>
            <FileText className="h-10 w-10 text-slate-300 mb-3" />
            <h4 className="text-sm font-semibold text-slate-700 mb-1">Source DSD document</h4>
            <p className="text-xs text-slate-500 mb-4">Section: {ev.section}</p>
            <p className="text-xs font-medium text-amber-600 bg-amber-50 px-3 py-1 rounded-full border border-amber-200 mb-4">
              Visual source preview unavailable
            </p>
          </>
        )}
        <button
          className="inline-flex items-center gap-2 rounded-md bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50 transition-colors disabled:opacity-50"
          disabled={loading}
          onClick={handleOpenSourceDoc}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {loading ? "Loading..." : "Open Source Document"}
        </button>
      </div>
      <div className="flex items-center justify-between px-3 py-2 bg-emerald-50">
        <p className="text-xs text-slate-600">{ev.description}</p>
      </div>
    </div>
  );
}

function GenericEvidenceCard({ ev, onZoom }) {
  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden shadow-sm">
      <div className="flex items-center justify-between px-3 py-2 bg-slate-100">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          {(ev.evidence_type || "").replace(/_/g, " ")}
        </span>
        <span className="text-xs text-slate-500">
          {ev.page_number ? `Page ${ev.page_number} \u2022 ` : ""}{ev.section}
        </span>
      </div>
      <div className="p-2 bg-white">
        {ev.snapshot_url ? (
          <EvidenceImage
            url={ev.snapshot_url}
            alt={ev.description}
            className="w-full h-auto border border-slate-100 rounded cursor-zoom-in hover:opacity-90 transition-opacity"
            onClick={(e) => { e.stopPropagation(); onZoom(ev.snapshot_url); }}
          />
        ) : (
          <div className="text-xs text-slate-400 italic p-4 text-center">Image not available</div>
        )}
      </div>
      <p className="text-xs text-slate-500 px-3 py-2 border-t border-slate-100">{ev.description}</p>
    </div>
  );
}

function EvidencePanel({ evidenceRefs }) {
  const [zoomImage, setZoomImage] = useState(null);

  const proof = (evidenceRefs || []).filter(ev => ev.evidence_type === "DSD_SEMANTIC_PROOF");
  const snapshots = (evidenceRefs || []).filter(ev => ev.evidence_type === "SOURCE_DSD_SNAPSHOT");
  const others = (evidenceRefs || []).filter(
    ev => ev.evidence_type !== "DSD_SEMANTIC_PROOF" && ev.evidence_type !== "SOURCE_DSD_SNAPSHOT"
  );

  return (
    <>
      <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
        {proof.map((ev, idx) => (
          <SemanticProofCard key={`proof-${idx}`} ev={ev} onZoom={setZoomImage} />
        ))}
        {snapshots.map((ev, idx) => (
          <SourceDsdSnapshotCard key={`snap-${idx}`} ev={ev} />
        ))}
        {others.map((ev, idx) => (
          <GenericEvidenceCard key={`other-${idx}`} ev={ev} onZoom={setZoomImage} />
        ))}
        {(evidenceRefs || []).length === 0 && (
          <div className="p-6 bg-white rounded-md border border-slate-200 text-center">
            <p className="text-sm text-slate-500 italic">No DSD evidence extracted for this scenario.</p>
          </div>
        )}
      </div>

      {/* Zoom Modal */}
      {zoomImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/90 p-4 backdrop-blur-sm"
          onClick={() => setZoomImage(null)}
        >
          <div className="relative max-w-7xl max-h-screen flex flex-col items-center">
            <button
              className="absolute -top-12 right-0 text-white p-2 hover:text-slate-300 transition-colors"
              onClick={() => setZoomImage(null)}
            >
              <span className="text-sm uppercase tracking-widest font-semibold flex items-center gap-2">Close ✕</span>
            </button>
            <EvidenceImage url={zoomImage} alt="Zoomed evidence" className="max-w-full max-h-[90vh] object-contain rounded-md shadow-2xl" />
          </div>
        </div>
      )}
    </>
  );
}

function TestCaseRow({ tc }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        className="hover:bg-slate-50 cursor-pointer transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-4 py-3 font-medium text-slate-900">{tc.test_case_id}</td>
        <td className="px-4 py-3">
          <span className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
            {tc.category}
          </span>
        </td>
        <td className="px-4 py-3 text-slate-500">{tc.requirement_id}</td>
        <td className="px-4 py-3 text-slate-700 line-clamp-1">{tc.test_case_title}</td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan="4" className="bg-slate-50 px-6 py-4 border-b border-slate-200 shadow-inner">
            <div className="grid grid-cols-2 gap-6">
                {/* Details */}
                <div className="space-y-5">
                  <div>
                    <h4 className="font-semibold text-slate-900 text-sm border-b pb-1 mb-2">Objective</h4>
                    <p className="text-slate-700 text-sm">{tc.objective}</p>
                  </div>
                  <div>
                    <h4 className="font-semibold text-slate-900 text-sm border-b pb-1 mb-2">Test Steps</h4>
                    <pre className="text-slate-700 text-sm whitespace-pre-wrap font-sans bg-white p-3 rounded-md border border-slate-200">{tc.test_steps}</pre>
                  </div>
                  <div>
                    <h4 className="font-semibold text-slate-900 text-sm border-b pb-1 mb-2">Expected Result</h4>
                    <p className="text-slate-700 text-sm">{tc.expected_result}</p>
                  </div>
                </div>

                {/* Evidence */}
                <div>
                  <h4 className="font-semibold text-slate-900 text-sm border-b pb-1 mb-3">DSD Evidence</h4>
                  <EvidencePanel evidenceRefs={tc.evidence_references || []} />
                </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}


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
                Parsed {result.requirement_count ?? 0} requirements and generated {result.test_case_count ?? 0} test cases in {(result.summary?.execution_time_seconds || 0).toFixed(1)} seconds.
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
              <span>Generated Test Suite ({result.test_case_count ?? 0} Cases)</span>
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
                    <TestCaseRow key={tc.test_case_id} tc={tc} />
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
