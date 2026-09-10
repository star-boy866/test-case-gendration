import { useState, useRef, useEffect, useMemo } from "react";
import { useSearchParams, useNavigate, Navigate } from "react-router-dom";
import { 
  UploadCloud, FileText, Loader2, AlertTriangle, LayoutDashboard, 
  List, Target, CheckSquare, Image as ImageIcon, Download, PlusCircle,
  CheckCircle2, RefreshCw, Briefcase, FileCode2, ShieldAlert, Sparkles, Shield
} from "lucide-react";
import { 
  uploadCognosDocument, 
  downloadCognosExport, 
  detectDsdFormat,
  getCognosRun,
  getLatestCognosRun,
  clearCognosWorkspaceState
} from "../services/api";
import { useAuth } from "../context/AuthContext";

const EMPTY_PROJECT_CONTEXT = {
  run_id: null,
  work_type: "",
  work_item_id: "",
  work_item_title: "",
  state: "",
  report_id: "",
  report_title: ""
};

import DSDIntelligenceSummary from "../components/cognos/DSDIntelligenceSummary";
import TestScenarioExplorer from "../components/cognos/TestScenarioExplorer";
import TestingDimensions from "../components/cognos/TestingDimensions";
import RequirementsView from "../components/cognos/RequirementsView";
import CoverageMatrix from "../components/cognos/CoverageMatrix";
import EvidenceLibrary from "../components/cognos/EvidenceLibrary";
import DataLatticeBackground from "../components/common/DataLatticeBackground";

const TABS = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "requirements", label: "Reports", icon: FileText },
  { id: "scenarios", label: "Test Cases", icon: List },
  { id: "evidence", label: "Evidence", icon: ImageIcon },
  { id: "dimensions", label: "Dimensions", icon: Target },
  { id: "coverage", label: "Settings & Matrix", icon: CheckSquare },
];

const DSD_PROFILES = [
  {
    id: "AUTO",
    label: "Auto Detect",
    displayLabel: "Auto Detect",
    description: "Automatically detect format from document structure",
  },
  {
    id: "NH",
    label: "NH — New Hampshire",
    displayLabel: "NH — New Hampshire",
    description: "New Hampshire MMIS DSD",
  },
  {
    id: "ND",
    label: "ND — North Dakota",
    displayLabel: "ND — North Dakota",
    description: "North Dakota Medicaid MMIS DSD",
  },
  {
    id: "AK",
    label: "AK — Alaska",
    displayLabel: "AK — Alaska",
    description: "Alaska Cognos DSD",
  },
];

