import React, { useState, useEffect, useRef, useMemo } from "react";
import { 
  FileText, Loader2, AlertTriangle, Image as ImageIcon, 
  Search, ChevronRight, X, ChevronLeft, ChevronDown,
  CheckCircle2, AlertCircle, Clock, Database, Layers,
  Link as LinkIcon, Info, Code, FileCheck, ArrowRight,
  ChevronRight as ChevronRightIcon, RefreshCw
} from "lucide-react";
import { api } from "../../services/api";
import InteractiveEvidenceViewer from "./InteractiveEvidenceViewer";

// ─── Error Boundary ───────────────────────────────────────────────────────────

class ScenarioErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ScenarioErrorBoundary caught an error:", error, errorInfo);
    this.setState({ errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 bg-red-50 border border-red-200 rounded-lg text-red-800 my-4 shadow-sm">
          <div className="flex items-center gap-2 font-bold text-base text-red-900 mb-2">
            <AlertTriangle className="h-5 w-5 text-red-600 shrink-0" />
            Unable to render this test scenario
          </div>
          {this.props.testCaseId && (
            <p className="text-xs font-semibold text-slate-700 mb-2">
              Test Case ID: <span className="font-mono bg-white px-2 py-0.5 border border-slate-200 rounded">{this.props.testCaseId}</span>
            </p>
          )}
          <p className="text-xs font-mono bg-red-100/60 p-3 rounded text-red-950 overflow-x-auto whitespace-pre-wrap mb-3 border border-red-200">
            {this.state.error?.toString() || "Unknown error"}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-md shadow-sm transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ─── Helpers & Normalization ──────────────────────────────────────────────────

function parseSteps(test_steps) {
  if (!test_steps) return [];
  if (Array.isArray(test_steps)) return test_steps;
  if (typeof test_steps === "string") {
    return test_steps.split("\n").map(s => s.trim()).filter(Boolean);
  }
  return [String(test_steps)];
}

function extractSql(validation_logic, test_data, validation_sql) {
  if (typeof validation_sql === "string" && validation_sql.trim()) {
    return validation_sql.trim();
  }
  if (typeof validation_logic === "string") {
    const match = validation_logic.match(/```sql\n([\s\S]*?)```/);
    if (match) return match[1].trim();
  }
  if (typeof test_data === "string") {
    const match = test_data.match(/```sql\n([\s\S]*?)```/);
    if (match) return match[1].trim();
  }
  return null;
}

// ─── Evidence Components ──────────────────────────────────────────────────────

function EvidenceImage({ url, alt, className, onClick, onLoaded }) {
  const [objectUrl, setObjectUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    if (!url) {
      setLoading(false);
      setError(true);
      return;
    }

    // Check if url is already a blob URL or data URL
    if (url.startsWith("blob:") || url.startsWith("data:")) {
      setObjectUrl(url);
      setLoading(false);
      setError(false);
      if (onLoaded) onLoaded(url);
      return;
    }

    setLoading(true);
    setError(false);

    const apiPath = url.startsWith("/api") ? url.substring(4) : url;

    api.get(apiPath, { responseType: 'blob' })
      .then((res) => {
        if (!active) return;
        const blobUrl = URL.createObjectURL(res.data);
        setObjectUrl(blobUrl);
        setLoading(false);
        if (onLoaded) onLoaded(blobUrl);
      })
      .catch((err) => {
        if (!active) return;
        console.error(`Failed to load evidence image (${url}):`, err?.response?.status || err?.message);
        setError(true);
        setLoading(false);
      });

    return () => {
      active = false;
      if (objectUrl && !objectUrl.startsWith("data:") && !url.startsWith("blob:")) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [url]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-36 w-full bg-slate-50 rounded-md animate-pulse">
        <div className="flex flex-col items-center gap-1.5 text-slate-400">
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          <span className="text-xs font-medium">Loading proof image...</span>
        </div>
      </div>
    );
  }

  if (error || !objectUrl) {
    return (
      <div className="flex flex-col items-center justify-center p-6 bg-slate-50 border border-slate-200 rounded-md text-slate-400 w-full">
        <AlertTriangle className="h-6 w-6 mb-2 text-amber-500" />
        <span className="text-xs font-medium">Preview unavailable</span>
      </div>
    );
  }

  return (
    <img 
      src={objectUrl} 
      alt={alt || "Evidence"} 
      className={className} 
      onClick={() => onClick && onClick(objectUrl)} 
    />
  );
}

function SemanticProofCard({ ev, onZoom }) {
  const [currentBlobUrl, setCurrentBlobUrl] = useState(null);
  const pageDisplay = ev?.page_display || (ev?.source_pages?.length > 1 ? ev.source_pages.join('–') : ev?.page_number);
  const pageText = pageDisplay ? `Page ${pageDisplay} \u2022 ` : "";
  const sectionText = ev?.section || "Report Layout";

  const handleOpenFull = (e) => {
    e.stopPropagation();
    if (onZoom) {
      onZoom({ imageUrl: currentBlobUrl || ev?.snapshot_url, evidence: ev, title: ev?.description });
    }
  };

  return (
    <div className="border border-blue-200 rounded-lg overflow-hidden shadow-sm h-full flex flex-col bg-white">
      <div className="flex items-center justify-between px-3 py-2 bg-blue-700 text-white shrink-0">
        <span className="text-xs font-bold uppercase tracking-widest opacity-90">Semantic DSD Proof</span>
        <span className="text-xs font-medium bg-blue-900/40 px-2 py-0.5 rounded-full">
          {pageText}{sectionText}
        </span>
      </div>
      <div className="p-2 flex-1 flex items-center justify-center bg-slate-50/50">
        {ev?.snapshot_url ? (
          <EvidenceImage
            url={ev.snapshot_url}
            alt={ev.description || "Semantic Proof"}
            className="w-full h-auto max-h-48 object-contain border border-blue-100 rounded cursor-zoom-in hover:opacity-90 transition-opacity bg-white"
            onLoaded={setCurrentBlobUrl}
            onClick={(blobUrl) => { onZoom && onZoom({ imageUrl: blobUrl || ev.snapshot_url, evidence: ev, title: ev.description }); }}
          />
        ) : (
          <div className="text-xs text-slate-400 italic p-4 text-center">Image not available</div>
        )}
      </div>
      <div className="flex items-center justify-between px-3 py-2 border-t border-blue-100 bg-blue-50 shrink-0">
        <p className="text-xs text-slate-600 truncate mr-2" title={ev?.description || ""}>
          {ev?.description || `Semantic evidence for ${ev?.test_case_id || "test"}`}
        </p>
        {ev?.snapshot_url && (
          <button
            type="button"
            className="text-xs font-semibold text-blue-700 hover:text-blue-900 underline shrink-0"
            onClick={handleOpenFull}
          >
            Open Full Size
          </button>
        )}
      </div>
    </div>
  );
}

function SourceDsdSnapshotCard({ ev, onZoom }) {
  const [loading, setLoading] = useState(false);
  const blobRef = useRef(null);
  const blobUrlRef = useRef(null);
  const previewMetaRef = useRef(null);
  const [snapshotObjectUrl, setSnapshotObjectUrl] = useState(null);
  const [snapshotFailed, setSnapshotFailed] = useState(false);

  useEffect(() => {
    let active = true;
    const runIdMatch = typeof ev?.source_document_url === "string" ? ev.source_document_url.match(/runs\/(\d+)/) : null;
    const runId = ev?.run_id || (runIdMatch ? runIdMatch[1] : null);
    
    if (!runId) {
      setSnapshotFailed(true);
      return;
    }

    setLoading(true);
    setSnapshotFailed(false);

    api.get(`/cognos/runs/${runId}/source-snapshot`, { 
      responseType: 'blob',
      params: {
        evidence_id: ev.evidence_id || '',
        section: ev.section || '',
        methodology: ev.methodology || '',
        target_field: ev.target_field || '',
        evidence_scope: ev.evidence_scope || '',
        test_case_id: ev.test_case_id || ''
      }
    })
      .then(async (res) => {
        if (!active) return;
        const blob = res.data;
        blobRef.current = blob;
        const blobUrl = URL.createObjectURL(blob);
        blobUrlRef.current = blobUrl;

        let sha256 = "N/A";
        try {
          const buffer = await blob.arrayBuffer();
          const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
          sha256 = Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, "0")).join("");
        } catch (e) {
          sha256 = "hash_calc_error";
        }

        previewMetaRef.current = {
          url: blobUrl,
          size: blob.size,
          type: blob.type,
          sha256,
          naturalWidth: 0,
          naturalHeight: 0
        };

        setSnapshotObjectUrl(blobUrl);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setSnapshotFailed(true);
        setLoading(false);
      });
    
    return () => {
      active = false;
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
      }
    };
  }, [ev?.run_id, ev?.source_document_url, ev?.evidence_id, ev?.section, ev?.methodology, ev?.target_field, ev?.evidence_scope]);

  const handleOpenFull = (e) => {
    e.stopPropagation();
    if (snapshotObjectUrl && onZoom) {
      onZoom({
        blob: blobRef.current,
        imageUrl: snapshotObjectUrl,
        evidence: ev,
        title: ev?.description,
        previewMeta: previewMetaRef.current
      });
    }
  };

  const pageDisplay = ev?.page_display || (ev?.source_pages?.length > 1 ? ev.source_pages.join('–') : ev?.page_number);
  const pageText = pageDisplay ? `Page ${pageDisplay} \u2022 ` : "";
  const sectionText = ev?.section || "Source Document";
  let rawScope = ev?.evidence_scope || "";
  if (rawScope === "REPORT_FREQUENCY_SCHEDULING") {
    rawScope = "Frequency & Scheduling";
  } else if (rawScope === "REPORT_HEADER") {
    rawScope = "Report Header";
  } else if (rawScope === "REPORT_SECTION_HEADING") {
    rawScope = "Section Headings";
  } else if (rawScope === "REPORT_SPECIAL_PROCESSING") {
    rawScope = "Special Processing";
  } else if (rawScope === "FULL_REPORT_LAYOUT" || ev?.methodology === "LAYOUT_VALIDATION") {
    rawScope = "Full Page";
  }
  const isLayoutVal = ev?.methodology === "LAYOUT_VALIDATION" || rawScope === "Full Page";
  const scopeDetail = isLayoutVal 
    ? "Full Page" 
    : ((rawScope && rawScope !== ev?.section) 
        ? rawScope 
        : (ev?.target_field && ev.target_field !== ev?.section ? ev.target_field : ""));
  const scopeText = scopeDetail ? ` \u2022 ${scopeDetail}` : "";

  return (
    <div className="border border-emerald-200 rounded-lg overflow-hidden shadow-sm h-full flex flex-col bg-white">
      <div className="flex items-center justify-between px-3 py-2 bg-emerald-700 text-white shrink-0">
        <span className="text-xs font-bold uppercase tracking-widest opacity-90">Source DSD Snapshot</span>
        <span className="text-xs font-medium bg-emerald-900/40 px-2 py-0.5 rounded-full truncate max-w-[320px]" title={`${pageText}${sectionText}${scopeText}`}>
          {pageText}{sectionText}{scopeText}
        </span>
      </div>
      <div className={`${isLayoutVal ? 'p-2.5' : 'p-4'} flex-1 flex flex-col items-center justify-center border-b border-emerald-100 bg-slate-50/50 relative overflow-hidden`}>
        {snapshotObjectUrl ? (
          <div className="w-full flex items-center justify-center">
            <img 
              src={snapshotObjectUrl} 
              alt="Source DSD Snapshot" 
              className={
                isLayoutVal
                  ? "source-dsd-full-page-preview w-full h-auto max-w-full block rounded border border-slate-200 shadow-sm bg-white cursor-zoom-in hover:opacity-95 transition-opacity"
                  : "max-h-48 object-contain border border-slate-200 rounded shadow-sm bg-white cursor-zoom-in hover:opacity-95 transition-opacity"
              }
              onLoad={(e) => {
                const nw = e.target.naturalWidth;
                const nh = e.target.naturalHeight;
                if (previewMetaRef.current) {
                  previewMetaRef.current.naturalWidth = nw;
                  previewMetaRef.current.naturalHeight = nh;
                }
                console.log({
                  area: "PREVIEW",
                  src: e.target.src,
                  size: blobRef.current?.size,
                  sha256: previewMetaRef.current?.sha256,
                  naturalWidth: nw,
                  naturalHeight: nh
                });
              }}
              onClick={() => onZoom && onZoom({
                blob: blobRef.current,
                imageUrl: snapshotObjectUrl,
                evidence: ev,
                title: ev?.description,
                previewMeta: previewMetaRef.current
              })}
            />
          </div>
        ) : snapshotFailed ? (
          <div className="flex flex-col items-center">
            <FileText className="h-8 w-8 text-slate-300 mb-2" />
            <p className="text-xs font-medium text-amber-600 bg-amber-50 px-3 py-1 rounded-full border border-amber-200 text-center">
              Visual source preview unavailable
            </p>
          </div>
        ) : (
          <div className="flex items-center justify-center h-36 w-full bg-slate-50 rounded-md animate-pulse">
            <div className="flex flex-col items-center gap-1.5 text-slate-400">
              <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
              <span className="text-xs font-medium">Loading source snapshot...</span>
            </div>
          </div>
        )}
      </div>
      <div className="px-3 py-2 bg-emerald-50 shrink-0 flex items-center justify-between gap-2">
        <p className="text-xs text-slate-600 truncate" title={ev?.description || ""}>
          {ev?.description || "Source document excerpt"}
        </p>
        <button
          type="button"
          className="inline-flex shrink-0 items-center gap-1.5 rounded bg-white px-2 py-1 text-xs font-medium text-emerald-700 shadow-sm ring-1 ring-inset ring-emerald-300 hover:bg-emerald-50 transition-colors disabled:opacity-50"
          disabled={!snapshotObjectUrl}
          onClick={handleOpenFull}
        >
          Open Full Size
        </button>
      </div>
    </div>
  );
}

