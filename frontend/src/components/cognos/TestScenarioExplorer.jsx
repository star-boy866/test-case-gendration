import React, { useState, useEffect, useRef, useMemo } from "react";
import { 
  FileText, Loader2, AlertTriangle, Image as ImageIcon, 
  Search, ChevronRight, X, ChevronLeft, ChevronDown,
  CheckCircle2, AlertCircle, Clock, Database, Layers,
  Link as LinkIcon, Info, Code, FileCheck, ArrowRight,
  RefreshCw, Copy, Check, SlidersHorizontal, Sparkles, 
  Shield, ArrowLeft, CheckCircle, XCircle, Ban, 
  HelpCircle, MessageSquare, ChevronUp, ExternalLink,
  Briefcase
} from "lucide-react";
import { api } from "../../services/api";
import InteractiveEvidenceViewer from "./InteractiveEvidenceViewer";
import DriftingParticles from "../common/DriftingParticles";

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
        <div className="p-6 bg-red-50/80 border border-red-200 rounded-xl text-red-800 my-4 shadow-xs">
          <div className="flex items-center gap-2 font-bold text-base text-red-900 mb-2">
            <AlertTriangle className="h-5 w-5 text-red-600 shrink-0" />
            Unable to render this test scenario
          </div>
          {this.props.testCaseId && (
            <p className="text-xs font-semibold text-slate-700 mb-2">
              Test Case ID: <span className="font-mono bg-white px-2 py-0.5 border border-slate-200 rounded">{this.props.testCaseId}</span>
            </p>
          )}
          <p className="text-xs font-mono bg-red-100/60 p-3 rounded-lg text-red-950 overflow-x-auto whitespace-pre-wrap mb-3 border border-red-200">
            {this.state.error?.toString() || "Unknown error"}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors"
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
      <div className="flex items-center justify-center h-36 w-full bg-slate-50 rounded-lg animate-pulse">
        <div className="flex flex-col items-center gap-1.5 text-slate-400">
          <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
          <span className="text-xs font-medium">Loading proof image...</span>
        </div>
      </div>
    );
  }

  if (error || !objectUrl) {
    return (
      <div className="flex flex-col items-center justify-center p-6 bg-slate-50 border border-slate-200 rounded-lg text-slate-400 w-full">
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
    <div className="border border-indigo-100 rounded-xl overflow-hidden shadow-2xs h-full flex flex-col bg-white transition-all hover:shadow-xs">
      <div className="flex items-center justify-between px-3 py-2 bg-gradient-to-r from-indigo-700 to-indigo-800 text-white shrink-0">
        <span className="text-xs font-bold uppercase tracking-wider opacity-95 flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5" /> Semantic DSD Proof
        </span>
        <span className="text-[11px] font-medium bg-indigo-900/40 px-2 py-0.5 rounded-full border border-indigo-400/20">
          {pageText}{sectionText}
        </span>
      </div>
      <div className="p-2.5 flex-1 flex items-center justify-center bg-slate-50/40">
        {ev?.snapshot_url ? (
          <EvidenceImage
            url={ev.snapshot_url}
            alt={ev.description || "Semantic Proof"}
            className="w-full h-auto max-h-48 object-contain border border-indigo-100/60 rounded-lg cursor-zoom-in hover:opacity-90 transition-opacity bg-white shadow-2xs"
            onLoaded={setCurrentBlobUrl}
            onClick={(blobUrl) => { onZoom && onZoom({ imageUrl: blobUrl || ev.snapshot_url, evidence: ev, title: ev.description }); }}
          />
        ) : (
          <div className="text-xs text-slate-400 italic p-4 text-center">Image not available</div>
        )}
      </div>
      <div className="flex items-center justify-between px-3 py-2 border-t border-indigo-100/60 bg-indigo-50/40 shrink-0">
        <p className="text-xs text-slate-600 truncate mr-2 font-medium" title={ev?.description || ""}>
          {ev?.description || `Semantic evidence for ${ev?.test_case_id || "test"}`}
        </p>
        {ev?.snapshot_url && (
          <button
            type="button"
            className="text-xs font-semibold text-indigo-700 hover:text-indigo-900 underline shrink-0 inline-flex items-center gap-1"
            onClick={handleOpenFull}
          >
            Open Full Size <ExternalLink className="h-3 w-3" />
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
  } else if (rawScope === "REPORT_BODY_MAPPING") {
    rawScope = "Full Mapping";
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
    <div className="border border-slate-200 rounded-xl overflow-hidden shadow-2xs h-full flex flex-col bg-white transition-all hover:border-slate-300">
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900 text-white shrink-0">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-100 flex items-center gap-1.5">
          <Shield className="h-3.5 w-3.5 text-blue-400" /> Source DSD Snapshot
        </span>
        <span className="text-[11px] font-medium bg-slate-800 text-blue-200 px-2.5 py-0.5 rounded-full truncate max-w-[320px] border border-slate-700 font-mono" title={`${pageText}${sectionText}${scopeText}`}>
          {pageText}{sectionText}{scopeText}
        </span>
      </div>
      <div className="flex-1 flex flex-col items-center justify-center p-3 sm:p-5 bg-slate-50/50 border-b border-slate-200/80 overflow-y-auto max-h-[640px] min-h-[220px]">
        {snapshotObjectUrl ? (
          <div className="w-full flex items-center justify-center">
            <img 
              src={snapshotObjectUrl} 
              alt="Source DSD Snapshot" 
              className={
                isLayoutVal
                  ? "source-dsd-full-page-preview w-full h-auto max-w-full block rounded-lg border border-slate-200/90 shadow-2xs bg-white cursor-zoom-in hover:opacity-95 transition-opacity"
                  : "w-auto h-auto max-w-full max-h-[580px] object-contain border border-slate-200/90 rounded-lg shadow-2xs bg-white cursor-zoom-in hover:opacity-95 transition-opacity mx-auto block"
              }
              onLoad={(e) => {
                const nw = e.target.naturalWidth;
                const nh = e.target.naturalHeight;
                if (previewMetaRef.current) {
                  previewMetaRef.current.naturalWidth = nw;
                  previewMetaRef.current.naturalHeight = nh;
                }
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
          <div className="flex flex-col items-center py-8">
            <FileText className="h-8 w-8 text-slate-300 mb-2" />
            <p className="text-xs font-medium text-amber-700 bg-amber-50 px-3 py-1 rounded-full border border-amber-200 text-center">
              Visual source preview unavailable
            </p>
          </div>
        ) : (
          <div className="flex items-center justify-center h-48 w-full bg-slate-50 rounded-lg animate-pulse">
            <div className="flex flex-col items-center gap-1.5 text-slate-400">
              <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
              <span className="text-xs font-medium">Loading source snapshot...</span>
            </div>
          </div>
        )}
      </div>
      <div className="px-4 py-2.5 bg-slate-50/70 shrink-0 flex items-center justify-between gap-2">
        <p className="text-xs text-slate-600 truncate font-medium" title={ev?.description || ""}>
          {ev?.description || "Source document excerpt"}
        </p>
        <button
          type="button"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-white px-3 py-1 text-xs font-semibold text-blue-600 shadow-2xs ring-1 ring-inset ring-slate-200 hover:bg-blue-50 hover:ring-blue-300 transition-colors disabled:opacity-50"
          disabled={!snapshotObjectUrl}
          onClick={handleOpenFull}
        >
          Open Full Size <ExternalLink className="h-3 w-3" />
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
    <div className="border border-slate-200 rounded-xl overflow-hidden shadow-2xs h-full flex flex-col bg-white transition-all hover:border-slate-300">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-100 shrink-0 border-b border-slate-200/80">
        <span className="text-xs font-bold text-slate-800 uppercase tracking-wide">
          {typeText}
        </span>
        <span className="text-xs text-slate-500 font-mono">
          {pageText}{sectionText}
        </span>
      </div>
      <div className="p-3.5 flex-1 flex items-center justify-center bg-slate-50/40 overflow-y-auto max-h-[640px] min-h-[220px]">
        {ev?.snapshot_url ? (
          <EvidenceImage
            url={ev.snapshot_url}
            alt={ev?.description || "Evidence snapshot"}
            className="w-auto h-auto max-w-full max-h-[580px] object-contain border border-slate-200/80 rounded-lg cursor-zoom-in hover:opacity-95 transition-opacity bg-white shadow-2xs mx-auto block"
            onClick={(e) => { e.stopPropagation(); onZoom && onZoom({ imageUrl: ev.snapshot_url, evidence: ev, title: ev?.description }); }}
          />
        ) : (
          <div className="text-xs text-slate-400 italic p-4 text-center">Image not available</div>
        )}
      </div>
      <div className="flex items-center justify-between px-4 py-2 border-t border-slate-200/60 bg-slate-50 shrink-0">
        <p className="text-xs text-slate-500 truncate mr-2" title={ev?.description || ""}>
          {ev?.description || "No description provided"}
        </p>
        {ev?.snapshot_url && (
          <button
            type="button"
            className="text-xs font-semibold text-blue-600 hover:text-blue-700 underline shrink-0 inline-flex items-center gap-1"
            onClick={handleOpenFull}
          >
            Open Full Size <ExternalLink className="h-3 w-3" />
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Business Scenario Title Resolver ──────────────────────────────────────────

export function getBusinessScenarioTitle(tc) {
  if (!tc) return "Validation Scenario";
  const id = (tc.test_case_id || "").toUpperCase();
  const cat = (tc.category || "").toLowerCase();
  const title = (tc.test_case_title || "").trim();

  if (id.includes("-EXEC-") || cat.includes("execution and scheduling") || cat.includes("execution & scheduling") || (cat.includes("execution") && cat.includes("scheduling")) || (cat.includes("scheduled") && cat.includes("execution"))) {
    return "Report Execution and Scheduling Validation";
  }
  if (id.includes("-DBRV-") || id.includes("-DBRE-") || cat.includes("db report") || cat.includes("database") || cat.includes("db mapping")) {
    return "Database Source Mapping Validation";
  }
  if (id.includes("-REPO-") || cat.includes("report definition")) {
    return "Report Definition Validation";
  }
  if (id.includes("-RHDR-") || cat.includes("report header")) {
    return "Report Header Validation";
  }
  if (id.includes("-LAYO-") || cat.includes("layout")) {
    return "Report Layout Validation";
  }
  if (id.includes("-SECT-") || cat.includes("section heading")) {
    return "Report Section Heading Validation";
  }
  if (id.includes("-SELC-") || cat.includes("selection criteria")) {
    return "Report Selection Criteria Validation";
  }
  if (id.includes("-LABE-") || cat.includes("label") || cat.includes("column label")) {
    return "Report Body Column Label Validation";
  }
  if (id.includes("-SORT-") || cat.includes("sort")) {
    return "Report Sort Order Validation";
  }
  if (id.includes("-SPEC-") || cat.includes("special processing")) {
    return "Report Special Processing Validation";
  }
  if (id.includes("-LOOK-") || cat.includes("lookup")) {
    return "Lookup Validation";
  }
  if (id.includes("-OUTP-") || cat.includes("output delivery")) {
    return "Output Delivery Validation";
  }
  if (id.includes("-SCRI-") || cat.includes("script output") || cat.includes("script")) {
    return "Script Output Validation";
  }
  if (id.includes("-FREQ-") || cat.includes("frequency") || cat.includes("scheduling")) {
    return "Report Frequency & Scheduling Validation";
  }
  if (id.includes("-SECU-") || cat.includes("security") || cat.includes("access")) {
    return "Report Security & Access Validation";
  }
  if (id.includes("-DIST-") || cat.includes("distribution")) {
    return "Report Distribution Validation";
  }

  // If title is clean and not a long generic verification prompt
  if (title && !title.startsWith("Verify ") && title.length < 50) {
    return title;
  }
  if (tc.category) {
    const cleanCat = tc.category.trim();
    if (cleanCat.toLowerCase().endsWith("validation")) {
      return cleanCat;
    }
    return `${cleanCat} Validation`;
  }
  return title || "Validation Scenario";
}

// ─── Workspace Detail Views ───────────────────────────────────────────────────

const WORKSPACE_TABS = [
  { id: "steps", label: "Test Steps", icon: Layers },
  { id: "data", label: "Test Data", icon: Database },
  { id: "evidence", label: "Evidence", icon: ImageIcon },
  { id: "sql", label: "SQL & Source Mapping", icon: Code },
];

function ScenarioWorkspaceDetail({ 
  tc, 
  selectedIndex, 
  totalCount, 
  onPrev, 
  onNext, 
  setZoomImage,
  executionState,
  onUpdateExecution
}) {
  const steps = useMemo(() => parseSteps(tc?.test_steps), [tc?.test_steps]);
  const [selectedStepIndex, setSelectedStepIndex] = useState(0);
  const [activeTab, setActiveTab] = useState("steps");
  const [copiedSql, setCopiedSql] = useState(false);
  const [commentDraft, setCommentDraft] = useState("");

  // Reset step index and comment on scenario change
  useEffect(() => {
    setSelectedStepIndex(0);
  }, [tc?.test_case_id]);

  const scenarioCommentKey = `${tc?.test_case_id}-scenario-comment`;
  const existingComment = executionState[scenarioCommentKey]?.comment || executionState[`${tc?.test_case_id}-step-0`]?.comment || "";

  useEffect(() => {
    setCommentDraft(existingComment);
  }, [tc?.test_case_id, existingComment]);

  const handleCommentBlur = () => {
    onUpdateExecution(scenarioCommentKey, { comment: commentDraft });
    onUpdateExecution(`${tc?.test_case_id}-step-${selectedStepIndex}`, { comment: commentDraft });
  };

  const sql = extractSql(tc?.validation_logic, tc?.test_data, tc?.validation_sql);
  const evidenceRefs = Array.isArray(tc?.evidence_references) ? tc.evidence_references : [];
  const snapshots = evidenceRefs.filter(ev => ev?.evidence_type === "SOURCE_DSD_SNAPSHOT");
  const others = evidenceRefs.filter(
    ev => ev?.evidence_type !== "DSD_SEMANTIC_PROOF" && ev?.evidence_type !== "SOURCE_DSD_SNAPSHOT"
  );

  const hasTestData = Boolean(tc?.test_data || tc?.preconditions);

  const handleCopySql = (e) => {
    e.stopPropagation();
    if (sql) {
      navigator.clipboard.writeText(sql);
      setCopiedSql(true);
      setTimeout(() => setCopiedSql(false), 2000);
    }
  };

  return (
    <div className="flex flex-col space-y-4 max-w-full relative z-10">
      
      {/* ── 1. Top Detail Header (Workspace Header) ───────────────────────── */}
      <div className="border-b border-slate-200 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          
          <div className="space-y-1 min-w-0 flex-1">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight leading-snug">
              {getBusinessScenarioTitle(tc)}
            </h1>

            {tc?.test_case_title && tc.test_case_title !== getBusinessScenarioTitle(tc) && (
              <p className="text-xs text-slate-500 font-normal line-clamp-1">
                {tc.test_case_title}
              </p>
            )}
          </div>

          {/* Quick Header Navigation */}
          <div className="flex items-center gap-1.5 shrink-0 self-start sm:self-center">
            <button
              type="button"
              onClick={onPrev}
              disabled={selectedIndex <= 0}
              title="Previous test scenario"
              className="inline-flex items-center gap-1 rounded-lg bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="h-3.5 w-3.5" /> Previous
            </button>
            <span className="text-xs font-semibold text-slate-600 bg-slate-50 px-2.5 py-1.5 rounded-lg border border-slate-200 font-mono">
              {selectedIndex + 1} of {totalCount}
            </span>
            <button
              type="button"
              onClick={onNext}
              disabled={selectedIndex >= totalCount - 1}
              title="Next test scenario"
              className="inline-flex items-center gap-1 rounded-lg bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Next <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>

        </div>
      </div>

      {/* ── 2. Workspace Horizontal Tabs (Clean Underline Style) ─────────────── */}
      <div className="border-b border-slate-200">
        <div className="flex items-center gap-6 overflow-x-auto no-scrollbar">
          {WORKSPACE_TABS.map((tab) => {
            const Icon = tab.icon;
            const isTabActive = activeTab === tab.id;
            let countBadge = null;
            if (tab.id === "steps") countBadge = steps.length;
            if (tab.id === "evidence") countBadge = snapshots.length;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-1.5 py-2.5 text-xs font-semibold transition-all whitespace-nowrap border-b-2 bg-transparent ${
                  isTabActive
                    ? "border-blue-600 text-blue-600 font-bold"
                    : "border-transparent text-slate-500 hover:text-slate-900 hover:border-slate-300 font-medium"
                }`}
              >
                <Icon className={`h-3.5 w-3.5 ${isTabActive ? "text-blue-600" : "text-slate-400"}`} />
                <span>{tab.label}</span>
                {countBadge !== null && countBadge > 0 && (
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold font-mono ${
                    isTabActive ? "bg-blue-100 text-blue-800" : "bg-slate-100 text-slate-500"
                  }`}>
                    {countBadge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── 3. TAB CONTENT AREAS ────────────────────────────────────────────── */}

      {/* TAB 1: Test Steps (Minimal Scenario Workspace) */}
      {activeTab === "steps" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
            
            {/* Left Column: Vertical Step Navigator (Primary Step Selector) */}
            <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl p-3 space-y-1.5 shadow-2xs">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100 px-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Step Navigator
                </span>
                <span className="text-[11px] font-mono font-semibold text-slate-500">
                  {steps.length} Steps
                </span>
              </div>
              <div className="space-y-1.5 max-h-[560px] overflow-y-auto pr-1">
                {steps.map((step, idx) => {
                  const isCurrent = idx === selectedStepIndex;
                  const stepMatch = typeof step === "string" ? step.match(/^(\d+)\.\s*(.*)/) : null;
                  const stepNum = stepMatch ? stepMatch[1] : idx + 1;
                  const stepLabel = stepMatch ? stepMatch[2] : String(step);

                  const stepKey = `${tc?.test_case_id}-step-${idx}`;
                  const execStatus = executionState[stepKey]?.status;
                  const isPass = execStatus === 'PASS';

                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setSelectedStepIndex(idx)}
                      className={`w-full flex items-start gap-2.5 p-2.5 rounded-lg text-left text-xs transition-all border ${
                        isCurrent
                          ? "bg-blue-50 border-blue-200 text-blue-950 font-semibold border-l-4 border-l-blue-600 shadow-2xs"
                          : "bg-slate-50/60 hover:bg-slate-100/70 border-slate-200/70 text-slate-700 font-medium border-l-4 border-l-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-1 shrink-0 mt-0.5">
                        <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold ${
                          isPass
                            ? "bg-emerald-600 text-white"
                            : isCurrent 
                            ? "bg-blue-600 text-white" 
                            : "bg-slate-200 text-slate-600"
                        }`}>
                          {isPass ? "✓" : stepNum}
                        </span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="line-clamp-2 leading-relaxed">
                          {stepLabel}
                        </p>
                        {execStatus && (
                          <span className={`inline-block mt-1 text-[10px] font-bold px-1.5 py-0.2 rounded border ${
                            execStatus === 'PASS' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                            execStatus === 'FAIL' ? 'bg-red-50 text-red-700 border-red-200' :
                            execStatus === 'BLOCKED' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                            'bg-slate-100 text-slate-600 border-slate-200'
                          }`}>
                            {execStatus}
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Right Column: Minimal Scenario Workspace (ONLY Objective & Execution Comments) */}
            <div className="lg:col-span-7 bg-white border border-slate-200 rounded-xl p-5 space-y-6 shadow-2xs">
              
              {/* 1. SCENARIO OBJECTIVE */}
              <div className="space-y-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  Scenario Objective
                </h3>
                <p className="text-xs sm:text-sm text-slate-900 leading-relaxed font-normal">
                  {tc?.objective || "Verify scenario requirements according to DSD specification."}
                </p>
              </div>

              <div className="border-t border-slate-100" />

              {/* 2. EXECUTION COMMENTS */}
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-700 block">
                  Execution Comments
                </label>
                <textarea
                  rows={8}
                  placeholder="Enter observation, defect reference, or execution comments..."
                  value={commentDraft}
                  onChange={(e) => setCommentDraft(e.target.value)}
                  onBlur={handleCommentBlur}
                  className="w-full text-xs rounded-lg border border-slate-200 bg-slate-50 p-3 text-slate-800 placeholder:text-slate-400 focus:bg-white focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all leading-relaxed"
                />
              </div>

            </div>

          </div>
        </div>
      )}

      {/* TAB 2: Test Data & Preconditions */}
      {activeTab === "data" && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-4 shadow-2xs">
          <div className="border-b border-slate-100 pb-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <Database className="h-3.5 w-3.5 text-blue-600" /> Test Data & Preconditions
            </h2>
          </div>

          {tc?.preconditions && (
            <div>
              <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Preconditions
              </h3>
              <p className="text-xs text-slate-800 bg-slate-50 p-3 rounded-lg border border-slate-200 leading-relaxed">
                {tc.preconditions}
              </p>
            </div>
          )}

          {tc?.test_data && (
            <div>
              <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Test Data Specification
              </h3>
              <pre className="text-xs text-slate-800 bg-slate-50 p-3 rounded-lg border border-slate-200 font-mono whitespace-pre-wrap leading-relaxed shadow-inner">
                {tc.test_data}
              </pre>
            </div>
          )}

          {!hasTestData && (
            <div className="text-center py-6 text-slate-400 text-xs italic">
              No specific preconditions or test data specified for this scenario.
            </div>
          )}
        </div>
      )}

      {/* TAB 3: Evidence Library */}
      {activeTab === "evidence" && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-4 shadow-2xs">
          <div className="border-b border-slate-100 pb-2 flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <ImageIcon className="h-3.5 w-3.5 text-blue-600" /> Evidence
            </h2>
            <span className="text-[11px] font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
              {snapshots.length} {snapshots.length === 1 ? "Reference" : "References"}
            </span>
          </div>

          <div className={snapshots.length + others.length <= 1 ? "w-full space-y-4" : "grid grid-cols-1 xl:grid-cols-2 gap-4"}>
            {snapshots.map((ev, idx) => (
              <SourceDsdSnapshotCard key={`snap-${idx}`} ev={ev} onZoom={setZoomImage} />
            ))}
            {others.map((ev, idx) => (
              <GenericEvidenceCard key={`other-${idx}`} ev={ev} onZoom={setZoomImage} />
            ))}
            {snapshots.length === 0 && others.length === 0 && (
              <div className="col-span-full py-10 bg-slate-50 rounded-xl border border-slate-200 text-center">
                <p className="text-xs text-slate-500">No visual evidence available for this scenario.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: SQL & Source Mapping */}
      {activeTab === "sql" && (
        <div className="space-y-4">
          
          {/* Validation SQL Area */}
          {tc?.sql_status === "UNAVAILABLE" ? (
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-3.5 text-slate-700">
              <div className="font-semibold text-xs uppercase tracking-wider text-slate-600 flex items-center gap-1.5 mb-1">
                <Info className="h-3.5 w-3.5 text-slate-500" /> SQL Generation Unavailable
              </div>
              <div className="text-xs text-slate-500">
                Reason: {tc?.sql_reason || "Source metadata is incomplete."}
              </div>
            </div>
          ) : tc?.sql_status === "REQUIRES_COMPLETION" ? (
            <div className="bg-amber-50/80 border border-amber-200 rounded-lg p-3.5 text-amber-900">
              <div className="font-semibold text-xs uppercase tracking-wider text-amber-800 flex items-center gap-1.5 mb-1">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-600" /> SQL Requires Completion
              </div>
              <div className="text-xs text-amber-700 mb-2">
                Reason: {tc?.sql_reason || "Selection criteria contains unresolved parameters."}
              </div>
              {sql && (
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-800 flex items-center gap-1.5">
                      <Code className="h-3.5 w-3.5 text-amber-700" /> Validation SQL Draft
                    </h4>
                    <button 
                      type="button"
                      onClick={handleCopySql}
                      className="inline-flex items-center gap-1 text-xs font-medium text-amber-800 hover:text-amber-900 bg-amber-100 hover:bg-amber-200 px-2.5 py-0.5 rounded transition-colors border border-amber-300"
                    >
                      {copiedSql ? <Check className="h-3 w-3 text-emerald-700" /> : <Copy className="h-3 w-3" />}
                      {copiedSql ? "Copied" : "Copy SQL"}
                    </button>
                  </div>
                  <pre className="text-xs text-slate-200 bg-slate-900 p-3.5 rounded-lg overflow-x-auto font-mono leading-relaxed shadow-inner">
                    {sql}
                  </pre>
                </div>
              )}
            </div>
          ) : sql ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <Code className="h-3.5 w-3.5 text-blue-600" />
                    Validation SQL Query
                  </h4>
                  {tc?.shared_sql_group && (
                    <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                      Consolidated Report Query
                    </span>
                  )}
                </div>
                <button 
                  type="button"
                  onClick={handleCopySql}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 bg-blue-50 px-2.5 py-1 rounded transition-colors border border-blue-200"
                >
                  {copiedSql ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                  {copiedSql ? "Copied" : "Copy SQL"}
                </button>
              </div>
              <pre className="text-xs text-slate-200 bg-slate-900 p-3.5 rounded-lg overflow-x-auto font-mono leading-relaxed shadow-inner">
                {sql}
              </pre>
            </div>
          ) : null}

          {/* Structured Source Mappings Table */}
          {Array.isArray(tc?.source_mappings) && tc.source_mappings.length > 0 ? (
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-2xs">
              <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">Source Mappings</h3>
                <span className="text-[11px] font-mono text-slate-500">{tc.source_mappings.length} Fields</span>
              </div>
              <table className="min-w-full divide-y divide-slate-200 text-xs">
                <thead>
                  <tr className="bg-slate-50/80 text-left text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                    <th className="px-4 py-2.5">Business Label</th>
                    <th className="px-4 py-2.5">Source Table</th>
                    <th className="px-4 py-2.5">Source Column</th>
                    <th className="px-4 py-2.5">Processing Rule</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-normal">
                  {tc.source_mappings.map((m, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/60 transition-colors">
                      <td className="px-4 py-2.5 font-semibold text-slate-900">{m.field}</td>
                      <td className="px-4 py-2.5 font-mono text-slate-600">{m.table || tc.source_table || "P_RPT_CLDI_TERM_TB"}</td>
                      <td className="px-4 py-2.5 font-mono font-medium text-blue-700">
                        {m.column === "Not resolved from DSD" ? (
                          <span className="text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">Not resolved</span>
                        ) : (
                          m.column
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-slate-600">{m.rule || tc.processing_rule || "Direct mapping from source table"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (tc?.source_table || tc?.source_column || tc?.source_columns || tc?.sort_field) && (
            <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-2xs">
              <table className="min-w-full divide-y divide-slate-200 text-xs">
                <tbody className="divide-y divide-slate-100">
                  {tc?.sort_field && (
                    <tr>
                      <td className="px-3.5 py-2 font-medium text-slate-500 bg-slate-50 w-1/3">Sort Field</td>
                      <td className="px-3.5 py-2 text-slate-900 font-semibold">{tc.sort_field}</td>
                    </tr>
                  )}
                  {tc?.source_table && (
                    <tr>
                      <td className="px-3.5 py-2 font-medium text-slate-500 bg-slate-50 w-1/3">Source Table</td>
                      <td className="px-3.5 py-2 text-slate-900 font-mono text-xs">{tc.source_table}</td>
                    </tr>
                  )}
                  {tc?.source_column && (
                    <tr>
                      <td className="px-3.5 py-2 font-medium text-slate-500 bg-slate-50 w-1/3">Source Column</td>
                      <td className="px-3.5 py-2 text-slate-900 font-mono text-xs">{tc.source_column}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

        </div>
      )}

      {/* ── 5. Bottom Navigation Bar ────────────────────────────────────────── */}
      <div className="border-t border-slate-200/80 pt-3 flex items-center justify-between">
        <button
          type="button"
          onClick={onPrev}
          disabled={selectedIndex <= 0}
          className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="h-4 w-4" /> Previous Test
        </button>
        <span className="text-xs font-semibold text-slate-600 bg-slate-50 px-3 py-1.5 rounded-full border border-slate-200 font-mono">
          Test {selectedIndex + 1} of {totalCount}
        </span>
        <button
          type="button"
          onClick={onNext}
          disabled={selectedIndex >= totalCount - 1}
          className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Next Test <ArrowRight className="h-4 w-4" />
        </button>
      </div>

    </div>
  );
}

// ─── Main 3-Zone Workspace Component ──────────────────────────────────────────

export default function TestScenarioExplorer({ result, projectContext }) {
  // Resolve project context from prop or localStorage
  const activeContext = useMemo(() => {
    if (projectContext && (projectContext.work_item_id || projectContext.work_item_title)) {
      return projectContext;
    }
    try {
      const raw = localStorage.getItem("cognos_project_context");
      if (raw) return JSON.parse(raw);
    } catch {}
    return null;
  }, [projectContext]);

  // Scenario Normalization and Business Consolidation
  const allTests = useMemo(() => {
    const rawList = [...(result?.test_cases || [])];
    rawList.sort((a, b) => (a.scenario_order || 0) - (b.scenario_order || 0));

    const dbScenarios = rawList.filter(tc => {
      const id = (tc.test_case_id || "").toUpperCase();
      const cat = (tc.category || "").toLowerCase();
      return id.includes("-DBRV-") || id.includes("-DBRE-") || cat.includes("db report") || cat.includes("database") || cat.includes("db mapping");
    });

    const sortScenarios = rawList.filter(tc => {
      const id = (tc.test_case_id || "").toUpperCase();
      const cat = (tc.category || "").toLowerCase();
      return id.includes("-SORT-") || cat.includes("sort");
    });

    const outpScenarios = rawList.filter(tc => {
      const id = (tc.test_case_id || "").toUpperCase();
      const cat = (tc.category || "").toLowerCase();
      return id.includes("-OUTP-") || cat.includes("output delivery") || cat.includes("delivery");
    });

    const consolidated = [];
    let dbHandled = false;
    let sortHandled = false;
    let outpHandled = false;

    for (const tc of rawList) {
      const id = (tc.test_case_id || "").toUpperCase();
      const cat = (tc.category || "").toLowerCase();
      const isDb = id.includes("-DBRV-") || id.includes("-DBRE-") || cat.includes("db report") || cat.includes("database") || cat.includes("db mapping");
      const isSort = id.includes("-SORT-") || cat.includes("sort");
      const isOutp = id.includes("-OUTP-") || cat.includes("output delivery") || cat.includes("delivery");

      if (isDb) {
        if (!dbHandled) {
          dbHandled = true;
          if (dbScenarios.length > 1) {
            const primary = dbScenarios[0];
            const allMappings = [];
            const seenFields = new Set();
            dbScenarios.forEach(s => {
              if (Array.isArray(s.source_mappings)) {
                s.source_mappings.forEach(m => {
                  if (m?.field && !seenFields.has(m.field)) {
                    seenFields.add(m.field);
                    allMappings.push(m);
                  }
                });
              } else if (s.source_field || s.source_column) {
                const f = s.source_field || s.test_case_title || "Field";
                if (!seenFields.has(f)) {
                  seenFields.add(f);
                  allMappings.push({
                    field: f,
                    column: s.source_column || "Not resolved from DSD",
                    table: s.source_table || "P_RPT_CLDI_TERM_TB"
                  });
                }
              }
            });

            consolidated.push({
              ...primary,
              test_case_id: primary.test_case_id.replace(/-DBRE-\d+/, "-DBRV-01").replace(/-DBRV-\d+/, "-DBRV-01"),
              test_case_title: "Verify all report data mappings for PRV-INT-027 against the source database",
              category: "DB Report Data Validation",
              source_mappings: allMappings.length > 0 ? allMappings : primary.source_mappings,
              priority: "High",
              source_section: "Report Body",
              objective: "Verify that all data fields in the report map accurately to their source database columns and comply with all processing/transformation rules per the DSD.",
              expected_result: "All report columns accurately reflect database records per the consolidated mapping specification with 0 discrepancies."
            });
          } else {
            consolidated.push(tc);
          }
        }
      } else if (isSort) {
        if (!sortHandled) {
          sortHandled = true;
          if (sortScenarios.length > 1) {
            const primary = sortScenarios[0];
            const allSortFields = sortScenarios.map(s => s.sort_field || s.test_case_title).filter(Boolean).join(", ");
            consolidated.push({
              ...primary,
              test_case_id: primary.test_case_id.replace(/-SORT-\d+/, "-SORT-01"),
              test_case_title: "Verify all report sort orders and grouping hierarchy per the DSD specification",
              category: "Sort Validation",
              sort_field: allSortFields || primary.sort_field,
              objective: `Verify that report records are sorted in the specified sequence (${allSortFields || 'primary and secondary sort keys'}) per the DSD.`,
              expected_result: "Report records are displayed in the exact sort sequence defined in the DSD specification."
            });
          } else {
            consolidated.push(tc);
          }
        }
      } else if (isOutp) {
        if (!outpHandled) {
          outpHandled = true;
          const primary = outpScenarios[0] || tc;
          const repId = primary.report_id || result?.report_id || "PRV-INT-027";
          consolidated.push({
            ...primary,
            test_case_id: primary.test_case_id.replace(/-OUTP-\d+/, "-OUTP-01"),
            test_case_title: `Verify report delivery to SDR page for ${repId}`,
            category: "Output Delivery Validation",
            objective: `Verify report '${repId}' is successfully delivered to 'SDR page' after execution.`,
            preconditions: `Report '${repId}' has been executed. 'SDR page' is accessible to tester.`,
            test_data: "Expected delivery destination: SDR page",
            test_steps: (
              `1. Open 'SDR page'.\n` +
              `2. Locate the generated '${repId}' report output.\n` +
              `3. Verify the report was delivered successfully to 'SDR page'.\n` +
              `4. Verify the delivered report matches the correct report ID, version, and output format.\n` +
              `5. Verify the delivered file is not corrupted and opens correctly.\n` +
              `6. Capture evidence of the successful delivery in 'SDR page'.`
            ),
            expected_result: (
              `Report ${repId} is successfully delivered to 'SDR page'. ` +
              `The delivered report is accessible, not corrupted, and matches the expected report ID.`
            )
          });
        }
      } else {
        consolidated.push(tc);
      }
    }

    return consolidated.map((tc) => {
      if (!tc) return tc;
      const sanitizeEdmsText = (text) => {
        if (typeof text !== "string" || !text) return text;
        return text
          .replace(/'EDMS'\s*\(or SDR delivery repository\)/gi, "'SDR page'")
          .replace(/\bEDMS\b/g, "SDR page")
          .replace(/\bedms\b/g, "SDR page");
      };

      return {
        ...tc,
        test_case_title: sanitizeEdmsText(tc.test_case_title),
        objective: sanitizeEdmsText(tc.objective),
        test_steps: sanitizeEdmsText(tc.test_steps),
        expected_result: sanitizeEdmsText(tc.expected_result),
        preconditions: sanitizeEdmsText(tc.preconditions),
        test_data: sanitizeEdmsText(tc.test_data),
        test_case_description: sanitizeEdmsText(tc.test_case_description),
        dsd_reference: sanitizeEdmsText(tc.dsd_reference),
        category: sanitizeEdmsText(tc.category),
        evidences: Array.isArray(tc.evidences)
          ? tc.evidences.map((ev) => ({
              ...ev,
              description: sanitizeEdmsText(ev?.description),
              placeholder: sanitizeEdmsText(ev?.placeholder),
              target_field: sanitizeEdmsText(ev?.target_field),
            }))
          : tc.evidences,
      };
    });
  }, [result]);

  // State
  const [selectedTestCaseId, setSelectedTestCaseId] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [methodologyFilter, setMethodologyFilter] = useState("ALL");
  const [riskFilter, setRiskFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [zoomImage, setZoomImage] = useState(null);
  const [mobileDetailOpen, setMobileDetailOpen] = useState(false);
  const [executionState, setExecutionState] = useState({});

  const handleUpdateExecution = (key, update) => {
    setExecutionState(prev => ({
      ...prev,
      [key]: { ...prev[key], ...update }
    }));
  };

  // Dynamic filter options
  const methodologies = useMemo(() => ["ALL", ...Array.from(new Set(allTests.map(tc => tc.category).filter(Boolean))).sort()], [allTests]);
  const risks = useMemo(() => ["ALL", ...Array.from(new Set(allTests.map(tc => tc.priority || "Medium").filter(Boolean))).sort()], [allTests]);
  const statuses = useMemo(() => ["ALL", ...Array.from(new Set(allTests.map(tc => tc.status || "Generated").filter(Boolean))).sort()], [allTests]);

  // Filter logic
  const filteredTests = useMemo(() => {
    return allTests.filter(tc => {
      const q = searchQuery.toLowerCase().trim();
      const bTitle = getBusinessScenarioTitle(tc).toLowerCase();
      const matchSearch = !q || 
        tc.test_case_id?.toLowerCase().includes(q) ||
        bTitle.includes(q) ||
        tc.test_case_title?.toLowerCase().includes(q) ||
        tc.category?.toLowerCase().includes(q) ||
        tc.source_section?.toLowerCase().includes(q);

      const matchMethodology = methodologyFilter === "ALL" || tc.category === methodologyFilter;
      const matchRisk = riskFilter === "ALL" || (tc.priority || "Medium") === riskFilter;
      const matchStatus = statusFilter === "ALL" || (tc.status || "Generated") === statusFilter;
      
      return matchSearch && matchMethodology && matchRisk && matchStatus;
    });
  }, [allTests, searchQuery, methodologyFilter, riskFilter, statusFilter]);

  // Initial selection
  useEffect(() => {
    if (filteredTests.length > 0) {
      const exists = filteredTests.some(tc => tc.test_case_id === selectedTestCaseId);
      if (!exists) {
        setSelectedTestCaseId(filteredTests[0].test_case_id);
      }
    } else {
      setSelectedTestCaseId(null);
    }
  }, [filteredTests, selectedTestCaseId]);

  // Selected Index & Object
  const selectedIndex = useMemo(() => {
    if (!selectedTestCaseId) return -1;
    return filteredTests.findIndex(tc => tc.test_case_id === selectedTestCaseId);
  }, [filteredTests, selectedTestCaseId]);

  const selectedTestCase = useMemo(() => {
    if (selectedIndex >= 0) return filteredTests[selectedIndex];
    return filteredTests[0] || null;
  }, [filteredTests, selectedIndex]);

  // Navigation handlers
  const handleNext = (e) => {
    if (e) e.stopPropagation();
    if (selectedIndex >= 0 && selectedIndex < filteredTests.length - 1) {
      const nextId = filteredTests[selectedIndex + 1].test_case_id;
      setSelectedTestCaseId(nextId);
      setTimeout(() => {
        const el = document.getElementById(`scenario-card-${nextId}`);
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
        const el = document.getElementById(`scenario-card-${prevId}`);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 50);
    }
  };

  const handleSelectScenario = (id) => {
    setSelectedTestCaseId(id);
    setMobileDetailOpen(true);
  };

  if (!allTests.length) {
    return (
      <div className="text-center text-slate-500 py-16 bg-white rounded-2xl border border-slate-200 shadow-xs m-6">
        <FileText className="h-10 w-10 mx-auto text-slate-300 mb-3" />
        <h3 className="text-base font-bold text-slate-800">No execution scenarios available</h3>
        <p className="text-xs text-slate-500 mt-1">Upload a Cognos DSD document to run the generation pipeline.</p>
      </div>
    );
  }

  return (
    <ScenarioErrorBoundary>
      <div className="flex h-full min-h-0 w-full overflow-hidden bg-[#f8fafc] relative">
        
        {/* Ambient Drifting Particles Background Layer */}
        <DriftingParticles />

        {/* ================================================================ */}
        {/* CENTER / ZONE 2: SCENARIO SIDEBAR (340px–390px)                  */}
        {/* ================================================================ */}
        <div className={`w-full md:w-[350px] lg:w-[370px] xl:w-[380px] shrink-0 flex flex-col bg-white border-r border-slate-200 min-h-0 overflow-hidden relative z-10 ${
          mobileDetailOpen ? "hidden md:flex" : "flex"
        }`}>
          
          {/* Top Navigator Header */}
          <div className="p-3 border-b border-slate-100 space-y-2 bg-white shrink-0">
            {/* Project Context Box in Sidebar (Phase 16 - Optional) */}
            {activeContext && (activeContext.work_item_id || activeContext.work_item_title || activeContext.work_type) && (
              <div className="p-2.5 bg-slate-50 border border-slate-200/80 rounded-xl space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1">
                    <Briefcase className="h-3 w-3 text-blue-600" />
                    Project Context
                  </span>
                  {activeContext.work_type && (
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded font-mono ${
                      activeContext.work_type === "DEFECT" ? "bg-amber-100 text-amber-800" : "bg-blue-100 text-blue-800"
                    }`}>
                      {activeContext.work_type === "DEFECT" ? "Defect" : "CR"}
                    </span>
                  )}
                </div>
                {activeContext.work_item_id && (
                  <div className="text-xs font-bold text-slate-900 font-mono">
                    {activeContext.work_item_id}
                  </div>
                )}
                {activeContext.work_item_title && (
                  <div className="text-[11px] text-slate-600 font-medium line-clamp-1" title={activeContext.work_item_title}>
                    {activeContext.work_item_title}
                  </div>
                )}
              </div>
            )}

            <div>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-slate-900 tracking-tight flex items-center gap-1.5">
                  <FileCheck className="h-4 w-4 text-blue-600" />
                  Execution Scenarios
                </h2>
                <span className="text-[11px] font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded-full font-mono">
                  {filteredTests.length}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 font-normal mt-0.5">
                Generated validation procedures
              </p>
            </div>

            {/* Search Input */}
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                <Search className="h-3.5 w-3.5" />
              </div>
              <input
                type="text"
                placeholder="Search scenarios..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="block w-full rounded-lg border border-slate-200 bg-slate-50/70 py-1.5 pl-8 pr-3 text-xs text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all shadow-2xs"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute inset-y-0 right-0 flex items-center pr-2.5 text-slate-400 hover:text-slate-600"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {/* Compact Filters */}
            <div className="grid grid-cols-3 gap-1.5">
              <select
                value={methodologyFilter}
                onChange={(e) => setMethodologyFilter(e.target.value)}
                aria-label="Filter by methodology"
                className="rounded-lg border border-slate-200 bg-slate-50/50 py-1 px-1.5 text-[11px] font-medium text-slate-700 focus:border-blue-500 focus:outline-none truncate"
              >
                <option value="ALL">Methodology: All</option>
                {methodologies.filter(m => m !== "ALL").map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>

              <select
                value={riskFilter}
                onChange={(e) => setRiskFilter(e.target.value)}
                aria-label="Filter by risk"
                className="rounded-lg border border-slate-200 bg-slate-50/50 py-1 px-1.5 text-[11px] font-medium text-slate-700 focus:border-blue-500 focus:outline-none truncate"
              >
                <option value="ALL">Risk: All</option>
                {risks.filter(r => r !== "ALL").map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                aria-label="Filter by status"
                className="rounded-lg border border-slate-200 bg-slate-50/50 py-1 px-1.5 text-[11px] font-medium text-slate-700 focus:border-blue-500 focus:outline-none truncate"
              >
                <option value="ALL">Status: All</option>
                {statuses.filter(s => s !== "ALL").map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

          </div>

          {/* Scrollable Scenario Cards (Independent Scroll) */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1.5 focus:outline-none bg-slate-50/30">
            {filteredTests.map((tc) => {
              const isSelected = tc.test_case_id === selectedTestCaseId;
              const bTitle = getBusinessScenarioTitle(tc);
              const risk = tc.priority || "Medium";
              const riskPill = risk.toLowerCase() === 'high' 
                ? 'bg-red-50 text-red-700 border-red-200' 
                : risk.toLowerCase() === 'low' 
                ? 'bg-slate-100 text-slate-600 border-slate-200' 
                : 'bg-amber-50 text-amber-700 border-amber-200';
              
              const status = tc.status || "Generated";

              return (
                <button
                  key={tc.test_case_id}
                  id={`scenario-card-${tc.test_case_id}`}
                  type="button"
                  onClick={() => handleSelectScenario(tc.test_case_id)}
                  className={`w-full text-left p-3 rounded-xl transition-all duration-150 relative border ${
                    isSelected
                      ? "bg-blue-50/50 border-slate-300 border-l-4 border-l-blue-600 shadow-xs"
                      : "bg-white border-slate-200 border-l-4 border-l-transparent hover:border-slate-300 hover:bg-slate-50/80 shadow-2xs"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <h3 className="text-[13px] font-semibold text-slate-900 line-clamp-1 leading-snug">
                      {bTitle}
                    </h3>
                    <span className={`text-[10px] font-semibold px-1.5 py-0.2 rounded border shrink-0 ${riskPill}`}>
                      {risk}
                    </span>
                  </div>

                  <div className="font-mono text-xs text-slate-500 mb-1.5">
                    {tc.test_case_id}
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-100">
                    <span className="truncate max-w-[200px]" title={tc.source_section || "Report Layout"}>
                      {tc.source_section || "Report Layout"}
                    </span>
                    <span className="flex items-center gap-1 font-medium text-emerald-600">
                      <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                      <span>{status}</span>
                    </span>
                  </div>
                </button>
              );
            })}

            {filteredTests.length === 0 && (
              <div className="text-center py-10 px-4 bg-white rounded-xl border border-slate-200 m-2">
                <Search className="h-6 w-6 text-slate-300 mx-auto mb-2" />
                <p className="text-xs font-semibold text-slate-700">No scenarios match criteria</p>
                <p className="text-[11px] text-slate-400 mt-0.5">Try clearing filters or search query</p>
              </div>
            )}
          </div>

        </div>

        {/* ================================================================ */}
        {/* RIGHT / ZONE 3: SELECTED SCENARIO WORKSPACE (FLEX-1)             */}
        {/* ================================================================ */}
        <div className={`flex-1 flex flex-col bg-white min-h-0 overflow-hidden relative z-10 ${
          mobileDetailOpen ? "flex" : "hidden md:flex"
        }`}>
          
          {/* Mobile Back Button Bar */}
          {mobileDetailOpen && (
            <div className="md:hidden bg-white border-b border-slate-200 p-2.5 flex items-center gap-2">
              <button
                type="button"
                onClick={() => setMobileDetailOpen(false)}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 bg-blue-50 px-3 py-1.5 rounded-lg"
              >
                <ArrowLeft className="h-4 w-4" /> Back to Scenario List
              </button>
            </div>
          )}

          {/* Scrollable Detail Workspace Area */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-6.5 focus:outline-none bg-slate-50/30">
            {selectedTestCase ? (
              <ScenarioWorkspaceDetail
                tc={selectedTestCase}
                selectedIndex={selectedIndex}
                totalCount={filteredTests.length}
                onPrev={handlePrev}
                onNext={handleNext}
                setZoomImage={setZoomImage}
                executionState={executionState}
                onUpdateExecution={handleUpdateExecution}
              />
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-8 bg-white rounded-2xl border border-slate-200 shadow-2xs">
                <FileText className="h-12 w-12 text-slate-300 mb-3" />
                <h3 className="text-base font-bold text-slate-800">Select a Test Scenario</h3>
                <p className="text-xs text-slate-500 max-w-sm mt-1">
                  Choose any execution scenario from the left navigator to inspect procedures, validation SQL, and DSD proof.
                </p>
              </div>
            )}
          </div>

        </div>

        {/* ── Interactive Snipping-Tool DSD Evidence Viewer Modal ─────────── */}
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