export default function CognosDashboard() {
  const { user, isTester } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [loadingRun, setLoadingRun] = useState(false);

  const [file, setFile] = useState(null);
  const [dsdProfile, setDsdProfile] = useState("AUTO");
  const [manualOverride, setManualOverride] = useState(false);
  const [detectionState, setDetectionState] = useState("IDLE"); // IDLE | DETECTING | DETECTED | LOW_CONFIDENCE | UNKNOWN
  const [detectedInfo, setDetectedInfo] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResultState] = useState(() => {
    try {
      const cached = sessionStorage.getItem("cognos_active_result");
      if (cached) {
        const parsed = JSON.parse(cached);
        const search = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
        if (search && search.get("new") === "true") {
          return null;
        }
        const queryRunId = search?.get("run_id");
        const storedRunId = localStorage.getItem("cognos_active_run_id");
        const targetId = queryRunId || storedRunId;
        if (targetId && (String(parsed.run_id) === String(targetId) || String(parsed.id) === String(targetId))) {
          return parsed;
        }
      }
    } catch {}
    return null;
  });

  const setResult = (val) => {
    setResultState(val);
    try {
      if (val) {
        sessionStorage.setItem("cognos_active_result", JSON.stringify(val));
        const rId = val.run_id || val.id;
        if (rId) localStorage.setItem("cognos_active_run_id", String(rId));
      } else {
        sessionStorage.removeItem("cognos_active_result");
      }
    } catch {}
  };

  const handleStartNewProject = () => {
    clearCognosWorkspaceState();
    setProjectContext(EMPTY_PROJECT_CONTEXT);
    setResult(null);
    setFile(null);
    setDetectedInfo(null);
    setDetectionState("IDLE");
    setManualOverride(false);
    setDsdProfile("AUTO");
    navigate("/cognos?new=true", { replace: true });
  };
  const [error, setError] = useState("");
  const [validationErrors, setValidationErrors] = useState([]);
  const fileInputRef = useRef(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [activeTab, setActiveTab] = useState("dashboard");

  const visibleTabs = useMemo(() => {
    if (isTester) {
      return TABS.filter((t) => ["dashboard", "scenarios", "evidence"].includes(t.id));
    }
    return TABS;
  }, [isTester]);

  const queryRunId = searchParams.get("run_id");
  const isNewQuery = searchParams.get("new") === "true";

  // Auto-sync run from query params or check available active run
  useEffect(() => {
    if (isNewQuery) {
      clearCognosWorkspaceState();
      setResult(null);
      setFile(null);
      setDetectedInfo(null);
      setDetectionState("IDLE");
      setLoadingRun(false);
      setProjectContext(EMPTY_PROJECT_CONTEXT);
      return;
    }

    const runIdParam = queryRunId || localStorage.getItem("cognos_active_run_id");

    if (runIdParam) {
      // If we already have this exact run loaded in memory, don't refetch or flash spinner
      if (result && (String(result.run_id) === String(runIdParam) || String(result.id) === String(runIdParam))) {
        try {
          localStorage.setItem("cognos_active_run_id", String(runIdParam));
          const syncContext = {
            run_id: result.run_id || result.id,
            report_id: result.report_id || "",
            report_title: result.report_title || result.report_definition?.metadata?.report_title || "Cognos Report",
            work_item_title: result.work_item_title || result.report_title || result.report_definition?.metadata?.report_title || "",
            work_item_id: result.work_item_id || "",
            work_type: result.work_type || "CR",
            state: result.state || ""
          };
          setProjectContext(syncContext);
          localStorage.setItem("cognos_project_context", JSON.stringify(syncContext));
        } catch {}
        if (!queryRunId) {
          navigate(`/cognos?run_id=${runIdParam}&tab=${activeTab || "dashboard"}`, { replace: true });
        }
        return;
      }

      setLoadingRun(true);
      getCognosRun(runIdParam)
        .then((res) => {
          setResult(res.data);
          try {
            localStorage.setItem("cognos_active_run_id", String(runIdParam));
            const syncContext = {
              run_id: res.data.run_id || res.data.id,
              report_id: res.data.report_id || "",
              report_title: res.data.report_title || res.data.report_definition?.metadata?.report_title || "Cognos Report",
              work_item_title: res.data.work_item_title || res.data.report_title || res.data.report_definition?.metadata?.report_title || "",
              work_item_id: res.data.work_item_id || "",
              work_type: res.data.work_type || "CR",
              state: res.data.state || ""
            };
            setProjectContext(syncContext);
            localStorage.setItem("cognos_project_context", JSON.stringify(syncContext));
          } catch {}
          if (!queryRunId) {
            navigate(`/cognos?run_id=${runIdParam}&tab=${activeTab || "dashboard"}`, { replace: true });
          }
        })
        .catch((err) => {
          console.error("Failed to load run:", err);
          if (err.response?.status === 403 || err.response?.status === 404) {
            try {
              localStorage.removeItem("cognos_active_run_id");
              sessionStorage.removeItem("cognos_active_result");
            } catch {}
            setResult(null);
            setError(err.response?.data?.detail || "Run not found or access denied.");
          }
        })
        .finally(() => setLoadingRun(false));
    } else {
      // If there is NO active/generated run, display clean DSD Upload / Test Case Setup page
      setResult(null);
      setFile(null);
      setDetectedInfo(null);
      setDetectionState("IDLE");
      setLoadingRun(false);
      setProjectContext(EMPTY_PROJECT_CONTEXT);
    }
  }, [queryRunId, isNewQuery]);

  // Sync tab from URL query params (e.g. ?tab=scenarios or ?tab=dashboard)
  useEffect(() => {
    const tabParam = searchParams.get("tab");
    if (tabParam && visibleTabs.some((t) => t.id === tabParam)) {
      setActiveTab(tabParam);
    } else if (tabParam && isTester && ["requirements", "dimensions", "coverage"].includes(tabParam)) {
      setActiveTab("dashboard");
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("tab", "dashboard");
        return next;
      }, { replace: true });
    }
  }, [searchParams.get("tab"), visibleTabs, isTester]);

  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("tab", tabId);
      return next;
    }, { replace: true });
  };

  // Project Context State (Phase 16 - Optional)
  const [projectContext, setProjectContext] = useState(() => {
    try {
      const search = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
      if (search && search.get("new") === "true") {
        return EMPTY_PROJECT_CONTEXT;
      }
      const queryRunId = search?.get("run_id");
      const storedRunId = typeof window !== "undefined" ? localStorage.getItem("cognos_active_run_id") : null;
      const targetId = queryRunId || storedRunId;
      const cached = typeof window !== "undefined" ? localStorage.getItem("cognos_project_context") : null;
      if (cached && targetId) {
        const parsed = JSON.parse(cached);
        if (String(parsed.run_id) === String(targetId)) {
          return {
            run_id: parsed.run_id || targetId,
            work_type: parsed.work_type || "",
            work_item_id: parsed.work_item_id || "",
            work_item_title: parsed.work_item_title || "",
            state: parsed.state || "",
            report_id: parsed.report_id || "",
            report_title: parsed.report_title || ""
          };
        }
      }
    } catch {}
    return EMPTY_PROJECT_CONTEXT;
  });

  const handleContextChange = (field, value) => {
    setProjectContext((prev) => {
      const next = { ...prev, [field]: value };
      try {
        localStorage.setItem("cognos_project_context", JSON.stringify(next));
      } catch {}
      return next;
    });
    if (validationErrors.length > 0) {
      setValidationErrors([]);
    }
  };

  const handleWorkTypeToggle = (type) => {
    const nextType = projectContext.work_type === type ? "" : type;
    handleContextChange("work_type", nextType);
  };

  const handleFileChange = async (e) => {
    const selected = e.target.files[0];
    if (selected) {
      if (!selected.name.toLowerCase().endsWith(".docx")) {
        setError("Please upload a standard Word Document (.docx).");
        setFile(null);
        setDetectionState("IDLE");
        setDetectedInfo(null);
      } else {
        setError("");
        setValidationErrors([]);
        setFile(selected);
        setResult(null);

        // Run auto-detection
        setDetectionState("DETECTING");
        try {
          const res = await detectDsdFormat(selected);
          setDetectedInfo(res.data);
          
          // Auto-populate report metadata if detected
          if (res.data?.report_id || res.data?.report_title) {
            setProjectContext(prev => ({
              ...prev,
              report_id: res.data.report_id || prev.report_id,
              report_title: res.data.report_title || prev.report_title,
              state: res.data.detected_format !== "UNKNOWN" ? res.data.detected_format : prev.state
            }));
          }

          if (res.data.status === "DETECTED") {
            setDetectionState("DETECTED");
            if (!manualOverride) {
              setDsdProfile(res.data.detected_format);
            }
          } else if (res.data.status === "LOW_CONFIDENCE") {
            setDetectionState("LOW_CONFIDENCE");
            if (!manualOverride) {
              setDsdProfile(res.data.detected_format);
            }
          } else {
            setDetectionState("UNKNOWN");
            if (!manualOverride) {
              setDsdProfile("AUTO");
            }
          }
        } catch (err) {
          console.warn("Format auto-detection failed:", err);
          setDetectionState("UNKNOWN");
          setDetectedInfo({
            detected_format: "UNKNOWN",
            confidence: "None",
            display_name: "Unknown",
            message: "Unable to determine DSD format. Please select NH / ND / AK manually."
          });
        }
      }
    }
  };

  const handleProfileSelect = (profileId) => {
    setDsdProfile(profileId);
    if (profileId === "AUTO") {
      setManualOverride(false);
      if (detectedInfo && detectedInfo.detected_format !== "UNKNOWN") {
        setDsdProfile(detectedInfo.detected_format);
      }
    } else {
      setManualOverride(true);
    }
  };

  const validateInputs = () => {
    const errs = [];
    if (!file) {
      errs.push("Please upload a Cognos Report Definition (.docx).");
    }
    return errs;
  };

  const handleUpload = async () => {
    const errs = validateInputs();
    if (errs.length > 0) {
      setValidationErrors(errs);
      return;
    }

    setIsProcessing(true);
    setError("");
    setValidationErrors([]);

    // Determine profile to send
    const effectiveProfile = manualOverride ? dsdProfile : (detectedInfo?.detected_format || dsdProfile || "AUTO");

    try {
      const response = await uploadCognosDocument({ 
        file, 
        dsdProfile: effectiveProfile,
        workType: projectContext.work_type,
        workItemId: projectContext.work_item_id,
        workItemTitle: projectContext.work_item_title,
      });
      const resData = response.data;
      
      // Update canonical project context from result
      const detectedState = effectiveProfile !== "AUTO" ? effectiveProfile : (detectedInfo?.detected_format || "NH");
      const detectedRepId = resData.report_id || resData.report_definition?.metadata?.report_id || projectContext.report_id || "Report";
      const detectedRepTitle = resData.report_title || resData.report_definition?.metadata?.report_title || projectContext.report_title || "Cognos Report";

      const updatedContext = {
        ...projectContext,
        run_id: resData?.run_id || resData?.id,
        state: detectedState,
        report_id: detectedRepId,
        report_title: detectedRepTitle,
      };

      setProjectContext(updatedContext);
      try {
        localStorage.setItem("cognos_project_context", JSON.stringify(updatedContext));
      } catch {}

      const generatedId = resData?.run_id || resData?.id;
      if (!generatedId) {
        throw new Error("Backend did not return a valid run_id.");
      }

      // 1. Immediately persist new active run
      try {
        localStorage.setItem("cognos_active_run_id", String(generatedId));
        sessionStorage.setItem("cognos_active_result", JSON.stringify(resData));
      } catch {}

      // 2. Set result and dashboard tab in state
      setResult(resData);
      setActiveTab("dashboard");
      setLoadingRun(false);

      // 3. Navigate directly to canonical route
      navigate(`/cognos?run_id=${generatedId}&tab=dashboard`, { replace: true });
    } catch (err) {
      setError(
        err.response?.data?.detail || err.message || "An error occurred during generation."
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

  const renderActiveTab = () => {
    if (isTester && ["requirements", "dimensions", "coverage"].includes(activeTab)) {
      return <DSDIntelligenceSummary result={result} projectContext={projectContext} />;
    }
    switch (activeTab) {
      case "dashboard": return <DSDIntelligenceSummary result={result} projectContext={projectContext} />;
      case "scenarios": return <TestScenarioExplorer result={result} projectContext={projectContext} />;
      case "dimensions": return <TestingDimensions result={result} projectContext={projectContext} />;
      case "requirements": return <RequirementsView result={result} projectContext={projectContext} />;
      case "coverage": return <CoverageMatrix result={result} projectContext={projectContext} />;
      case "evidence": return <EvidenceLibrary result={result} projectContext={projectContext} />;
      default: return <DSDIntelligenceSummary result={result} projectContext={projectContext} />;
    }
  };

  // ── Loading Guard: Show clean spinner while active run is loading ───
  if (loadingRun && !result) {
    return (
      <div className="flex flex-col items-center justify-center h-full w-full bg-[#f8fafc] text-slate-500">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600 mb-3" />
        <p className="text-sm font-medium">Loading test case workspace…</p>
      </div>
    );
  }

  // ── Upload View (Compact, Single Viewport Layout) ─────────────────────────
  if (!result) {
    let badgeText = "Auto Detect";
    if (manualOverride) {
      const p = DSD_PROFILES.find((p) => p.id === dsdProfile);
      badgeText = p?.displayLabel || dsdProfile;
    } else if (file) {
      if (detectionState === "DETECTED") {
        badgeText = `${detectedInfo?.display_name || dsdProfile}`;
      } else if (detectionState === "LOW_CONFIDENCE") {
        badgeText = `${detectedInfo?.display_name || dsdProfile} (Low)`;
      } else if (detectionState === "UNKNOWN") {
        badgeText = "Unknown Format";
      } else if (detectionState === "DETECTING") {
        badgeText = "Detecting...";
      }
    }

    const detectedReportId = detectedInfo?.report_id || projectContext.report_id;
    const detectedReportTitle = detectedInfo?.report_title || projectContext.report_title;

    return (
      <div className="relative h-full w-full overflow-y-auto flex flex-col justify-center p-3 sm:p-4 bg-[#f8fafc] text-slate-900">
        <DataLatticeBackground />
        <div className="relative z-10 max-w-4xl w-full mx-auto">
          
          {/* Main Setup Card (Compact Viewport Container) */}
          <div className="rounded-2xl border border-slate-200 bg-white p-3.5 sm:p-4 lg:p-5 shadow-xs flex flex-col gap-3">
            
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <div>
                <h1 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-blue-600" />
                  DSD Intelligence Dashboard
                </h1>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Configure test context, select DSD profile, and upload a Cognos Report Definition (.docx).
                </p>
              </div>
              <span className="hidden sm:inline-flex text-[10px] font-semibold px-2 py-0.5 rounded-full border border-blue-200 bg-blue-50 text-blue-700">
                Cognos Test Case Studio
              </span>
            </div>

            {/* ── 1. TEST CASE CONTEXT (Single Compact Row) ───────────────────── */}
            <div className="bg-slate-50/70 border border-slate-200/80 rounded-xl p-2.5 sm:p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <Briefcase className="h-3 w-3 text-blue-600" />
                  Test Case Context
                </span>
                <span className="text-[10px] text-slate-400 font-medium hidden sm:inline">Add CR/Defect details for project traceability (optional)</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-12 gap-2 items-end">
                {/* Work Type */}
                <div className="sm:col-span-3 space-y-0.5">
                  <label className="text-[11px] font-semibold text-slate-700 block">Work Type</label>
                  <div className="grid grid-cols-2 gap-1 p-0.5 bg-white border border-slate-200 rounded-lg shadow-2xs h-[34px]">
                    <button
                      type="button"
                      onClick={() => handleWorkTypeToggle("CR")}
                      className={`flex items-center justify-center gap-1 rounded-md text-[11px] font-bold transition-all ${
                        projectContext.work_type === "CR" ? "bg-blue-600 text-white shadow-xs" : "text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      <span className={`h-1 w-1 rounded-full ${projectContext.work_type === "CR" ? "bg-white" : "bg-blue-600"}`} />
                      CR
                    </button>
                    <button
                      type="button"
                      onClick={() => handleWorkTypeToggle("DEFECT")}
                      className={`flex items-center justify-center gap-1 rounded-md text-[11px] font-bold transition-all ${
                        projectContext.work_type === "DEFECT" ? "bg-amber-600 text-white shadow-xs" : "text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      <span className={`h-1 w-1 rounded-full ${projectContext.work_type === "DEFECT" ? "bg-white" : "bg-amber-600"}`} />
                      Defect
                    </button>
                  </div>
                </div>

                {/* CR / Defect ID */}
                <div className="sm:col-span-3 space-y-0.5">
                  <label className="text-[11px] font-semibold text-slate-700 block">CR / Defect ID</label>
                  <input
                    type="text"
                    value={projectContext.work_item_id}
                    onChange={(e) => handleContextChange("work_item_id", e.target.value)}
                    placeholder="e.g. CR 18175"
                    className="w-full h-[34px] px-2.5 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs"
                  />
                </div>

                {/* CR / Defect Title */}
                <div className="sm:col-span-6 space-y-0.5">
                  <label className="text-[11px] font-semibold text-slate-700 block">CR / Defect Title</label>
                  <input
                    type="text"
                    value={projectContext.work_item_title}
                    onChange={(e) => handleContextChange("work_item_title", e.target.value)}
                    placeholder="Enter change request or defect title"
                    className="w-full h-[34px] px-2.5 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs"
                  />
                </div>
              </div>
            </div>

            {/* ── 2. DSD FORMAT SELECTION ─────────────────────────────────────── */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-bold text-slate-900">
                  Select DSD Format
                </label>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border transition-colors ${
                  detectionState === "DETECTED" && !manualOverride
                    ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                    : detectionState === "UNKNOWN" && !manualOverride
                    ? "text-rose-700 bg-rose-50 border-rose-200"
                    : "text-blue-700 bg-blue-50 border-blue-200"
                }`}>
                  Format: {badgeText}
                </span>
              </div>

              {/* Format Pills */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {DSD_PROFILES.map((profile) => {
                  const isSelected = (!manualOverride && profile.id === "AUTO") || (manualOverride && dsdProfile === profile.id);
                  return (
                    <button
                      key={profile.id}
                      type="button"
                      onClick={() => handleProfileSelect(profile.id)}
                      className={`flex flex-col text-left p-2 rounded-lg border transition-all ${
                        isSelected
                          ? "border-blue-600 bg-blue-50/70 ring-1 ring-blue-500 shadow-2xs"
                          : "border-slate-200 hover:border-slate-300 hover:bg-slate-50/70 bg-white"
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className={`h-1.5 w-1.5 rounded-full ${isSelected ? "bg-blue-600" : "bg-slate-300"}`} />
                        <span className={`text-[11px] font-bold ${isSelected ? "text-blue-950" : "text-slate-800"}`}>
                          {profile.label}
                        </span>
                      </div>
                      <span className="text-[9px] text-slate-500 pl-3 line-clamp-1 mt-0.5">
                        {profile.description}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* ── 3. DETECTED REPORT METADATA (Read-Only) ──────────────────────── */}
            {file && (detectedReportId || detectedReportTitle || detectedInfo) && (
              <div className="bg-emerald-50/70 border border-emerald-200/80 rounded-xl p-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-fadeIn">
                <div className="flex items-center gap-2.5 min-w-0">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-900">
                        Detected Report
                      </span>
                      {detectedReportId && (
                        <span className="font-mono text-xs font-bold text-emerald-800 bg-white px-2 py-0.5 border border-emerald-200 rounded">
                          {detectedReportId}
                        </span>
                      )}
                      {detectedInfo?.display_name && (
                        <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-100/60 px-2 py-0.5 rounded-full">
                          {detectedInfo.display_name}
                        </span>
                      )}
                    </div>
                    {detectedReportTitle && (
                      <p className="text-xs text-emerald-950 font-medium mt-0.5 truncate">
                        {detectedReportTitle}
                      </p>
                    )}
                  </div>
                </div>

                {detectionState === "DETECTED" && !manualOverride && (
                  <button
                    type="button"
                    onClick={() => setManualOverride(true)}
                    className="text-[11px] font-semibold text-emerald-800 bg-white hover:bg-emerald-100/50 border border-emerald-300 px-2.5 py-1 rounded-md shadow-2xs shrink-0"
                  >
                    Change Format
                  </button>
                )}
              </div>
            )}

            {/* ── 4. UPLOAD DROPZONE & ACTIONS ─────────────────────────────────── */}
            <div
              className={`flex flex-col sm:flex-row items-center justify-between gap-3 rounded-xl border-2 border-dashed p-3 sm:p-4 transition-colors ${
                file ? "border-blue-300 bg-blue-50/40" : "border-slate-300 bg-slate-50/60 hover:bg-slate-100/60"
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
                  <div className="flex items-center gap-3 text-left">
                    <div className="p-2 bg-white rounded-xl shadow-2xs border border-slate-200 text-blue-600 shrink-0">
                      <UploadCloud className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-xs sm:text-sm font-bold text-slate-900">
                        Upload Cognos Report Definition
                      </p>
                      <p className="text-[10px] sm:text-[11px] text-slate-500">
                        Supports NH, ND, and AK Cognos DSD Word Documents (.docx)
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full sm:w-auto rounded-lg bg-white px-3.5 py-1.5 text-xs font-bold text-slate-700 shadow-2xs border border-slate-300 hover:bg-slate-50 transition-all"
                  >
                    Browse Files
                  </button>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-2.5 min-w-0 text-left">
                    <div className="p-2 bg-white rounded-xl shadow-2xs border border-blue-200 text-blue-600 shrink-0">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs sm:text-sm font-bold text-slate-900 truncate">
                        {file.name}
                      </p>
                      <p className="text-[10px] text-slate-500">
                        {(file.size / 1024).toFixed(1)} KB • Word Document
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 w-full sm:w-auto shrink-0">
                    <button
                      type="button"
                      onClick={() => setFile(null)}
                      className="flex-1 sm:flex-none rounded-lg bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs border border-slate-200 hover:bg-slate-50"
                    >
                      Change File
                    </button>
                    <button
                      type="button"
                      onClick={handleUpload}
                      disabled={isProcessing}
                      className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 px-4 py-1.5 text-xs font-bold text-white shadow-sm disabled:opacity-60 transition-all cursor-pointer"
                    >
                      {isProcessing ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Generating...
                        </>
                      ) : (
                        "Generate Intelligence"
                      )}
                    </button>
                  </div>
                </>
              )}
            </div>

            {/* Validation & Error Notices */}
            {validationErrors.length > 0 && (
              <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900 border border-amber-200 space-y-1">
                <div className="flex items-center gap-1.5 font-bold text-amber-950">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                  Missing Required Context:
                </div>
                <ul className="list-disc list-inside text-[11px] pl-1 space-y-0.5 text-amber-800">
                  {validationErrors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            {error && (
              <div className="flex items-start gap-2.5 rounded-lg bg-red-50 p-3 text-xs text-red-800 border border-red-200">
                <AlertTriangle className="h-4 w-4 shrink-0 text-red-600" />
                <div className="font-medium">{error}</div>
              </div>
            )}

          </div>

        </div>
      </div>
    );
  }

  // ── Dashboard View ─────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col sm:flex-row h-full w-full bg-[#f8fafc] overflow-hidden min-h-0">
      {/* ── ZONE 1 Mobile Horizontal Bar (< sm) ─────────────── */}
      <div className="sm:hidden flex items-center justify-between border-b border-slate-200 bg-white px-2.5 py-1.5 shrink-0 z-20 gap-1.5 shadow-2xs overflow-x-auto no-scrollbar">
        <div className="flex items-center gap-1.5 min-w-0">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-900 text-white font-mono font-bold text-[10px] tracking-tight shrink-0">
            {result.report_id ? result.report_id.slice(0, 3) : "DSD"}
          </div>
          <div className="flex items-center gap-1">
            {visibleTabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => handleTabChange(tab.id)}
                  title={tab.label}
                  aria-label={tab.label}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 ${
                    isActive 
                      ? "bg-blue-50 text-blue-700 font-bold shadow-2xs" 
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                >
                  <Icon className={`h-3.5 w-3.5 ${isActive ? "text-blue-600" : "text-slate-400"}`} />
                  <span className="truncate">{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0 pl-1.5 border-l border-slate-100">
          <button
            type="button"
            onClick={handleDownload}
            disabled={isDownloading}
            title="Export to Excel"
            aria-label="Export to Excel"
            className="h-7 w-7 flex items-center justify-center rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-70 transition-all shadow-2xs"
          >
            {isDownloading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
          </button>
          <button
            type="button"
            onClick={handleStartNewProject}
            title="Upload New DSD / New Project"
            aria-label="Upload New DSD / New Project"
            className="h-7 w-7 flex items-center justify-center rounded-lg bg-white border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-800 transition-all shadow-2xs"
          >
            <PlusCircle className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* ── ZONE 1: Global Left Icon Rail (>= sm: 56px) ─────────────── */}
      <div 
        className="hidden sm:flex w-[56px] flex-shrink-0 bg-white border-r border-slate-200 flex-col items-center py-3 shadow-2xs z-20"
      >
        {/* Top Report Suite Badge */}
        <div className="mb-3 flex flex-col items-center justify-center" title={result.report_id || "DSD Suite"}>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-white font-mono font-bold text-[11px] tracking-tight shadow-2xs">
            {result.report_id ? result.report_id.slice(0, 3) : "DSD"}
          </div>
        </div>
        
        {/* Navigation Items (Clean 56px Line Icon Rail) */}
        <nav className="flex-1 flex flex-col items-center space-y-1.5 w-full px-1.5">
          {visibleTabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                title={tab.label}
                aria-label={tab.label}
                className={`relative w-10 h-10 flex items-center justify-center rounded-xl transition-all duration-150 group ${
                  isActive 
                    ? "bg-blue-50 text-blue-600 font-semibold shadow-2xs" 
                    : "text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                }`}
              >
                {/* Active left pill indicator */}
                {isActive && (
                  <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-blue-600" />
                )}
                <Icon className={`h-4.5 w-4.5 ${isActive ? "text-blue-600" : "text-slate-400 group-hover:text-slate-600"}`} />
              </button>
            );
          })}
        </nav>
        
        {/* Footer Actions (Export, New Run) */}
        <div className="pt-2 border-t border-slate-100 flex flex-col items-center space-y-2 w-full px-1.5">
          <button
            type="button"
            onClick={handleDownload}
            disabled={isDownloading}
            title="Export to Excel"
            aria-label="Export to Excel"
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-70 transition-all shadow-2xs"
          >
            {isDownloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          </button>
          
          <button
            type="button"
            onClick={handleStartNewProject}
            title="Upload New DSD / New Project"
            aria-label="Upload New DSD / New Project"
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-white border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-800 transition-all shadow-2xs"
          >
            <PlusCircle className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* ── Main Content Area ─────────────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 overflow-hidden bg-[#f8fafc] flex flex-col">
        <main className={`flex-1 overflow-hidden min-h-0 ${activeTab === "scenarios" ? "p-0" : "p-3 sm:p-4 lg:p-4.5 flex flex-col"}`}>
          <div className="h-full min-h-0 flex flex-col">
            {renderActiveTab()}
          </div>
        </main>
      </div>
    </div>
  );
}
