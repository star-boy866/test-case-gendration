import React, { useMemo, useState } from "react";
import { ListChecks, AlertTriangle } from "lucide-react";

export default function CoverageMatrix({ result }) {
  const [filter, setFilter] = useState("ALL"); // ALL, COVERED, UNCOVERED, AMBIGUOUS

  const requirements = result?.requirements || [];
  const testCases = result?.test_cases || [];

  // Map requirements to tests
  const matrix = useMemo(() => {
    return requirements.map((req) => {
      // Find all test cases that link to this requirement
      const linkedTests = testCases.filter(tc => 
        tc.requirement_id === req.requirement_id || 
        (tc.requirement_ids && tc.requirement_ids.includes(req.requirement_id))
      );

      let status = "UNCOVERED";
      if (req.is_ambiguous) {
        status = "AMBIGUOUS";
      } else if (linkedTests.length > 0) {
        status = "COVERED";
      } else if (req.is_duplicate_of) {
        status = "DUPLICATE";
      }

      return {
        ...req,
        linkedTests,
        status,
      };
    }).filter(r => r.status !== "DUPLICATE"); // Hide pure duplicates from main matrix
  }, [requirements, testCases]);

  const filteredMatrix = useMemo(() => {
    if (filter === "ALL") return matrix;
    return matrix.filter(r => r.status === filter);
  }, [matrix, filter]);

  const coverageStats = useMemo(() => {
    const total = matrix.length;
    const covered = matrix.filter(r => r.status === "COVERED").length;
    const uncovered = matrix.filter(r => r.status === "UNCOVERED").length;
    const ambiguous = matrix.filter(r => r.status === "AMBIGUOUS").length;
    return { total, covered, uncovered, ambiguous };
  }, [matrix]);

  if (!requirements.length) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-500">
        <ListChecks className="h-10 w-10 mb-4 text-slate-300" />
        <h3 className="text-lg font-medium text-slate-900">No Coverage Data</h3>
        <p className="text-sm mt-1">Run the pipeline to generate a coverage matrix.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm flex flex-col h-full overflow-hidden">
      <div className="border-b border-slate-200 bg-white px-4 py-3 sm:px-5 sm:py-4">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-3 mb-4">
          <div>
            <h2 className="text-base sm:text-lg font-bold text-slate-900">Traceability Matrix</h2>
            <p className="text-xs sm:text-sm text-slate-500 font-normal mt-0.5">End-to-end mapping from DSD requirements to Developer UTs</p>
          </div>
          
          <div className="flex flex-wrap gap-1.5 sm:gap-2">
            <button 
              onClick={() => setFilter("ALL")}
              className={`px-2.5 py-1 sm:px-3 rounded-md text-xs font-medium transition-colors ${filter === "ALL" ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
            >
              All ({coverageStats.total})
            </button>
            <button 
              onClick={() => setFilter("COVERED")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${filter === "COVERED" ? "bg-green-600 text-white" : "bg-green-50 text-green-700 hover:bg-green-100"}`}
            >
              Covered ({coverageStats.covered})
            </button>
            <button 
              onClick={() => setFilter("UNCOVERED")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${filter === "UNCOVERED" ? "bg-red-600 text-white" : "bg-red-50 text-red-700 hover:bg-red-100"}`}
            >
              Uncovered ({coverageStats.uncovered})
            </button>
            <button 
              onClick={() => setFilter("AMBIGUOUS")}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${filter === "AMBIGUOUS" ? "bg-amber-500 text-white" : "bg-amber-50 text-amber-700 hover:bg-amber-100"}`}
            >
              Ambiguous ({coverageStats.ambiguous})
            </button>
          </div>
        </div>

        {/* Coverage Progress Bar */}
        <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden flex shadow-inner">
          <div 
            className="h-full bg-green-500" 
            style={{ width: `${(coverageStats.covered / (coverageStats.total || 1)) * 100}%` }}
          />
          <div 
            className="h-full bg-red-400" 
            style={{ width: `${(coverageStats.uncovered / (coverageStats.total || 1)) * 100}%` }}
          />
          <div 
            className="h-full bg-amber-400" 
            style={{ width: `${(coverageStats.ambiguous / (coverageStats.total || 1)) * 100}%` }}
          />
        </div>
      </div>
      
      <div className="flex-1 overflow-auto bg-slate-50/30">
        <table className="min-w-[650px] divide-y divide-slate-200 text-sm text-left relative">
          <thead className="bg-white sticky top-0 z-10 shadow-sm">
            <tr>
              <th className="px-4 py-3 font-semibold text-slate-600 w-32 bg-slate-50/95 backdrop-blur">Status</th>
              <th className="px-4 py-3 font-semibold text-slate-600 w-48 bg-slate-50/95 backdrop-blur">Requirement ID</th>
              <th className="px-4 py-3 font-semibold text-slate-600 bg-slate-50/95 backdrop-blur">Requirement Text</th>
              <th className="px-4 py-3 font-semibold text-slate-600 w-1/3 bg-slate-50/95 backdrop-blur">Linked Test Cases</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {filteredMatrix.map((row) => (
              <tr key={row.requirement_id || Math.random().toString()} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3 align-top">
                  {row.status === "COVERED" && (
                    <span className="inline-flex items-center rounded-md bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
                      Covered
                    </span>
                  )}
                  {row.status === "UNCOVERED" && (
                    <span className="inline-flex items-center rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-600/10">
                      Uncovered
                    </span>
                  )}
                  {row.status === "AMBIGUOUS" && (
                    <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-600/20">
                      <AlertTriangle className="h-3 w-3" /> Ambiguous
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 font-medium text-slate-900 align-top">{row.requirement_id}</td>
                <td className="px-4 py-3 text-slate-700 align-top">
                  <div className="line-clamp-2" title={row.requirement_text}>{row.requirement_text}</div>
                </td>
                <td className="px-4 py-3 align-top">
                  {row.linkedTests.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {row.linkedTests.map(tc => (
                        <span key={tc.test_case_id} className="inline-flex items-center rounded bg-indigo-50 px-1.5 py-0.5 text-xs font-medium text-indigo-700 border border-indigo-100">
                          {tc.test_case_id}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400 italic">No linked tests</span>
                  )}
                </td>
              </tr>
            ))}
            {filteredMatrix.length === 0 && (
              <tr>
                <td colSpan="4" className="px-4 py-12 text-center text-slate-500 bg-slate-50">
                  No records match the current filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
