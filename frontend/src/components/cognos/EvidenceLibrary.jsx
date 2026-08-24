import React, { useMemo, useState, useEffect } from "react";
import { Image as ImageIcon, Search, AlertTriangle } from "lucide-react";
import { api } from "../../services/api";
import InteractiveEvidenceViewer from "./InteractiveEvidenceViewer";

function EvidenceImage({ url, alt, className, onClick }) {
  const [objectUrl, setObjectUrl] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    if (!url) return;

    const apiPath = url.startsWith("/api") ? url.substring(4) : url;

    api.get(apiPath, { responseType: 'blob' })
      .then((res) => {
        if (!active) return;
        const blobUrl = URL.createObjectURL(res.data);
        setObjectUrl(blobUrl);
      })
      .catch((err) => {
        if (!active) return;
        console.error(`Failed to load evidence image (${url}):`, err.response?.status || err.message);
        setError(true);
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-slate-50 border border-slate-200 rounded-md text-slate-400">
        <AlertTriangle className="h-6 w-6 mb-2 text-amber-500" />
        <span className="text-sm font-medium">Evidence unavailable</span>
      </div>
    );
  }

  if (!objectUrl) {
    return (
      <div className="flex items-center justify-center h-32 bg-slate-50 rounded-md animate-pulse">
        <ImageIcon className="h-6 w-6 text-slate-300" />
      </div>
    );
  }

  return <img src={objectUrl} alt={alt} className={className} onClick={onClick} />;
}


export default function EvidenceLibrary({ result }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [zoomImage, setZoomImage] = useState(null);

  // Extract all unique evidence references from all test cases
  const allEvidence = useMemo(() => {
    const testCases = result?.test_cases || [];
    const evidenceMap = new Map();

    testCases.forEach(tc => {
      if (tc.evidence_references) {
        tc.evidence_references.forEach(ev => {
          if (ev.snapshot_url) {
            if (!evidenceMap.has(ev.snapshot_url)) {
              evidenceMap.set(ev.snapshot_url, {
                ...ev,
                linkedTests: [tc.test_case_id]
              });
            } else {
              const existing = evidenceMap.get(ev.snapshot_url);
              if (!existing.linkedTests.includes(tc.test_case_id)) {
                existing.linkedTests.push(tc.test_case_id);
              }
            }
          }
        });
      }
    });

    return Array.from(evidenceMap.values());
  }, [result]);

  const filteredEvidence = useMemo(() => {
    return allEvidence.filter(ev => {
      const textToSearch = `${ev.section || ''} ${ev.description || ''} ${ev.evidence_type || ''}`.toLowerCase();
      return textToSearch.includes(searchTerm.toLowerCase());
    });
  }, [allEvidence, searchTerm]);

  if (allEvidence.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-500">
        <ImageIcon className="h-10 w-10 mb-4 text-slate-300" />
        <h3 className="text-lg font-medium text-slate-900">No Evidence Found</h3>
        <p className="text-sm mt-1">No semantic proofs or snapshots were generated for this run.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm flex flex-col h-full overflow-hidden">
      <div className="border-b border-slate-200 bg-white px-5 py-4">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Evidence Library</h2>
            <p className="text-sm text-slate-500 font-normal mt-0.5">Centralized gallery of all DSD screenshots and semantic proofs</p>
          </div>
          <span className="inline-flex items-center rounded-md bg-purple-50 px-3 py-1 text-sm font-medium text-purple-700 border border-purple-200 shadow-sm">
            Total Unique Images: {allEvidence.length}
          </span>
        </div>
        
        <div className="relative max-w-md">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
            <Search className="h-4 w-4 text-slate-400" />
          </div>
          <input
            type="text"
            placeholder="Search by section, description, or type..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="block w-full rounded-md border-0 py-1.5 pl-9 pr-3 text-slate-900 ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-brand-600 sm:text-sm sm:leading-6"
          />
        </div>
      </div>
      
      <div className="flex-1 overflow-auto bg-slate-50/50 p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredEvidence.map((ev, idx) => (
            <div key={idx} className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden flex flex-col">
              <div className="p-2 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider truncate mr-2">
                  {(ev.evidence_type || "").replace(/_/g, " ")}
                </span>
                <span className="text-[10px] font-medium bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded">
                  {ev.section}
                </span>
              </div>
              <div className="p-2 flex-1 flex flex-col justify-center bg-white cursor-zoom-in" onClick={() => setZoomImage({ imageUrl: ev.snapshot_url, evidence: ev, title: ev.description })}>
                 <EvidenceImage
                    url={ev.snapshot_url}
                    alt={ev.description}
                    className="w-full h-auto max-h-48 object-contain rounded hover:opacity-90 transition-opacity"
                  />
              </div>
              <div className="p-3 border-t border-slate-100 bg-white">
                <p className="text-xs text-slate-600 line-clamp-2" title={ev.description}>{ev.description}</p>
                <div className="mt-2 pt-2 border-t border-slate-50 flex flex-wrap gap-1">
                  {ev.linkedTests.map(tcId => (
                    <span key={tcId} className="text-[10px] bg-indigo-50 text-indigo-700 px-1 rounded border border-indigo-100">
                      {tcId}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
          
          {filteredEvidence.length === 0 && (
            <div className="col-span-full py-12 text-center text-slate-500">
              No evidence matches your search.
            </div>
          )}
        </div>
      </div>

      {zoomImage && (
        <InteractiveEvidenceViewer
          isOpen={Boolean(zoomImage)}
          onClose={() => setZoomImage(null)}
          imageUrl={typeof zoomImage === 'object' ? zoomImage.imageUrl : zoomImage}
          evidence={typeof zoomImage === 'object' ? zoomImage.evidence : null}
          title={typeof zoomImage === 'object' ? zoomImage.title : null}
        />
      )}
    </div>
  );
}