function GenericEvidenceCard({ ev, onZoom }) {
  const pageDisplay = ev?.page_display || (ev?.source_pages?.length > 1 ? ev.source_pages.join('–') : ev?.page_number);
  const pageText = pageDisplay ? `Page ${pageDisplay} \u2022 ` : "";
  const sectionText = ev?.section || "Source Document";
  const typeText = (ev?.evidence_type || "Evidence").replace(/_/g, " ");

  const handleOpenFull = (e) => {
    e.stopPropagation();
    if (ev?.snapshot_url && onZoom) {
      onZoom({ imageUrl: ev.snapshot_url, evidence: ev, title: ev?.description });
    }
  };

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden shadow-sm h-full flex flex-col bg-white">
      <div className="flex items-center justify-between px-3 py-2 bg-slate-100 shrink-0">
        <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
          {typeText}
        </span>
        <span className="text-xs text-slate-500">
          {pageText}{sectionText}
        </span>
      </div>
      <div className="p-2 flex-1 flex items-center justify-center bg-slate-50/50">
        {ev?.snapshot_url ? (
          <EvidenceImage
            url={ev.snapshot_url}
            alt={ev?.description || "Evidence snapshot"}
            className="w-full h-auto max-h-48 object-contain border border-slate-100 rounded cursor-zoom-in hover:opacity-90 transition-opacity bg-white"
            onClick={(e) => { e.stopPropagation(); onZoom && onZoom({ imageUrl: ev.snapshot_url, evidence: ev, title: ev?.description }); }}
          />
        ) : (
          <div className="text-xs text-slate-400 italic p-4 text-center">Image not available</div>
        )}
      </div>
      <div className="flex items-center justify-between px-3 py-2 border-t border-slate-100 bg-slate-50 shrink-0">
        <p className="text-xs text-slate-500 truncate mr-2" title={ev?.description || ""}>
          {ev?.description || "No description provided"}
        </p>
        {ev?.snapshot_url && (
          <button
            type="button"
            className="text-xs font-semibold text-slate-600 hover:text-slate-900 underline shrink-0"
            onClick={handleOpenFull}
          >
            Open Full Size
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Inner Accordion Section ──────────────────────────────────────────────────

function CollapsibleSection({ title, children, defaultOpen = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden mb-4 bg-white shadow-sm">
      <button 
        type="button"
        onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }}
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-50/80 hover:bg-slate-100 transition-colors text-left font-medium text-slate-800"
      >
        <span className="font-semibold text-sm text-slate-800 flex items-center gap-2">
          {isOpen ? <ChevronDown className="h-4 w-4 text-slate-500" /> : <ChevronRightIcon className="h-4 w-4 text-slate-500" />}
          {title}
        </span>
      </button>
      {isOpen && (
        <div className="p-4 border-t border-slate-200">
          {children}
        </div>
      )}
    </div>
  );
}

// ─── Expanded Scenario Content ────────────────────────────────────────────────

function ScenarioDetailContent({ 
  tc, 
  selectedIndex, 
  totalCount, 
  onPrev, 
  onNext, 
  setZoomImage 
}) {
  const steps = parseSteps(tc?.test_steps);
  const sql = extractSql(tc?.validation_logic, tc?.test_data, tc?.validation_sql);
  const evidenceRefs = Array.isArray(tc?.evidence_references) ? tc.evidence_references : [];
  const proof = evidenceRefs.filter(ev => ev?.evidence_type === "DSD_SEMANTIC_PROOF");
  const snapshots = evidenceRefs.filter(ev => ev?.evidence_type === "SOURCE_DSD_SNAPSHOT");
  const others = evidenceRefs.filter(
    ev => ev?.evidence_type !== "DSD_SEMANTIC_PROOF" && ev?.evidence_type !== "SOURCE_DSD_SNAPSHOT"
  );

  const reqList = Array.isArray(tc?.requirement_ids) && tc.requirement_ids.length > 0
    ? tc.requirement_ids
    : tc?.requirement_id
    ? [tc.requirement_id]
    : [];

  const hasSourceMapping = Boolean(
    tc?.source_table || 
    tc?.source_column || 
    tc?.source_columns ||
    tc?.selection_criteria || 
    tc?.processing_rule || 
    tc?.formatting_rule || 
    tc?.validation_sql || 
    tc?.expected_validation || 
    sql
  );
  const hasTestData = Boolean(tc?.test_data || tc?.preconditions);

  return (
    <div className="px-6 py-6 bg-slate-50/30 border-l-4 border-l-brand-600">
      
      {/* Objective (Always visible) */}
      <div className="mb-6">
        <h4 className="text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
          <Info className="h-4 w-4 text-blue-600" /> Objective
        </h4>
        <p className="text-sm text-slate-700 leading-relaxed bg-blue-50/50 p-4 rounded-lg border border-blue-100">
          {tc?.objective || "No specific objective provided."}
        </p>
      </div>

      {/* Test Steps (Open by default) */}
      <CollapsibleSection title="Test Steps" defaultOpen={true}>
        <div className="text-sm text-slate-700 bg-white border border-slate-200 rounded-lg overflow-hidden">
          {steps.length > 0 ? (
            steps.map((step, idx) => {
              const stepMatch = typeof step === "string" ? step.match(/^(\d+)\.\s*(.*)/) : null;
              if (stepMatch) {
                return (
                  <div key={idx} className="flex gap-3 p-3 border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <span className="font-bold text-slate-400 w-5 text-right shrink-0">{stepMatch[1]}.</span>
                    <span>{stepMatch[2]}</span>
                  </div>
                );
              }
              return (
                <div key={idx} className="p-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 flex gap-2">
                  <span className="font-bold text-slate-400 w-5 text-right shrink-0">{idx + 1}.</span>
                  <span>{String(step)}</span>
                </div>
              );
            })
          ) : (
            <div className="p-4 text-slate-500 italic">No steps provided.</div>
          )}
        </div>
      </CollapsibleSection>

      {/* Expected Result (Open by default) */}
      <CollapsibleSection title="Expected Result" defaultOpen={true}>
        <div className="bg-green-50 p-4 rounded-lg border border-green-200 flex items-start gap-3">
          <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
          <p className="text-sm text-green-900 leading-relaxed font-medium whitespace-pre-wrap">
            {tc?.expected_result || "Verification criteria fulfilled successfully."}
          </p>
        </div>
      </CollapsibleSection>

      {/* Test Data & Preconditions (Closed by default) */}
      {hasTestData && (
        <CollapsibleSection title="Test Data & Preconditions" defaultOpen={false}>
          <div className="space-y-4">
            {tc?.preconditions && (
              <div>
                <h5 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Preconditions / Qualifying Conditions</h5>
                <p className="text-sm text-slate-700 bg-slate-50 p-3 rounded border border-slate-200">
                  {tc.preconditions}
                </p>
              </div>
            )}
            {tc?.test_data && (
              <div>
                <h5 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Test Data</h5>
                <p className="text-sm text-slate-700 bg-slate-50 p-3 rounded border border-slate-200 font-mono text-xs whitespace-pre-wrap">
                  {tc.test_data}
                </p>
              </div>
            )}
          </div>
        </CollapsibleSection>
      )}

      {/* SQL & Source Mapping (Closed by default) */}
      {hasSourceMapping && (
        <CollapsibleSection title="SQL & Source Mapping" defaultOpen={false}>
          <div className="space-y-4">
            {(tc?.source_table || tc?.source_column || tc?.source_columns || tc?.sort_field || tc?.sort_direction || tc?.selection_criteria || (tc?.source_mappings && tc.source_mappings.length > 0) || tc?.processing_rule || tc?.formatting_rule) && (
              <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <tbody className="divide-y divide-slate-100">
                    {tc?.sort_field && (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Sort Field</td>
                        <td className="px-4 py-2.5 text-slate-900 font-semibold">{tc.sort_field}</td>
                      </tr>
                    )}
                    {tc?.sort_direction && (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Sort Direction</td>
                        <td className="px-4 py-2.5 text-slate-900 font-medium">{tc.sort_direction}</td>
                      </tr>
                    )}
                    {tc?.source_table && (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Source Table</td>
                        <td className="px-4 py-2.5 text-slate-900 font-mono text-xs">{tc.source_table}</td>
                      </tr>
                    )}
                    {tc?.source_columns ? (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Source Columns</td>
                        <td className="px-4 py-2.5 text-slate-900 font-mono text-xs whitespace-pre-line leading-relaxed">{tc.source_columns}</td>
                      </tr>
                    ) : tc?.source_column ? (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Source Column</td>
                        <td className="px-4 py-2.5 text-slate-900 font-mono text-xs">
                          {tc.source_column === "Not resolved from DSD" ? (
                            <span className="text-amber-700 font-semibold bg-amber-50 px-2 py-0.5 rounded border border-amber-200 inline-flex items-center gap-1">
                              Not resolved from DSD
                            </span>
                          ) : (
                            tc.source_column
                          )}
                        </td>
                      </tr>
                    ) : null}
                    {tc?.selection_criteria && (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Selection Criteria</td>
                        <td className="px-4 py-2.5 text-slate-900 font-mono text-xs whitespace-pre-line leading-relaxed">{tc.selection_criteria}</td>
                      </tr>
                    )}
                    {tc?.source_mappings && tc.source_mappings.length > 0 && (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Source Mapping</td>
                        <td className="px-4 py-2.5 text-slate-900 font-mono text-xs space-y-1">
                          {tc.source_mappings.map((m, idx) => (
                            <div key={idx} className="flex items-center gap-2">
                              <span className="text-slate-600 font-sans font-medium">{m.field}</span>
                              <span className="text-slate-400">→</span>
                              <span className={`font-semibold ${m.column === "Not resolved from DSD" ? "text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200" : "text-slate-900"}`}>
                                {m.column}
                              </span>
                              {m.sort_direction && (
                                <span className="text-slate-500 font-sans text-[11px] font-normal">({m.sort_direction})</span>
                              )}
                            </div>
                          ))}
                        </td>
                      </tr>
                    )}
                    {tc?.lookup_table && (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Lookup Table</td>
                        <td className="px-4 py-2.5 text-slate-900 font-mono text-xs">{tc.lookup_table}</td>
                      </tr>
                    )}
                    {tc?.lookup_code_column && (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Lookup Code Column</td>
                        <td className="px-4 py-2.5 text-slate-900 font-mono text-xs">{tc.lookup_code_column}</td>
                      </tr>
                    )}
                    {tc?.lookup_description_column && (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Lookup Description Column</td>
                        <td className="px-4 py-2.5 text-slate-900 font-mono text-xs">{tc.lookup_description_column}</td>
                      </tr>
                    )}
                    {tc?.lookup_domain && (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Lookup Domain</td>
                        <td className="px-4 py-2.5 text-slate-900 font-mono text-xs">{tc.lookup_domain}</td>
                      </tr>
                    )}
                    {tc?.processing_rule && (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Processing Rule</td>
                        <td className="px-4 py-2.5 text-slate-900">{tc.processing_rule}</td>
                      </tr>
                    )}
                    {tc?.formatting_rule && (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Formatting Rule</td>
                        <td className="px-4 py-2.5 text-slate-900">{tc.formatting_rule}</td>
                      </tr>
                    )}
                    {tc?.traceability_source && (
                      <tr>
                        <td className="px-4 py-2.5 font-medium text-slate-500 bg-slate-50 w-1/3">Generated From</td>
                        <td className="px-4 py-2.5 text-slate-700 text-xs font-medium">{tc.traceability_source}</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
            
            {/* Validation SQL Area */}
            {tc?.sql_status === "UNAVAILABLE" ? (
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-slate-700">
                <div className="font-semibold text-xs uppercase tracking-wider text-slate-600 flex items-center gap-1.5 mb-1">
                  <Info className="h-4 w-4 text-slate-500" /> SQL Generation Unavailable
                </div>
                <div className="text-xs text-slate-500">
                  Reason: {tc?.sql_reason || "Source metadata is incomplete."}
                </div>
              </div>
            ) : tc?.sql_status === "REQUIRES_COMPLETION" ? (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-amber-900">
                <div className="font-semibold text-xs uppercase tracking-wider text-amber-800 flex items-center gap-1.5 mb-1">
                  <AlertTriangle className="h-4 w-4 text-amber-600" /> SQL Requires Completion
                </div>
                <div className="text-xs text-amber-700 mb-2">
                  Reason: {tc?.sql_reason || "Selection criteria contains unresolved parameters."}
                </div>
                {sql && (
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <h5 className="text-xs font-semibold uppercase tracking-wider text-amber-800 flex items-center gap-1.5">
                        <Code className="h-3.5 w-3.5 text-amber-700" /> Validation SQL Draft
                      </h5>
                      <button 
                        type="button"
                        onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(sql); }}
                        className="text-xs font-medium text-amber-800 hover:text-amber-900 bg-amber-100 hover:bg-amber-200 px-2.5 py-1 rounded transition-colors border border-amber-300"
                      >
                        Copy SQL
                      </button>
                    </div>
                    <pre className="text-xs text-slate-300 bg-slate-900 p-3.5 rounded-lg overflow-x-auto font-mono leading-relaxed shadow-inner">
                      {sql}
                    </pre>
                  </div>
                )}
              </div>
            ) : sql ? (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h5 className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                    <Code className="h-3.5 w-3.5 text-slate-500" /> Validation SQL
                  </h5>
                  <button 
                    type="button"
                    onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(sql); }}
                    className="text-xs font-medium text-brand-600 hover:text-brand-700 bg-brand-50 px-2.5 py-1 rounded transition-colors border border-brand-200"
                  >
                    Copy SQL
                  </button>
                </div>
                <pre className="text-xs text-slate-300 bg-slate-900 p-4 rounded-lg overflow-x-auto font-mono leading-relaxed shadow-inner">
                  {sql}
                </pre>
              </div>
            ) : (
              <div className="text-sm text-slate-500 italic p-1">No custom SQL query attached.</div>
            )}

            {/* SQL Purpose / Expected Validation */}
            {tc?.expected_validation && (
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                <h5 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">
                  SQL Purpose
                </h5>
                <p className="text-sm text-slate-800 font-medium">
                  {tc.expected_validation}
                </p>
              </div>
            )}
          </div>
        </CollapsibleSection>
      )}

      {/* Traceability (Closed by default) */}
      <CollapsibleSection title="Traceability" defaultOpen={false}>
        <div className="space-y-3">
          {reqList.length > 0 ? (
            reqList.map((req, idx) => (
              <div key={idx} className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-slate-900">{req}</span>
                  <span className="text-xs font-medium bg-green-100 text-green-700 px-2 py-0.5 rounded flex items-center gap-1 border border-green-200">
                    <CheckCircle2 className="h-3 w-3" /> Covered
                  </span>
                </div>
                <div className="text-xs text-slate-500">
                  Category: <span className="font-medium text-slate-700">{tc?.category || "General"}</span> &bull; Section: <span className="font-medium text-slate-700">{tc?.source_section || "Not specified"}</span>
                </div>
                <div className="text-xs text-slate-600 mt-2 border-t border-slate-100 pt-2">
                  Evidence References: {evidenceRefs.length}
                </div>
              </div>
            ))
          ) : (
            <div className="p-4 bg-amber-50 rounded-lg border border-amber-200 text-amber-800 text-sm">
              Requirement: N/A (No specific requirement mapped)
            </div>
          )}
        </div>
      </CollapsibleSection>

      {/* DSD Evidence (Open by default) — Reviewer-Facing: Authoritative Source DSD Snapshot */}
      <CollapsibleSection title="DSD Evidence" defaultOpen={true}>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {snapshots.map((ev, idx) => (
            <SourceDsdSnapshotCard key={`snap-${idx}`} ev={ev} onZoom={setZoomImage} />
          ))}
          {others.map((ev, idx) => (
            <GenericEvidenceCard key={`other-${idx}`} ev={ev} onZoom={setZoomImage} />
          ))}
          {snapshots.length === 0 && others.length === 0 && (
            <div className="col-span-full p-8 bg-slate-50 rounded-lg border border-slate-200 text-center flex flex-col items-center justify-center">
              <ImageIcon className="h-10 w-10 text-slate-300 mb-2" />
              <p className="text-sm text-slate-500 font-medium">No evidence available</p>
            </div>
          )}
        </div>
      </CollapsibleSection>

      {/* Bottom Navigation */}
      <div className="mt-8 pt-4 border-t border-slate-200 flex items-center justify-between">
        <button
          type="button"
          onClick={onPrev}
          disabled={selectedIndex <= 0}
          className="inline-flex items-center gap-1.5 rounded-md bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="h-4 w-4" /> Previous Test
        </button>
        <span className="text-xs font-semibold text-slate-700 bg-slate-100 px-3.5 py-1.5 rounded-full border border-slate-200 shadow-sm font-mono">
          {selectedIndex + 1} / {totalCount}
        </span>
        <button
          type="button"
          onClick={onNext}
          disabled={selectedIndex >= totalCount - 1}
          className="inline-flex items-center gap-1.5 rounded-md bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Next Test <ArrowRight className="h-4 w-4" />
        </button>
      </div>

    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function TestScenarioExplorer({ result }) {
  const allTests = useMemo(() => {
    const list = [...(result?.test_cases || [])];
    return list.sort((a, b) => (a.scenario_order || 0) - (b.scenario_order || 0));
  }, [result]);

  // State
  const [selectedTestCaseId, setSelectedTestCaseId] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchQuery, setSearchQuery] = useState("");
  const [methodologyFilter, setMethodologyFilter] = useState("ALL");
  const [riskFilter, setRiskFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [zoomImage, setZoomImage] = useState(null);

  // Dynamic filter options
  const methodologies = useMemo(() => ["ALL", ...Array.from(new Set(allTests.map(tc => tc.category).filter(Boolean))).sort()], [allTests]);
  const risks = useMemo(() => ["ALL", ...Array.from(new Set(allTests.map(tc => tc.priority || "Medium").filter(Boolean))).sort()], [allTests]);
  const statuses = useMemo(() => ["ALL", ...Array.from(new Set(allTests.map(tc => tc.status || "Generated").filter(Boolean))).sort()], [allTests]);

  // Filter logic
  const filteredTests = useMemo(() => {
    return allTests.filter(tc => {
      const matchSearch = !searchQuery || 
        tc.test_case_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tc.test_case_title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tc.requirement_id?.toLowerCase().includes(searchQuery.toLowerCase());
      const matchMethodology = methodologyFilter === "ALL" || tc.category === methodologyFilter;
      const matchRisk = riskFilter === "ALL" || (tc.priority || "Medium") === riskFilter;
      const matchStatus = statusFilter === "ALL" || (tc.status || "Generated") === statusFilter;
      
      return matchSearch && matchMethodology && matchRisk && matchStatus;
    });
  }, [allTests, searchQuery, methodologyFilter, riskFilter, statusFilter]);

  // Selected Index (Guaranteed to be safe)
  const selectedIndex = useMemo(() => {
    if (!selectedTestCaseId) return -1;
    return filteredTests.findIndex(tc => tc.test_case_id === selectedTestCaseId);
  }, [filteredTests, selectedTestCaseId]);

  // Pagination logic
  const totalPages = Math.max(1, Math.ceil(filteredTests.length / pageSize));
  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(totalPages);
  }, [totalPages, currentPage]);

  const paginatedTests = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredTests.slice(start, start + pageSize);
  }, [filteredTests, currentPage, pageSize]);

  // Navigation handlers
  const handleNext = (e) => {
    if (e) e.stopPropagation();
    if (selectedIndex >= 0 && selectedIndex < filteredTests.length - 1) {
      const nextId = filteredTests[selectedIndex + 1].test_case_id;
      setSelectedTestCaseId(nextId);
      setTimeout(() => {
        const el = document.getElementById(`scenario-${nextId}`);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 50);
    }
  };

  const handlePrev = (e) => {
    if (e) e.stopPropagation();
    if (selectedIndex > 0) {
      const prevId = filteredTests[selectedIndex - 1].test_case_id;
      setSelectedTestCaseId(prevId);
      setTimeout(() => {
        const el = document.getElementById(`scenario-${prevId}`);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 50);
    }
  };

  const toggleExpansion = (id) => {
    setSelectedTestCaseId(prev => (prev === id ? null : id));
  };

  if (!allTests.length) {
    return <div className="text-center text-slate-500 py-12">No test cases available.</div>;
  }

  return (
    <ScenarioErrorBoundary>
      <div className="flex h-full overflow-hidden bg-white rounded-xl border border-slate-200 shadow-sm relative flex-col">
        
        {/* Header & Toolbar */}
        <div className="bg-white border-b border-slate-200 px-5 py-4 z-10 shrink-0 relative">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Execution Scenarios</h2>
              <p className="text-sm text-slate-500 font-normal mt-0.5">Generated step-by-step validation procedures</p>
            </div>
            <span className="inline-flex items-center rounded-md bg-slate-100 px-3 py-1 text-sm font-medium text-slate-800 border border-slate-200 shadow-sm">
              Total: {filteredTests.length}
            </span>
          </div>
          
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                <Search className="h-4 w-4 text-slate-400" />
              </div>
              <input
                type="text"
                placeholder="Search test cases..."
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                className="block w-full rounded-md border-0 py-1.5 pl-9 pr-3 text-slate-900 ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-brand-600 sm:text-sm sm:leading-6"
              />
            </div>
            
            <div className="relative min-w-[150px]">
               <select
                 value={methodologyFilter}
                 onChange={(e) => { setMethodologyFilter(e.target.value); setCurrentPage(1); }}
                 className="block w-full rounded-md border-0 py-1.5 pl-3 pr-8 text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-brand-600 sm:text-sm sm:leading-6 bg-white"
               >
                 <option value="ALL">Methodology: All</option>
                 {methodologies.filter(m=>m!=="ALL").map(m => <option key={m} value={m}>{m}</option>)}
               </select>
            </div>

            <div className="relative min-w-[120px]">
               <select
                 value={riskFilter}
                 onChange={(e) => { setRiskFilter(e.target.value); setCurrentPage(1); }}
                 className="block w-full rounded-md border-0 py-1.5 pl-3 pr-8 text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-brand-600 sm:text-sm sm:leading-6 bg-white"
               >
                 <option value="ALL">Risk: All</option>
                 {risks.filter(m=>m!=="ALL").map(m => <option key={m} value={m}>{m}</option>)}
               </select>
            </div>

            <div className="relative min-w-[120px]">
               <select
                 value={statusFilter}
                 onChange={(e) => { setStatusFilter(e.target.value); setCurrentPage(1); }}
                 className="block w-full rounded-md border-0 py-1.5 pl-3 pr-8 text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-brand-600 sm:text-sm sm:leading-6 bg-white"
               >
                 <option value="ALL">Status: All</option>
                 {statuses.filter(m=>m!=="ALL").map(m => <option key={m} value={m}>{m}</option>)}
               </select>
            </div>
          </div>
        </div>

        {/* Table Area */}
        <div className="flex-1 overflow-auto bg-slate-50/50 w-full relative">
          <table className="w-full divide-y divide-slate-200 text-sm text-left">
            <thead className="bg-white sticky top-0 z-10 shadow-sm">
              <tr>
                <th className="px-4 py-3 font-semibold text-slate-600 bg-slate-50/95 backdrop-blur w-48">Test Case ID</th>
                <th className="px-4 py-3 font-semibold text-slate-600 bg-slate-50/95 backdrop-blur">Methodology</th>
                <th className="px-4 py-3 font-semibold text-slate-600 bg-slate-50/95 backdrop-blur">Requirement</th>
                <th className="px-4 py-3 font-semibold text-slate-600 bg-slate-50/95 backdrop-blur">Source Section</th>
                <th className="px-4 py-3 font-semibold text-slate-600 bg-slate-50/95 backdrop-blur w-24">Risk</th>
                <th className="px-4 py-3 font-semibold text-slate-600 bg-slate-50/95 backdrop-blur w-24">Status</th>
                <th className="px-4 py-3 font-semibold text-slate-600 bg-slate-50/95 backdrop-blur w-12 text-center"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {paginatedTests.map((tc) => {
                const isSelected = tc.test_case_id === selectedTestCaseId;
                const risk = tc.priority || "Medium";
                const riskColor = risk.toLowerCase() === 'high' ? 'bg-red-50 text-red-700 ring-red-600/20' : 
                                  risk.toLowerCase() === 'low' ? 'bg-slate-50 text-slate-600 ring-slate-500/20' : 
                                  'bg-amber-50 text-amber-700 ring-amber-600/20';
                
                const status = tc.status || "Generated";
                const statusColor = status.toLowerCase() === 'ready' || status.toLowerCase() === 'generated' ? 'bg-green-50 text-green-700 ring-green-600/20' : 'bg-blue-50 text-blue-700 ring-blue-600/20';

                return (
                  <React.Fragment key={tc.test_case_id}>
                    <tr 
                      id={`scenario-${tc.test_case_id}`}
                      onClick={() => toggleExpansion(tc.test_case_id)}
                      className={`cursor-pointer transition-colors group ${isSelected ? 'bg-brand-50 border-l-4 border-l-brand-600' : 'hover:bg-slate-50/80 border-l-4 border-l-transparent'}`}
                    >
                      <td className="px-4 py-3 font-semibold text-slate-900 truncate max-w-[200px]" title={tc.test_case_title}>
                        <div className="flex flex-col">
                          <span>{tc.test_case_id}</span>
                          {isSelected && <span className="text-xs text-slate-500 font-normal truncate mt-0.5">{tc.test_case_title}</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center rounded-md bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 ring-1 ring-inset ring-indigo-700/10 truncate max-w-[150px]">
                          {tc.category || "General"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-500 text-xs font-mono max-w-[120px] truncate">{tc.requirement_id || "-"}</td>
                      <td className="px-4 py-3 text-slate-600 text-xs truncate max-w-[150px]">{tc.source_section || "Not specified"}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${riskColor}`}>
                          {risk}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${statusColor}`}>
                          {status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center text-slate-400">
                        {isSelected ? <ChevronDown className="h-5 w-5 inline-block text-brand-600" /> : <ChevronRightIcon className="h-5 w-5 inline-block group-hover:text-slate-600" />}
                      </td>
                    </tr>

                    {/* Expanded Content */}
                    {isSelected && (
                      <tr className="bg-white">
                        <td colSpan="7" className="p-0 border-b border-slate-200 shadow-inner">
                          <ScenarioErrorBoundary testCaseId={tc.test_case_id}>
                            <ScenarioDetailContent 
                              tc={tc} 
                              selectedIndex={selectedIndex}
                              totalCount={filteredTests.length}
                              onPrev={handlePrev}
                              onNext={handleNext}
                              setZoomImage={setZoomImage}
                            />
                          </ScenarioErrorBoundary>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
              {paginatedTests.length === 0 && (
                <tr>
                  <td colSpan="7" className="px-4 py-12 text-center text-slate-500 bg-slate-50">
                    No scenarios match the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="bg-white border-t border-slate-200 px-5 py-3 flex items-center justify-between shrink-0">
          <div className="text-sm text-slate-500">
            Showing <span className="font-medium text-slate-900">{filteredTests.length === 0 ? 0 : (currentPage - 1) * pageSize + 1}</span> to <span className="font-medium text-slate-900">{Math.min(currentPage * pageSize, filteredTests.length)}</span> of <span className="font-medium text-slate-900">{filteredTests.length}</span> results
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-500">Rows per page:</span>
              <select
                value={pageSize}
                onChange={(e) => { setPageSize(Number(e.target.value)); setCurrentPage(1); }}
                className="rounded-md border-0 py-1 pl-2 pr-7 text-sm text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-brand-600"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </div>
            <div className="flex rounded-md shadow-sm">
              <button
                type="button"
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="relative inline-flex items-center rounded-l-md bg-white px-2 py-1.5 text-slate-400 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 focus:z-10 disabled:opacity-50"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="relative inline-flex items-center bg-white px-4 py-1.5 text-sm font-semibold text-slate-900 ring-1 ring-inset ring-slate-300">
                {currentPage}
              </span>
              <button
                type="button"
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages || totalPages === 0}
                className="relative inline-flex items-center rounded-r-md bg-white px-2 py-1.5 text-slate-400 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 focus:z-10 disabled:opacity-50"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Interactive Snipping-Tool DSD Evidence Viewer */}
        {zoomImage && (
          <InteractiveEvidenceViewer
            isOpen={Boolean(zoomImage)}
            onClose={() => setZoomImage(null)}
            imageUrl={typeof zoomImage === 'object' ? zoomImage.imageUrl : zoomImage}
            blob={typeof zoomImage === 'object' ? zoomImage.blob : null}
            evidence={typeof zoomImage === 'object' ? zoomImage.evidence : null}
            title={typeof zoomImage === 'object' ? zoomImage.title : null}
            previewMeta={typeof zoomImage === 'object' ? zoomImage.previewMeta : null}
          />
        )}

      </div>
    </ScenarioErrorBoundary>
  );
}
