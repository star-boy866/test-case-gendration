import { useState, useRef } from "react";
import { 
  UploadCloud, FileText, Loader2, AlertTriangle, LayoutDashboard, 
  List, Target, CheckSquare, Image as ImageIcon, Download, PlusCircle,
  ChevronLeft, ChevronRight, CheckCircle2, RefreshCw
} from "lucide-react";
import { uploadCognosDocument, downloadCognosExport, detectDsdFormat } from "../services/api";

import DSDIntelligenceSummary from "../components/cognos/DSDIntelligenceSummary";
import TestScenarioExplorer from "../components/cognos/TestScenarioExplorer";
import TestingDimensions from "../components/cognos/TestingDimensions";
import RequirementsView from "../components/cognos/RequirementsView";
import CoverageMatrix from "../components/cognos/CoverageMatrix";
import EvidenceLibrary from "../components/cognos/EvidenceLibrary";

const TABS = [
  { id: "dashboard", label: "Intelligence Dashboard", icon: LayoutDashboard },
  { id: "scenarios", label: "Execution Scenarios", icon: List },
  { id: "dimensions", label: "Testing Dimensions", icon: Target },
  { id: "requirements", label: "Requirements", icon: FileText },
  { id: "coverage", label: "Coverage Matrix", icon: CheckSquare },
  { id: "evidence", label: "Evidence Library", icon: ImageIcon },
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
    description: "North Dakota Medicaid Systems Project MMIS DSD",
  },
  {
    id: "AK",
    label: "AK — Alaska",
    displayLabel: "AK — Alaska",
    description: "Alaska Cognos DSD",
  },
];

