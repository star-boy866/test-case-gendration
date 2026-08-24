import React from "react";
import { CheckCircle2, Shield, FileCheck, Layers, GitMerge } from "lucide-react";

function KpiCard({ title, value, subtitle, icon: Icon, colorClass }) {
  return (
    <div className={`p-6 rounded-xl border bg-white shadow-sm flex flex-col justify-between ${colorClass}`}>
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">{title}</h3>
        <div className="p-2 rounded-lg bg-white/60 shadow-sm backdrop-blur">
          <Icon className="h-5 w-5 opacity-80" />
        </div>
      </div>
      <div>
        <div className="text-3xl font-bold text-slate-900">{value}</div>
        <div className="text-sm font-medium opacity-80 mt-1">{subtitle}</div>
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
    <div className="space-y-6">
      {/* Overview Header */}
      <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm flex items-start justify-between relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-brand-50 rounded-full blur-3xl opacity-60 -mr-16 -mt-16 pointer-events-none"></div>
        <div className="relative z-10">
          <div className="flex items-center gap-2 text-green-700 font-semibold mb-2 bg-green-50 px-3 py-1 rounded-full w-fit border border-green-200">
            <CheckCircle2 className="h-4 w-4" />
            <span className="text-xs tracking-wide uppercase">Pipeline Completed</span>
          </div>
          <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight mt-3">
            {result.report_id || "Report ID Not Found"}
          </h2>
          <p className="text-lg text-slate-600 font-medium mt-1">
            {result.report_definition?.metadata?.report_title || "Unknown Title"}
          </p>
          <div className="flex items-center gap-4 mt-6 text-sm text-slate-500 font-medium">
            <span className="flex items-center gap-1.5"><Shield className="h-4 w-4" /> Enterprise QA Validated</span>
            <span>&bull;</span>
            <span>Generation Time: {(summary.execution_time_seconds || 0).toFixed(1)}s</span>
          </div>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard 
          title="Total Requirements" 
          value={result.requirement_count ?? 0}
          subtitle="Extracted from DSD"
          icon={FileCheck}
          colorClass="border-blue-100 bg-gradient-to-br from-blue-50/50 to-white text-blue-800"
        />
        <KpiCard 
          title="Execution Scenarios" 
          value={result.test_case_count ?? 0}
          subtitle="Generated Developer UTs"
          icon={Layers}
          colorClass="border-indigo-100 bg-gradient-to-br from-indigo-50/50 to-white text-indigo-800"
        />
        <KpiCard 
          title="Methodology Coverage" 
          value={`${Math.round(coverage.methodology_coverage_percentage || 0)}%`}
          subtitle={`${methodologiesGenerated} patterns applied`}
          icon={GitMerge}
          colorClass="border-emerald-100 bg-gradient-to-br from-emerald-50/50 to-white text-emerald-800"
        />
        <KpiCard 
          title="Requirement Coverage" 
          value={`${Math.round(coverage.overall_coverage_percentage || 0)}%`}
          subtitle={`${coverage.requirements_covered || 0} mapped to tests`}
          icon={CheckCircle2}
          colorClass="border-amber-100 bg-gradient-to-br from-amber-50/50 to-white text-amber-800"
        />
      </div>

      {/* Detailed Coverage Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
           <h3 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
             <Layers className="h-5 w-5 text-indigo-500" />
             Test Scenario Distribution
           </h3>
           <div className="space-y-4">
             <div className="flex justify-between items-center text-sm">
               <span className="text-slate-600 font-medium">Header & Metadata</span>
               <span className="font-bold text-slate-900 bg-slate-100 px-3 py-1 rounded-full">{summary.metadata_tests + summary.header_tests || 0}</span>
             </div>
             <div className="flex justify-between items-center text-sm">
               <span className="text-slate-600 font-medium">Selection & Parameters</span>
               <span className="font-bold text-slate-900 bg-slate-100 px-3 py-1 rounded-full">{summary.selection_tests + summary.parameter_tests || 0}</span>
             </div>
             <div className="flex justify-between items-center text-sm">
               <span className="text-slate-600 font-medium">Column Data & Logic</span>
               <span className="font-bold text-slate-900 bg-slate-100 px-3 py-1 rounded-full">{summary.column_tests + summary.logic_tests + summary.report_label_tests || 0}</span>
             </div>
             <div className="flex justify-between items-center text-sm">
               <span className="text-slate-600 font-medium">Layout & Formatting</span>
               <span className="font-bold text-slate-900 bg-slate-100 px-3 py-1 rounded-full">{summary.layout_tests + summary.format_tests + summary.date_format_tests || 0}</span>
             </div>
           </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
           <h3 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
             <FileCheck className="h-5 w-5 text-blue-500" />
             Requirement Analysis
           </h3>
           <div className="space-y-4">
             <div className="flex justify-between items-center text-sm">
               <span className="text-slate-600 font-medium text-green-700">Covered</span>
               <span className="font-bold text-slate-900 bg-green-50 px-3 py-1 rounded-full">{coverage.requirements_covered || 0}</span>
             </div>
             <div className="flex justify-between items-center text-sm">
               <span className="text-slate-600 font-medium text-amber-700">Unmapped / Ambiguous</span>
               <span className="font-bold text-slate-900 bg-amber-50 px-3 py-1 rounded-full">{coverage.requirements_unmapped + coverage.requirements_ambiguous || 0}</span>
             </div>
             <div className="flex justify-between items-center text-sm">
               <span className="text-slate-600 font-medium text-slate-500">Duplicates (Ignored)</span>
               <span className="font-bold text-slate-900 bg-slate-100 px-3 py-1 rounded-full">{coverage.requirements_duplicate || 0}</span>
             </div>
           </div>
        </div>
      </div>
    </div>
  );
}
