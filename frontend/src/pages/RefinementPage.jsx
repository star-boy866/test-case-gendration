import { useEffect, useState, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import { runGeneration, getRefinementGrid, getJudgeEvaluation } from "../services/api";
import { useWorkflow } from "../context/WorkflowContext.jsx";
import RefinementGridRow from "../components/RefinementGridRow.jsx";
import AddManualRowForm from "../components/AddManualRowForm.jsx";

const COLUMNS = ["SL#", "Source", "Test Scenario", "Detailed Test Steps", "Expected Results", "Verification SQL", "Actions"];

export default function RefinementPage() {
  const { reportId, sessionId } = useWorkflow();
  const [requirement, setRequirement] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generationError, setGenerationError] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const [showDetails, setShowDetails] = useState(false);

  const [grid, setGrid] = useState([]);
  const [gridLoading, setGridLoading] = useState(false);
  const [gridError, setGridError] = useState(null);

  // Phase 10 — LLM-as-Judge is computed asynchronously in the backend
  // (FastAPI BackgroundTasks) and never gates anything above, so the UI
  // polls for it briefly after a generation call rather than waiting on it.
  const [judgeEvaluation, setJudgeEvaluation] = useState(null);
  const judgePollRef = useRef(null);

  const refreshGrid = useCallback(() => {
    if (!sessionId) return;
    setGridLoading(true);
    getRefinementGrid(sessionId)
      .then((res) => setGrid(res.data))
      .catch((err) => setGridError(err.response?.data?.detail || "Could not load the grid."))
      .finally(() => setGridLoading(false));
  }, [sessionId]);

  useEffect(() => {
    refreshGrid();
  }, [refreshGrid]);

  // Stop any in-flight poll if the session changes or the component unmounts.
  useEffect(() => {
    setJudgeEvaluation(null);
    return () => {
      if (judgePollRef.current) clearInterval(judgePollRef.current);
    };
  }, [sessionId]);

  const pollForJudgeEvaluation = useCallback((sid) => {
    if (judgePollRef.current) clearInterval(judgePollRef.current);
    let attempts = 0;
    const maxAttempts = 6; // ~30s total, generous for a local LLM call
    judgePollRef.current = setInterval(async () => {
      attempts += 1;
      try {
        const res = await getJudgeEvaluation(sid);
        if (res.data.available) {
          setJudgeEvaluation(res.data);
          clearInterval(judgePollRef.current);
        } else if (attempts >= maxAttempts) {
          // Give up quietly — this is a supplementary, best-effort layer,
          // not something the user should be blocked or alarmed by if it
          // never shows up (e.g. Ollama wasn't running for the background
          // task either).
          clearInterval(judgePollRef.current);
        }
      } catch {
        clearInterval(judgePollRef.current);
      }
    }, 5000);
  }, []);

  const handleGenerate = async () => {
    if (!requirement.trim()) return;
    setGenerating(true);
    setGenerationError(null);
    setLastResult(null);
    setJudgeEvaluation(null);
    try {
      const res = await runGeneration({ reportId, requirement });
      setLastResult(res.data);
      refreshGrid();
      // Fast-path/cache-hit responses never schedule a background judge
      // evaluation (see api/generation.py), so only poll when the full
      // pipeline actually ran.
      if (res.data.cache_status === "miss" || res.data.cache_status === "partial_hit") {
        pollForJudgeEvaluation(sessionId);
      }
    } catch (err) {
      setGenerationError(
        err.response?.data?.detail ||
          "Generation failed — is the backend running, and Ollama available for non-fast-path requests?"
      );
    } finally {
      setGenerating(false);
    }
  };

  if (!sessionId) {
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Step 3 — Interactive Refinement Grid</h2>
        <div className="flex items-start gap-2 rounded-md bg-amber-50 p-4 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            No confirmed session yet. Go back to{" "}
            <Link to="/gatekeeper" className="underline">
              Step 2 — Gatekeeper
            </Link>{" "}
            and confirm scope first.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Step 3 — Interactive Refinement Grid</h2>
        <p className="text-sm text-slate-500">
          Generate scenarios from a requirement, then edit, remove, or add to
          them directly. Every human edit is logged for audit — nothing here
          is silently overwritten.
        </p>
      </div>

      {/* Generation input */}
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <label className="mb-1 block text-sm font-medium text-slate-700">
          Natural language requirement
        </label>
        <div className="flex gap-2">
          <textarea
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
            rows={2}
            placeholder="e.g. Validate Swipe Card Issuance tracking when indicator equals 'N'"
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <button
            onClick={handleGenerate}
            disabled={generating || !requirement.trim()}
            className="flex shrink-0 items-center gap-1 self-start rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <Sparkles className="h-4 w-4" />
            {generating ? "Generating…" : "Generate"}
          </button>
        </div>

        {generationError && (
          <div className="mt-3 flex items-start gap-2 rounded-md bg-red-50 p-3 text-sm text-red-700">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{generationError}</span>
          </div>
        )}

        {lastResult && (
          <div className="mt-3 rounded-md bg-slate-50 p-3 text-xs text-slate-600">
            <button
              onClick={() => setShowDetails((s) => !s)}
              className="flex items-center gap-1 font-medium text-slate-700"
            >
              {showDetails ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              cache: {lastResult.cache_status} · quality score: {lastResult.quality_score.toFixed(2)}
              {lastResult.critic_report && ` · critic passed: ${lastResult.critic_report.passed}`}
            </button>
            {showDetails && (
              <div className="mt-2 space-y-2">
                {lastResult.cache_explanation && <p>{lastResult.cache_explanation}</p>}
                {lastResult.pipeline_warnings?.length > 0 && (
                  <div>
                    <p className="font-medium text-slate-700">Pipeline notes:</p>
                    <ul className="list-inside list-disc">
                      {lastResult.pipeline_warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {judgeEvaluation && (
          <div className="mt-3 rounded-md border border-indigo-100 bg-indigo-50 p-3 text-xs text-indigo-900">
            <div className="mb-1 flex items-center gap-1 font-medium">
              <Sparkles className="h-3.5 w-3.5" />
              Async AI quality review (supplementary — does not gate anything)
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="font-semibold">{judgeEvaluation.completeness.toFixed(2)}</div>
                <div className="text-indigo-500">Completeness</div>
              </div>
              <div>
                <div className="font-semibold">{judgeEvaluation.hallucination_prevention.toFixed(2)}</div>
                <div className="text-indigo-500">No hallucination</div>
              </div>
              <div>
                <div className="font-semibold">{judgeEvaluation.schema_adherence.toFixed(2)}</div>
                <div className="text-indigo-500">Schema adherence</div>
              </div>
            </div>
            {judgeEvaluation.rationale && (
              <p className="mt-2 text-indigo-700">{judgeEvaluation.rationale}</p>
            )}
            {judgeEvaluation.warnings?.length > 0 && (
              <ul className="mt-1 list-inside list-disc text-indigo-700">
                {judgeEvaluation.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Grid */}
      {gridError && (
        <div className="flex items-start gap-2 rounded-md bg-red-50 p-3 text-sm text-red-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{gridError}</span>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-100 text-slate-600">
            <tr>
              {COLUMNS.map((col) => (
                <th key={col} className="px-3 py-2 font-medium">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grid.length === 0 && !gridLoading && (
              <tr>
                <td className="px-4 py-6 text-slate-400" colSpan={COLUMNS.length}>
                  No scenarios yet — generate some above, or add one manually below.
                </td>
              </tr>
            )}
            {grid.map((row) => (
              <RefinementGridRow
                key={row.row_id}
                row={row}
                sessionId={sessionId}
                onChanged={refreshGrid}
              />
            ))}
          </tbody>
        </table>
      </div>

      <AddManualRowForm sessionId={sessionId} onAdded={refreshGrid} />
    </div>
  );
}
