import React from "react";
import { CheckCircle2, Shield, FileCheck, Layers, GitMerge } from "lucide-react";

function KpiCard({ title, value, subtitle, icon: Icon, colorClass }) {
  return (
    <div className={`p-3 sm:p-3.5 rounded-xl border bg-white shadow-2xs flex flex-col justify-between ${colorClass}`}>
      <div className="flex justify-between items-start mb-1.5">
        <h3 className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{title}</h3>
        <div className="p-1.5 rounded-lg bg-white/80 shadow-2xs backdrop-blur border border-slate-100">
          <Icon className="h-3.5 w-3.5 opacity-80" />
        </div>
      </div>
      <div>
        <div className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight font-mono">{value}</div>
        <div className="text-[11px] font-medium text-slate-500 mt-0.5 truncate">{subtitle}</div>
      </div>
    </div>
  );
}

export default function DSDIntelligenceSummary({ result }) {
  const summary = result?.summary || {};
  const coverage = result?.coverage || {};
  
  // Calculate methodology patterns generated
  const methodologiesGenerated = coverage.methodology_patterns_generated || result?.methodology_applicability?.generated?.length || 0;

  return (
    <div className="h-full w-full flex flex-col justify-between gap-3 sm:gap-3.5 max-w-7xl mx-auto min-h-0">
      {/* ── 1. Top Report Intelligence Header Card ────────────────────────── */}
      <div className="rounded-xl border border-slate-200 bg-white p-3.5 sm:p-4 shadow-2xs flex items-center justify-between relative overflow-hidden shrink-0">
        <div className="absolute top-0 right-0 w-48 h-48 bg-blue-50/60 rounded-full blur-2xl pointer-events-none" />
        
        <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between w-full gap-2">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200/80">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                Pipeline Completed
              </span>
              <span className="text-slate-300">•</span>
              <span className="text-xs font-semibold text-slate-500 flex items-center gap-1">
                <Shield className="h-3.5 w-3.5 text-blue-600" />
                Enterprise QA Validated
              </span>
            </div>
            
            <div className="flex items-baseline gap-2.5 pt-0.5">
              <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight font-mono">
                {result.report_id || "Report ID Not Found"}
              </h2>
              <span className="text-sm sm:text-base text-slate-600 font-medium truncate">
                {result.report_definition?.metadata?.report_title || "Invoice for County Jail Claims"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs font-medium text-slate-500 shrink-0 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200/80">
            <span>Gen Time:</span>
            <span className="font-mono font-bold text-slate-800">{(summary.execution_time_seconds || 0).toFixed(1)}s</span>
          </div>
        </div>
      </div>

      {/* ── 2. KPI 4-Card Row ────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3 shrink-0">
        <KpiCard 
          title="Total Requirements" 
          value={result.requirement_count ?? 0}
          subtitle="Extracted from DSD"
          icon={FileCheck}
          colorClass="border-blue-200/80 bg-gradient-to-br from-blue-50/60 to-white text-blue-800"
        />
        <KpiCard 
          title="Execution Scenarios" 
          value={result.test_case_count ?? 0}
          subtitle="Generated Developer UTs"
          icon={Layers}
          colorClass="border-indigo-200/80 bg-gradient-to-br from-indigo-50/60 to-white text-indigo-800"
        />
        <KpiCard 
          title="Methodology Coverage" 
          value={`${Math.round(coverage.methodology_coverage_percentage || 0)}%`}
          subtitle={`${methodologiesGenerated} patterns applied`}
          icon={GitMerge}
          colorClass="border-emerald-200/80 bg-gradient-to-br from-emerald-50/60 to-white text-emerald-800"
        />
        <KpiCard 
          title="Requirement Coverage" 
          value={`${Math.round(coverage.overall_coverage_percentage || 0)}%`}
          subtitle={`${coverage.requirements_covered || 0} mapped to tests`}
          icon={CheckCircle2}
          colorClass="border-amber-200/80 bg-gradient-to-br from-amber-50/60 to-white text-amber-800"
        />
      </div>

      {/* ── 3. Bottom Stats Split Panels ─────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2.5 sm:gap-3 flex-1 min-h-0">
        <div className="rounded-xl border border-slate-200 bg-white p-3.5 sm:p-4 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2 mb-1">
            <h3 className="text-xs sm:text-sm font-bold text-slate-900 flex items-center gap-1.5">
              <Layers className="h-4 w-4 text-indigo-600" />
              Test Scenario Distribution
            </h3>
            <span className="text-[11px] text-slate-400 font-medium">By Test Category</span>
          </div>
          
          <div className="space-y-1.5 flex-1 flex flex-col justify-around py-1 text-xs sm:text-sm">
            <div className="flex justify-between items-center py-1 px-2 rounded-lg hover:bg-slate-50 transition-colors">
              <span className="text-slate-600 font-medium">Header & Metadata</span>
              <span className="font-mono font-bold text-slate-900 bg-slate-100 px-2.5 py-0.5 rounded-md text-xs">{summary.metadata_tests + summary.header_tests || 0}</span>
            </div>
            <div className="flex justify-between items-center py-1 px-2 rounded-lg hover:bg-slate-50 transition-colors">
              <span className="text-slate-600 font-medium">Selection & Parameters</span>
              <span className="font-mono font-bold text-slate-900 bg-slate-100 px-2.5 py-0.5 rounded-md text-xs">{summary.selection_tests + summary.parameter_tests || 0}</span>
            </div>
            <div className="flex justify-between items-center py-1 px-2 rounded-lg hover:bg-slate-50 transition-colors">
              <span className="text-slate-600 font-medium">Column Data & Logic</span>
              <span className="font-mono font-bold text-slate-900 bg-slate-100 px-2.5 py-0.5 rounded-md text-xs">{summary.column_tests + summary.logic_tests + summary.report_label_tests || 0}</span>
            </div>
            <div className="flex justify-between items-center py-1 px-2 rounded-lg hover:bg-slate-50 transition-colors">
              <span className="text-slate-600 font-medium">Layout & Formatting</span>
              <span className="font-mono font-bold text-slate-900 bg-slate-100 px-2.5 py-0.5 rounded-md text-xs">{summary.layout_tests + summary.format_tests + summary.date_format_tests || 0}</span>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-3.5 sm:p-4 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2 mb-1">
            <h3 className="text-xs sm:text-sm font-bold text-slate-900 flex items-center gap-1.5">
              <FileCheck className="h-4 w-4 text-blue-600" />
              Requirement Analysis
            </h3>
            <span className="text-[11px] text-slate-400 font-medium">Traceability Health</span>
          </div>
          
          <div className="space-y-1.5 flex-1 flex flex-col justify-around py-1 text-xs sm:text-sm">
            <div className="flex justify-between items-center py-1 px-2 rounded-lg hover:bg-emerald-50/50 transition-colors">
              <span className="text-emerald-700 font-medium">Covered</span>
              <span className="font-mono font-bold text-emerald-900 bg-emerald-50 px-2.5 py-0.5 rounded-md text-xs border border-emerald-200/60">{coverage.requirements_covered || 0}</span>
            </div>
            <div className="flex justify-between items-center py-1 px-2 rounded-lg hover:bg-amber-50/50 transition-colors">
              <span className="text-amber-700 font-medium">Unmapped / Ambiguous</span>
              <span className="font-mono font-bold text-amber-900 bg-amber-50 px-2.5 py-0.5 rounded-md text-xs border border-amber-200/60">{coverage.requirements_unmapped + coverage.requirements_ambiguous || 0}</span>
            </div>
            <div className="flex justify-between items-center py-1 px-2 rounded-lg hover:bg-slate-50 transition-colors">
              <span className="text-slate-500 font-medium">Duplicates (Ignored)</span>
              <span className="font-mono font-bold text-slate-700 bg-slate-100 px-2.5 py-0.5 rounded-md text-xs">{coverage.requirements_duplicate || 0}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