export default function CognosDashboard() {
  const [file, setFile] = useState(null);
  const [dsdProfile, setDsdProfile] = useState("AUTO");
  const [manualOverride, setManualOverride] = useState(false);
  const [detectionState, setDetectionState] = useState("IDLE"); // IDLE | DETECTING | DETECTED | LOW_CONFIDENCE | UNKNOWN
  const [detectedInfo, setDetectedInfo] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem("cognos_sidebar_collapsed") === "true";
    } catch {
      return false;
    }
  });

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("cognos_sidebar_collapsed", String(next));
      } catch {}
      return next;
    });
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
        setFile(selected);
        setResult(null);

        // Run auto-detection
        setDetectionState("DETECTING");
        try {
          const res = await detectDsdFormat(selected);
          setDetectedInfo(res.data);
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

  const handleUpload = async () => {
    if (!file) return;
    setIsProcessing(true);
    setError("");

    // Determine profile to send
    const effectiveProfile = manualOverride ? dsdProfile : (detectedInfo?.detected_format || dsdProfile || "AUTO");

    try {
      const response = await uploadCognosDocument({ file, dsdProfile: effectiveProfile });
      setResult(response.data);
      setActiveTab("dashboard");
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

  const renderActiveTab = () => {
    switch (activeTab) {
      case "dashboard": return <DSDIntelligenceSummary result={result} />;
      case "scenarios": return <TestScenarioExplorer result={result} />;
      case "dimensions": return <TestingDimensions result={result} />;
      case "requirements": return <RequirementsView result={result} />;
      case "coverage": return <CoverageMatrix result={result} />;
      case "evidence": return <EvidenceLibrary result={result} />;
      default: return <DSDIntelligenceSummary result={result} />;
    }
  };

  // ── Upload View ────────────────────────────────────────────────────────────
  if (!result) {
    // Current display label for badge
    let badgeText = "Selected DSD Format: Auto Detect";
    if (manualOverride) {
      const p = DSD_PROFILES.find((p) => p.id === dsdProfile);
      badgeText = `Selected DSD Format: ${p?.displayLabel || dsdProfile}`;
    } else if (file) {
      if (detectionState === "DETECTED") {
        badgeText = `Detected DSD Format: ${detectedInfo?.display_name || dsdProfile}`;
      } else if (detectionState === "LOW_CONFIDENCE") {
        badgeText = `Detected DSD Format: ${detectedInfo?.display_name || dsdProfile} (Low Confidence)`;
      } else if (detectionState === "UNKNOWN") {
        badgeText = "Detected DSD Format: Unknown";
      } else if (detectionState === "DETECTING") {
        badgeText = "Detecting DSD format...";
      }
    } else {
      const p = DSD_PROFILES.find((p) => p.id === dsdProfile);
      badgeText = `Selected DSD Format: ${p?.displayLabel || "Auto Detect"}`;
    }

    return (
      <div className="max-w-4xl mx-auto mt-10">
        <div className="mb-8">
          <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">
            DSD Intelligence Dashboard
          </h2>
          <p className="mt-2 text-base text-slate-500">
            Upload a Cognos Report Definition (DOCX) to extract requirements, evaluate methodology rules, and generate an enterprise-grade traceable test suite.
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          {/* Select DSD Format Section */}
          <div className="mb-6 pb-6 border-b border-slate-100">
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-bold text-slate-900">
                Select DSD Format
              </label>
              <span className={`text-xs font-semibold px-3 py-1 rounded-full border transition-colors ${
                detectionState === "DETECTED" && !manualOverride
                  ? "text-emerald-700 bg-emerald-50 border-emerald-200"
                  : detectionState === "UNKNOWN" && !manualOverride
                  ? "text-rose-700 bg-rose-50 border-rose-200"
                  : "text-brand-700 bg-brand-50 border-brand-200"
              }`}>
                {badgeText}
              </span>
            </div>

            {/* Detection Banner if file uploaded */}
            {file && !manualOverride && (
              <div className="mb-4">
                {detectionState === "DETECTING" && (
                  <div className="p-3.5 bg-blue-50/80 border border-blue-200 rounded-xl flex items-center gap-3">
                    <Loader2 className="h-4 w-4 text-blue-600 animate-spin shrink-0" />
                    <p className="text-xs font-semibold text-blue-900">
                      Detecting DSD format...
                    </p>
                  </div>
                )}

                {detectionState === "DETECTED" && detectedInfo && (
                  <div className="p-3.5 bg-emerald-50/80 border border-emerald-200 rounded-xl flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
                      <div>
                        <p className="text-xs font-bold text-emerald-950">
                          Detected: <span className="text-emerald-700">{detectedInfo.display_name}</span>
                        </p>
                        <p className="text-[11px] text-emerald-700 mt-0.5">
                          Confidence: <span className="font-semibold">{detectedInfo.confidence}</span>
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setManualOverride(true)}
                      className="text-xs font-semibold text-emerald-800 bg-white hover:bg-emerald-100/50 border border-emerald-300 px-3 py-1.5 rounded-lg shadow-sm transition-all"
                    >
                      Change Format
                    </button>
                  </div>
                )}

                {detectionState === "UNKNOWN" && (
                  <div className="p-3.5 bg-rose-50/80 border border-rose-200 rounded-xl flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <AlertTriangle className="h-5 w-5 text-rose-600 shrink-0" />
                      <div>
                        <p className="text-xs font-bold text-rose-950">
                          Unable to determine DSD format.
                        </p>
                        <p className="text-[11px] text-rose-700 mt-0.5">
                          Please select NH / ND / AK manually below.
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setManualOverride(true)}
                      className="text-xs font-semibold text-rose-800 bg-white hover:bg-rose-100/50 border border-rose-300 px-3 py-1.5 rounded-lg shadow-sm transition-all"
                    >
                      Select Manually
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Manual Override Active Notice */}
            {manualOverride && file && (
              <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between">
                <p className="text-xs text-amber-800 font-medium">
                  Manual override active: <strong>{DSD_PROFILES.find((p) => p.id === dsdProfile)?.displayLabel || dsdProfile}</strong>
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setManualOverride(false);
                    if (detectedInfo && detectedInfo.detected_format !== "UNKNOWN") {
                      setDsdProfile(detectedInfo.detected_format);
                    } else {
                      setDsdProfile("AUTO");
                    }
                  }}
                  className="text-xs font-semibold text-amber-900 underline hover:text-amber-700"
                >
                  Reset to Auto Detect
                </button>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {DSD_PROFILES.map((profile) => {
                const isSelected = (!manualOverride && profile.id === "AUTO") || (manualOverride && dsdProfile === profile.id);
                return (
                  <label
                    key={profile.id}
                    className={`relative flex flex-col p-3 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? "border-brand-500 bg-brand-50/60 ring-2 ring-brand-500/20 shadow-sm"
                        : "border-slate-200 hover:border-slate-300 hover:bg-slate-50 bg-white"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 mb-1">
                      <input
                        type="radio"
                        name="dsd-profile"
                        value={profile.id}
                        checked={isSelected}
                        onChange={() => handleProfileSelect(profile.id)}
                        className="h-4 w-4 text-brand-600 border-slate-300 focus:ring-brand-500"
                      />
                      <span className={`text-xs font-bold ${isSelected ? "text-brand-900" : "text-slate-800"}`}>
                        {profile.label}
                      </span>
                    </div>
                    <span className="text-[11px] text-slate-500 pl-6 leading-snug">
                      {profile.description}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Upload Dropzone */}
          <div
            className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-colors ${
              file ? "border-brand-300 bg-brand-50" : "border-slate-300 bg-slate-50 hover:bg-slate-100"
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
                <div className="p-4 bg-white rounded-full shadow-sm mb-4 border border-slate-100">
                  <UploadCloud className="h-10 w-10 text-brand-500" />
                </div>
                <p className="text-base font-semibold text-slate-900">
                  Upload Cognos Report Definition
                </p>
                <p className="text-sm text-slate-500 mt-1 mb-6 text-center max-w-sm">
                  Supports NH, ND and AK Cognos DSD formats.
                </p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50 transition-all active:scale-95"
                >
                  Browse Files
                </button>
              </>
            ) : (
              <>
                <div className="p-4 bg-white rounded-full shadow-sm mb-4 border border-brand-100">
                  <FileText className="h-10 w-10 text-brand-600" />
                </div>
                <p className="text-base font-bold text-slate-900">{file.name}</p>
                <p className="text-sm text-slate-500 mt-1 mb-6 font-medium">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
                <div className="flex gap-4">
                  <button
                    onClick={() => setFile(null)}
                    className="rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50 transition-all active:scale-95"
                  >
                    Change File
                  </button>
                  <button
                    onClick={handleUpload}
                    disabled={isProcessing}
                    className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-bold text-white shadow-md hover:bg-brand-500 disabled:opacity-70 transition-all active:scale-95"
                  >
                    {isProcessing ? (
                      <>
                        <Loader2 className="h-5 w-5 animate-spin" />
                        Analyzing & Generating...
                      </>
                    ) : (
                      "Generate Intelligence"
                    )}
                  </button>
                </div>
              </>
            )}
          </div>

          {error && (
            <div className="mt-6 flex items-start gap-3 rounded-xl bg-red-50 p-4 text-sm text-red-800 border border-red-100 shadow-sm">
              <AlertTriangle className="h-5 w-5 shrink-0 text-red-600" />
              <div className="font-medium">{error}</div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Dashboard View ─────────────────────────────────────────────────────────
  return (
    <div className="flex min-h-[calc(100vh-113px)] w-full">
      {/* Left Sidebar Navigation */}
      <div 
        className={`${
          isSidebarCollapsed ? "w-[68px]" : "w-[240px]"
        } flex-shrink-0 bg-slate-900 flex flex-col shadow-2xl z-20 transition-all duration-200 ease-in-out`}
      >
        {/* Header & Toggle */}
        <div className={`p-4 border-b border-slate-800 flex items-center ${isSidebarCollapsed ? "justify-center flex-col gap-2" : "justify-between"}`}>
          {!isSidebarCollapsed && (
            <div className="min-w-0 pr-2">
              <h2 className="text-white font-bold text-base tracking-tight truncate">DSD Intelligence</h2>
              <p className="text-slate-400 text-xs mt-0.5 font-mono truncate">{result.report_id}</p>
            </div>
          )}
          <button
            type="button"
            onClick={toggleSidebar}
            aria-label={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors shrink-0 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {isSidebarCollapsed ? (
              <ChevronRight className="h-5 w-5" />
            ) : (
              <ChevronLeft className="h-5 w-5" />
            )}
          </button>
        </div>
        
        {/* Navigation Items */}
        <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-1.5">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                title={tab.label}
                aria-label={tab.label}
                className={`w-full flex items-center ${
                  isSidebarCollapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5"
                } rounded-lg text-sm font-medium transition-all group relative ${
                  isActive 
                    ? "bg-brand-600 text-white shadow-md shadow-brand-900/20" 
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icon className={`h-5 w-5 shrink-0 ${isActive ? "text-white" : "text-slate-400 group-hover:text-slate-200"}`} />
                {!isSidebarCollapsed && <span className="truncate">{tab.label}</span>}
              </button>
            );
          })}
        </nav>
        
        {/* Footer Actions */}
        <div className="p-3 border-t border-slate-800 space-y-2">
          <button
            type="button"
            onClick={handleDownload}
            disabled={isDownloading}
            title="Export to Excel"
            aria-label="Export to Excel"
            className={`w-full flex items-center justify-center ${
              isSidebarCollapsed ? "px-0 py-2.5" : "gap-2 px-3 py-2"
            } rounded-lg bg-green-600 text-sm font-bold text-white shadow hover:bg-green-500 disabled:opacity-70 transition-all`}
          >
            {isDownloading ? <Loader2 className="h-4 w-4 animate-spin shrink-0" /> : <Download className="h-4 w-4 shrink-0" />}
            {!isSidebarCollapsed && <span>Export to Excel</span>}
          </button>
          
          <button
            type="button"
            onClick={() => {
              setResult(null);
              setFile(null);
            }}
            title="New Analysis"
            aria-label="New Analysis"
            className={`w-full flex items-center justify-center ${
              isSidebarCollapsed ? "px-0 py-2.5" : "gap-2 px-3 py-2"
            } rounded-lg bg-slate-800 text-sm font-medium text-slate-300 hover:bg-slate-700 hover:text-white transition-all`}
          >
            <PlusCircle className="h-4 w-4 shrink-0" />
            {!isSidebarCollapsed && <span>New Analysis</span>}
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 min-w-0 overflow-hidden bg-slate-50 flex flex-col">
        <main className="flex-1 overflow-auto p-6 lg:p-8">
          <div className="h-full">
            {renderActiveTab()}
          </div>
        </main>
      </div>
    </div>
  );
}
