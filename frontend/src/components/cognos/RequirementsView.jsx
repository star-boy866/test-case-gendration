import React, { useState, useMemo } from "react";
import { FileSearch, Search, Filter } from "lucide-react";

export default function RequirementsView({ result }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  
  const requirements = result?.requirements || [];
  
  const categories = useMemo(() => {
    const cats = new Set(requirements.map(r => r.category));
    return ["ALL", ...Array.from(cats).sort()];
  }, [requirements]);
  
  const filteredReqs = useMemo(() => {
    return requirements.filter(r => {
      const matchesSearch = (r.field || "").toLowerCase().includes(searchTerm.toLowerCase()) || 
                            (r.requirement_text || "").toLowerCase().includes(searchTerm.toLowerCase()) ||
                            (r.requirement_id || "").toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesCategory = categoryFilter === "ALL" || r.category === categoryFilter;
      
      return matchesSearch && matchesCategory;
    });
  }, [requirements, searchTerm, categoryFilter]);

  if (!requirements.length) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-500">
        <FileSearch className="h-10 w-10 mb-4 text-slate-300" />
        <h3 className="text-lg font-medium text-slate-900">No Requirements Extracted</h3>
        <p className="text-sm mt-1">The extraction pipeline did not return any requirements.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm flex flex-col h-full overflow-hidden">
      <div className="border-b border-slate-200 bg-white px-5 py-4">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Extracted Requirements</h2>
            <p className="text-sm text-slate-500 font-normal mt-0.5">Raw structural intent mapped from the DSD</p>
          </div>
          <span className="inline-flex items-center rounded-md bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700 border border-blue-200 shadow-sm">
            Total: {requirements.length}
          </span>
        </div>
        
        {/* Filters */}
        <div className="flex gap-4">
          <div className="relative flex-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <Search className="h-4 w-4 text-slate-400" />
            </div>
            <input
              type="text"
              placeholder="Search ID, field, or text..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="block w-full rounded-md border-0 py-1.5 pl-9 pr-3 text-slate-900 ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-brand-600 sm:text-sm sm:leading-6"
            />
          </div>
          <div className="relative">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <Filter className="h-4 w-4 text-slate-400" />
            </div>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="block w-full rounded-md border-0 py-1.5 pl-9 pr-8 text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-inset focus:ring-brand-600 sm:text-sm sm:leading-6"
            >
              {categories.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>
      </div>
      
      <div className="flex-1 overflow-auto bg-slate-50/30">
        <table className="min-w-full divide-y divide-slate-200 text-sm text-left">
          <thead className="bg-white sticky top-0 z-10 shadow-sm">
            <tr>
              <th className="px-4 py-3 font-semibold text-slate-600 w-32 bg-slate-50/95 backdrop-blur">Requirement ID</th>
              <th className="px-4 py-3 font-semibold text-slate-600 w-48 bg-slate-50/95 backdrop-blur">Category</th>
              <th className="px-4 py-3 font-semibold text-slate-600 w-48 bg-slate-50/95 backdrop-blur">Field / Element</th>
              <th className="px-4 py-3 font-semibold text-slate-600 bg-slate-50/95 backdrop-blur">Requirement Text</th>
              <th className="px-4 py-3 font-semibold text-slate-600 w-32 bg-slate-50/95 backdrop-blur">Source Trace</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {filteredReqs.map((req) => (
              <tr key={req.requirement_id || Math.random().toString()} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3 font-medium text-slate-900 align-top">{req.requirement_id}</td>
                <td className="px-4 py-3 align-top">
                  <span className="inline-flex items-center rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 border border-slate-200">
                    {req.category}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-indigo-700 align-top break-words">
                  {req.field || req.business_label || "-"}
                </td>
                <td className="px-4 py-3 text-slate-700 align-top">
                  <div className="whitespace-pre-wrap">{req.requirement_text}</div>
                  {req.processing_rule && (
                    <div className="mt-2 text-xs bg-amber-50 text-amber-900 border border-amber-100 p-2 rounded">
                      <span className="font-semibold block mb-0.5">Processing Logic:</span>
                      {req.processing_rule}
                    </div>
                  )}
                  {req.source_columns && req.source_columns.length > 0 && (
                    <div className="mt-2 text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded inline-block">
                      Source Cols: {req.source_columns.join(", ")}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-500 text-xs align-top">
                  {req.source_page ? `Page ${req.source_page}` : "Doc"}
                  <br/>
                  <span className="font-medium text-slate-600 truncate block max-w-xs">{req.source_section}</span>
                </td>
              </tr>
            ))}
            {filteredReqs.length === 0 && (
              <tr>
                <td colSpan="5" className="px-4 py-12 text-center text-slate-500 bg-slate-50">
                  No requirements match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
