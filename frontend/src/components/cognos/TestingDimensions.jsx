import React from "react";
import { GitMerge, CheckCircle, XCircle, AlertCircle } from "lucide-react";

function PatternCard({ pattern, status, reason, confidence, evidenceSource }) {
  const isApplicable = status === "APPLICABLE";
  
  const statusColor = isApplicable 
    ? "bg-green-50 text-green-700 border-green-200" 
    : "bg-slate-50 text-slate-500 border-slate-200";
    
  const StatusIcon = isApplicable ? CheckCircle : XCircle;

  return (
    <div className={`p-4 rounded-lg border shadow-sm ${isApplicable ? "bg-white border-green-200" : "bg-slate-50/50 border-slate-200 opacity-75"}`}>
      <div className="flex justify-between items-start mb-2">
        <h4 className={`font-semibold text-sm ${isApplicable ? "text-slate-900" : "text-slate-600"}`}>
          {pattern.replace(/_/g, " ")}
        </h4>
        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${statusColor}`}>
          <StatusIcon className="h-3 w-3" />
          {status}
        </span>
      </div>
      <p className="text-sm text-slate-600 mt-1">{reason}</p>
      
      {isApplicable && (
        <div className="mt-3 pt-3 border-t border-slate-100 flex justify-between items-center text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <span className="font-medium text-slate-700">Source:</span> {evidenceSource || "Derived Developer Methodology"}
          </span>
          <span className="flex items-center gap-1">
            <span className="font-medium text-slate-700">Confidence:</span> 
            <span className={confidence === "High" ? "text-green-600 font-semibold" : "text-amber-600 font-semibold"}>{confidence || "High"}</span>
          </span>
        </div>
      )}
    </div>
  );
}

export default function TestingDimensions({ result }) {
  const methodology = result?.methodology_applicability;
  
  if (!methodology) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-500">
        <AlertCircle className="h-10 w-10 mb-4 text-amber-400" />
        <h3 className="text-lg font-medium text-slate-900">No Methodology Data Available</h3>
        <p className="text-sm mt-1">The DSD pipeline did not return structural methodology analysis.</p>
      </div>
    );
  }

  const generated = methodology.generated || [];
  const notGenerated = methodology.not_generated || [];

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden flex flex-col h-full">
      <div className="border-b border-slate-200 bg-white px-6 py-5">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <GitMerge className="h-5 w-5 text-brand-600" />
          Methodology Applicability
        </h2>
        <p className="text-sm text-slate-500 font-normal mt-1">
          Golden methodology patterns automatically evaluated against DSD evidence.
        </p>
      </div>
      
      <div className="flex-1 overflow-auto bg-slate-50/50 p-6">
        <div className="space-y-8">
          
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
              Applicable Dimensions ({generated.length})
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {generated.map((item, idx) => (
                <PatternCard 
                  key={idx}
                  pattern={item.pattern}
                  status="APPLICABLE"
                  reason={item.applicable_reason}
                  confidence={item.confidence}
                  evidenceSource={item.evidence_source}
                />
              ))}
            </div>
            {generated.length === 0 && (
              <div className="p-4 rounded border border-dashed border-slate-300 text-center text-slate-500 text-sm">
                No methodologies were deemed applicable for this document.
              </div>
            )}
          </div>

          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-slate-400"></span>
              Not Applicable ({notGenerated.length})
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {notGenerated.map((item, idx) => (
                <PatternCard 
                  key={idx}
                  pattern={item.pattern}
                  status="NOT APPLICABLE"
                  reason={item.reason}
                  confidence={item.confidence}
                />
              ))}
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}
