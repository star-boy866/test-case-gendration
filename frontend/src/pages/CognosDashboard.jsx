import { useState, useRef } from "react";
import { 
  UploadCloud, FileText, Loader2, AlertTriangle, LayoutDashboard, 
  List, Target, CheckSquare, Image as ImageIcon, Download, PlusCircle,
  ChevronLeft, ChevronRight
} from "lucide-react";
import { uploadCognosDocument, downloadCognosExport } from "../services/api";

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

export default function CognosDashboard() {
  const [file, setFile] = useState(null);
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
                  Must be a standard .docx format matching the NH MMIS DSD template.
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
