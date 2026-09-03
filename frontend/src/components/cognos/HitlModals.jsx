import React, { useState, useEffect } from "react";
import {
  X, AlertTriangle, CheckCircle2, Sparkles, Edit3,
  Clock, History, Plus, FileText, Lock, Unlock,
  Trash2, ArrowRight, Shield, Check, Info, Ban
} from "lucide-react";

// ─── 1. Flag Issue Dialog ─────────────────────────────────────────────────────

const ISSUE_TYPES = [
  "Incorrect test step",
  "Incorrect expected result",
  "Incorrect DSD interpretation",
  "Incorrect SQL",
  "Incorrect source mapping",
  "Incorrect execution method",
  "Missing scenario",
  "Duplicate scenario",
  "Other"
];

export function FlagIssueModal({ isOpen, onClose, scenario, onSubmit, isLoading }) {
  const [issueType, setIssueType] = useState("Incorrect execution method");
  const [comment, setComment] = useState("");

  useEffect(() => {
    if (isOpen) {
      setIssueType(scenario?.issue_type || "Incorrect execution method");
      setComment(scenario?.issue_comment || "");
    }
  }, [isOpen, scenario]);

  if (!isOpen || !scenario) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      issue_type: issueType,
      issue_comment: comment.trim(),
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
              <AlertTriangle className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Flag Scenario Issue</h3>
              <p className="text-xs text-slate-500 font-mono">{scenario.test_case_id}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block">
              Issue Type <span className="text-red-500">*</span>
            </label>
            <select
              value={issueType}
              onChange={(e) => setIssueType(e.target.value)}
              className="w-full h-9 px-3 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 shadow-2xs"
            >
              {ISSUE_TYPES.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block">
              Explanation & Findings <span className="text-red-500">*</span>
            </label>
            <textarea
              rows={4}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="e.g., Scheduled report execution is performed through IWA/UC4, not directly through Cognos..."
              className="w-full p-3 bg-white border border-slate-200 rounded-lg text-xs font-normal text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 shadow-2xs leading-relaxed"
              required
            />
            <p className="text-[11px] text-slate-500">
              Submitting moves this scenario to <span className="font-semibold text-amber-700">Needs Review</span> status.
            </p>
          </div>

          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-3.5 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || !comment.trim()}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-bold shadow-xs transition-colors"
            >
              {isLoading ? "Submitting..." : "Submit for Review"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── 2. AI Suggest Correction Modal ──────────────────────────────────────────

export function SuggestCorrectionModal({
  isOpen,
  onClose,
  scenario,
  suggestion,
  isLoading,
  onApply,
  onEditMyself,
}) {
  if (!isOpen || !scenario) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-2xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-gradient-to-r from-blue-50/70 to-indigo-50/70">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white shadow-xs">
              <Sparkles className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-sm font-bold text-slate-900">AI Suggested Correction</h3>
              <p className="text-xs text-slate-500 font-mono">{scenario.test_case_id}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4 max-h-[75vh] overflow-y-auto">
          {isLoading ? (
            <div className="py-12 text-center space-y-2">
              <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-blue-600 border-t-transparent" />
              <p className="text-xs text-slate-500 font-medium">Analyzing scenario against DSD rules...</p>
            </div>
          ) : suggestion ? (
            <div className="space-y-4">
              {/* Reason Banner */}
              <div className="p-3.5 bg-blue-50/80 border border-blue-200 rounded-xl space-y-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-blue-800 flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5" /> Reasoning
                </span>
                <p className="text-xs text-blue-950 leading-relaxed">
                  {suggestion.reason}
                </p>
              </div>

              {/* Comparison Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* Current */}
                <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block">
                    Current Specification
                  </span>
                  <div className="space-y-1 text-xs">
                    {suggestion.current?.execution_tool && (
                      <p className="text-slate-600">
                        <strong className="text-slate-800">Tool:</strong> {suggestion.current.execution_tool}
                      </p>
                    )}
                    {suggestion.current?.report_id && (
                      <p className="text-slate-600">
                        <strong className="text-slate-800">Report ID:</strong> {suggestion.current.report_id}
                      </p>
                    )}
                    <div>
                      <strong className="text-slate-800 block mb-1">Steps:</strong>
                      <pre className="text-[11px] font-mono whitespace-pre-wrap bg-white p-2.5 rounded border border-slate-200 text-slate-700">
                        {suggestion.current?.test_steps || "No steps"}
                      </pre>
                    </div>
                  </div>
                </div>

                {/* Suggested */}
                <div className="p-3.5 bg-emerald-50/50 border border-emerald-200 rounded-xl space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700 flex items-center gap-1">
                    <Check className="h-3 w-3" /> Proposed Correction
                  </span>
                  <div className="space-y-1 text-xs">
                    {suggestion.suggested?.execution_tool && (
                      <p className="text-emerald-950">
                        <strong className="text-emerald-900">Tool:</strong> {suggestion.suggested.execution_tool}
                      </p>
                    )}
                    {suggestion.suggested?.report_id && (
                      <p className="text-emerald-950">
                        <strong className="text-emerald-900">Report ID:</strong> {suggestion.suggested.report_id}
                      </p>
                    )}
                    <div>
                      <strong className="text-emerald-900 block mb-1">Steps:</strong>
                      <pre className="text-[11px] font-mono whitespace-pre-wrap bg-white p-2.5 rounded border border-emerald-200 text-emerald-950 font-medium">
                        {suggestion.suggested?.test_steps}
                      </pre>
                    </div>
                  </div>
                </div>
              </div>

              {/* Note */}
              <p className="text-[11px] text-slate-500 italic">
                Note: AI suggestions are recommendations only. Scenarios are never modified without explicit human approval.
              </p>
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-slate-500">
              No correction suggestions generated.
            </div>
          )}

          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
            >
              Dismiss
            </button>
            <button
              type="button"
              onClick={() => {
                onClose();
                onEditMyself(suggestion?.suggested);
              }}
              className="px-3.5 py-1.5 rounded-lg bg-white border border-slate-300 text-xs font-semibold text-slate-800 hover:bg-slate-50 transition-colors"
            >
              Edit Myself
            </button>
            <button
              type="button"
              disabled={!suggestion || isLoading}
              onClick={() => onApply(suggestion?.suggested)}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-bold shadow-xs transition-colors"
            >
              <Check className="h-3.5 w-3.5" /> Apply Suggestion
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── 3. Manual Scenario Editor Modal ──────────────────────────────────────────

export function ManualScenarioEditorModal({
  isOpen,
  onClose,
  scenario,
  onSaveDraft,
  onApproveDirect,
  isLoading,
  initialValues,
}) {
  const [formData, setFormData] = useState({
    test_case_title: "",
    objective: "",
    execution_method: "Scheduled",
    execution_tool: "IWA",
    report_id: "",
    test_steps: [],
    expected_result: "",
    review_comments: "",
  });

  useEffect(() => {
    if (isOpen && scenario) {
      const rawSteps = initialValues?.test_steps || scenario.test_steps || "";
      const stepArray = Array.isArray(rawSteps)
        ? rawSteps
        : String(rawSteps).split("\n").map(s => s.trim()).filter(Boolean);

      setFormData({
        test_case_title: initialValues?.test_case_title || scenario.test_case_title || "",
        objective: initialValues?.objective || scenario.objective || "",
        execution_method: initialValues?.execution_method || scenario.execution_method || "Scheduled",
        execution_tool: initialValues?.execution_tool || scenario.execution_tool || "IWA",
        report_id: initialValues?.report_id || scenario.report_id || "",
        test_steps: stepArray.length > 0 ? stepArray : ["1. Execute report in designated environment."],
        expected_result: initialValues?.expected_result || scenario.expected_result || "",
        review_comments: scenario.review_comments || "",
      });
    }
  }, [isOpen, scenario, initialValues]);

  if (!isOpen || !scenario) return null;

  const handleStepChange = (idx, value) => {
    const updated = [...formData.test_steps];
    updated[idx] = value;
    setFormData({ ...formData, test_steps: updated });
  };

  const handleAddStep = () => {
    const nextNum = formData.test_steps.length + 1;
    setFormData({
      ...formData,
      test_steps: [...formData.test_steps, `${nextNum}. Verify report output`],
    });
  };

  const handleRemoveStep = (idx) => {
    if (formData.test_steps.length <= 1) return;
    const updated = formData.test_steps.filter((_, i) => i !== idx);
    setFormData({ ...formData, test_steps: updated });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-3xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
              <Edit3 className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Edit Scenario Specification</h3>
              <p className="text-xs text-slate-500 font-mono">{scenario.test_case_id} • v{scenario.version || 1}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Scrollable Form Body */}
        <div className="p-5 space-y-4 overflow-y-auto flex-1">
          {/* Scenario Name */}
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700 block">
              Scenario Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.test_case_title}
              onChange={(e) => setFormData({ ...formData, test_case_title: e.target.value })}
              className="w-full h-9 px-3 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs"
              required
            />
          </div>

          {/* Objective */}
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700 block">
              Scenario Objective <span className="text-red-500">*</span>
            </label>
            <textarea
              rows={2}
              value={formData.objective}
              onChange={(e) => setFormData({ ...formData, objective: e.target.value })}
              className="w-full p-2.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs leading-relaxed"
              required
            />
          </div>

          {/* Execution Controls Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700 block">
                Execution Method
              </label>
              <select
                value={formData.execution_method}
                onChange={(e) => setFormData({ ...formData, execution_method: e.target.value })}
                className="w-full h-9 px-2.5 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="Scheduled">Scheduled</option>
                <option value="On Request">On Request</option>
                <option value="Batch">Batch</option>
                <option value="Other">Other</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700 block">
                Execution Tool
              </label>
              <select
                value={formData.execution_tool}
                onChange={(e) => setFormData({ ...formData, execution_tool: e.target.value })}
                className="w-full h-9 px-2.5 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="IWA">IWA (NH Scheduler)</option>
                <option value="UC4">UC4 (ND Scheduler)</option>
                <option value="Cognos Portal">Cognos Portal</option>
                <option value="Info Analysis">Application UI (Info Analysis)</option>
                <option value="SQL Client">SQL Client</option>
                <option value="Other">Other</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700 block">
                Report ID
              </label>
              <input
                type="text"
                value={formData.report_id}
                onChange={(e) => setFormData({ ...formData, report_id: e.target.value })}
                className="w-full h-9 px-3 bg-white border border-slate-200 rounded-lg text-xs font-mono text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
          </div>

          {/* Test Steps */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-700">
                Test Steps ({formData.test_steps.length}) <span className="text-red-500">*</span>
              </label>
              <button
                type="button"
                onClick={handleAddStep}
                className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700"
              >
                <Plus className="h-3.5 w-3.5" /> Add Step
              </button>
            </div>
            <div className="space-y-2">
              {formData.test_steps.map((step, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[11px] font-bold text-slate-600 font-mono">
                    {idx + 1}
                  </span>
                  <input
                    type="text"
                    value={step}
                    onChange={(e) => handleStepChange(idx, e.target.value)}
                    className="flex-1 h-8 px-3 bg-white border border-slate-200 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  {formData.test_steps.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveStep(idx)}
                      title="Remove step"
                      className="text-slate-400 hover:text-rose-600 p-1.5 rounded transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Expected Verification Result */}
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700 block">
              Expected Verification Result <span className="text-red-500">*</span>
            </label>
            <textarea
              rows={2}
              value={formData.expected_result}
              onChange={(e) => setFormData({ ...formData, expected_result: e.target.value })}
              className="w-full p-2.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs leading-relaxed"
              required
            />
          </div>

          {/* Execution Comments */}
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700 block">
              Execution / Review Comments
            </label>
            <textarea
              rows={2}
              value={formData.review_comments}
              onChange={(e) => setFormData({ ...formData, review_comments: e.target.value })}
              placeholder="Add observation or rationale for changes..."
              className="w-full p-2.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs leading-relaxed"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100 bg-slate-50/50 shrink-0">
          <span className="text-[11px] text-slate-500">
            Saving draft increments version and sets status to <strong className="text-sky-700">Corrected</strong>.
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-3.5 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isLoading || !formData.test_case_title.trim() || !formData.objective.trim()}
              onClick={() => onSaveDraft(formData)}
              className="px-4 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-700 disabled:opacity-50 text-white text-xs font-bold shadow-xs transition-colors"
            >
              {isLoading ? "Saving..." : "Save Draft"}
            </button>
            <button
              type="button"
              disabled={isLoading || !formData.test_case_title.trim() || !formData.objective.trim()}
              onClick={() => onApproveDirect(formData)}
              className="inline-flex items-center gap-1 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-bold shadow-xs transition-colors"
            >
              <Check className="h-3.5 w-3.5" /> Approve Scenario
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── 4. Version History Modal ─────────────────────────────────────────────────

export function VersionHistoryModal({ isOpen, onClose, scenario }) {
  if (!isOpen || !scenario) return null;

  const history = Array.isArray(scenario.edit_history) ? scenario.edit_history : [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-2xl overflow-hidden flex flex-col max-h-[85vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
              <History className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Scenario Version History</h3>
              <p className="text-xs text-slate-500 font-mono">{scenario.test_case_id} • Currently v{scenario.version || 1}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {history.length === 0 ? (
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-500 text-center">
              Version 1 (Initial AI Generation)
            </div>
          ) : (
            <div className="relative border-l-2 border-slate-200 ml-4 space-y-6">
              {history.map((h, idx) => {
                const isApproved = h.status === "APPROVED";
                const isNeedsReview = h.status === "NEEDS_REVIEW";
                const isCorrected = h.status === "CORRECTED";
                const badgeColor = isApproved
                  ? "bg-emerald-100 text-emerald-800 border-emerald-200"
                  : isNeedsReview
                  ? "bg-amber-100 text-amber-800 border-amber-200"
                  : isCorrected
                  ? "bg-sky-100 text-sky-800 border-sky-200"
                  : "bg-slate-100 text-slate-700 border-slate-200";

                return (
                  <div key={idx} className="relative pl-6">
                    <span className={`absolute -left-2.5 top-0.5 h-5 w-5 rounded-full border-2 border-white flex items-center justify-center text-[10px] font-bold ${
                      isApproved ? "bg-emerald-600 text-white" : "bg-slate-400 text-white"
                    }`}>
                      {h.version || idx + 1}
                    </span>

                    <div className="bg-slate-50/80 p-3.5 rounded-xl border border-slate-200/80 space-y-2">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-900">
                            Version {h.version || idx + 1}
                          </span>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${badgeColor}`}>
                            {h.action || h.status}
                          </span>
                        </div>
                        <span className="text-[11px] text-slate-500 font-medium">
                          {h.timestamp ? new Date(h.timestamp).toLocaleString() : "Initial"}
                        </span>
                      </div>

                      <p className="text-xs text-slate-700">
                        {h.summary || "Revision record"}
                      </p>

                      {h.author && (
                        <p className="text-[11px] text-slate-500">
                          By: <span className="font-semibold text-slate-700">{h.author}</span>
                        </p>
                      )}

                      {/* Diff details if available */}
                      {Array.isArray(h.diffs) && h.diffs.length > 0 && (
                        <div className="pt-2 border-t border-slate-200 space-y-1">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                            Field Changes:
                          </span>
                          <div className="space-y-1">
                            {h.diffs.map((d, dIdx) => (
                              <div key={dIdx} className="text-[11px] bg-white p-2 rounded border border-slate-200 font-mono">
                                <span className="font-bold text-slate-900">{d.field}: </span>
                                <span className="text-rose-600 line-through">{d.from || "(empty)"}</span>
                                <span className="text-slate-400 mx-1">→</span>
                                <span className="text-emerald-700 font-semibold">{d.to || "(empty)"}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="px-5 py-3 border-t border-slate-100 bg-slate-50/50 flex justify-end shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-900 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── 5. Add Missing Scenario Dialog ──────────────────────────────────────────

export function AddMissingScenarioModal({
  isOpen,
  onClose,
  onPropose,
  onAccept,
  onEditInModal,
  isLoading,
  proposedScenario,
}) {
  const [whatToTest, setWhatToTest] = useState("");
  const [dsdRef, setDsdRef] = useState("");

  if (!isOpen) return null;

  const handlePropose = (e) => {
    e.preventDefault();
    if (!whatToTest.trim()) return;
    onPropose({
      whatToTest: whatToTest.trim(),
      dsdReference: dsdRef.trim() || "DSD Specification",
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white">
              <Plus className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Add Missing Test Scenario</h3>
              <p className="text-xs text-slate-500">Propose a test scenario not captured in automated extraction</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4 overflow-y-auto flex-1">
          {!proposedScenario ? (
            <form onSubmit={handlePropose} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 block">
                  What should be tested? <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={whatToTest}
                  onChange={(e) => setWhatToTest(e.target.value)}
                  placeholder="e.g., Report retention configuration and 90-day archive purge"
                  className="w-full h-9 px-3 bg-white border border-slate-200 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 block">
                  DSD Reference
                </label>
                <input
                  type="text"
                  value={dsdRef}
                  onChange={(e) => setDsdRef(e.target.value)}
                  placeholder="e.g., Report Retention • Page 12"
                  className="w-full h-9 px-3 bg-white border border-slate-200 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs"
                />
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={isLoading || !whatToTest.trim()}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-bold shadow-xs transition-colors"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  {isLoading ? "Generating Proposal..." : "Generate Scenario"}
                </button>
              </div>
            </form>
          ) : (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="p-3.5 bg-blue-50 border border-blue-200 rounded-xl space-y-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-blue-800">
                  AI Proposed Missing Scenario
                </span>
                <p className="text-xs text-blue-950 font-semibold">
                  {proposedScenario.test_case_title}
                </p>
              </div>

              <div className="space-y-2 text-xs">
                <div>
                  <strong className="text-slate-700 block">Objective:</strong>
                  <p className="text-slate-900 bg-slate-50 p-2.5 rounded border border-slate-200 mt-0.5">
                    {proposedScenario.objective}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <strong className="text-slate-700">Category:</strong> {proposedScenario.category}
                  </div>
                  <div>
                    <strong className="text-slate-700">Execution Tool:</strong> {proposedScenario.execution_tool}
                  </div>
                </div>

                <div>
                  <strong className="text-slate-700 block">Proposed Steps:</strong>
                  <pre className="text-[11px] font-mono whitespace-pre-wrap bg-slate-50 p-2.5 rounded border border-slate-200 text-slate-800 mt-0.5">
                    {proposedScenario.test_steps}
                  </pre>
                </div>

                <div>
                  <strong className="text-slate-700 block">Expected Result:</strong>
                  <p className="text-slate-900 bg-slate-50 p-2.5 rounded border border-slate-200 mt-0.5">
                    {proposedScenario.expected_result}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => onPropose(null)}
                  className="text-xs font-semibold text-slate-600 hover:text-slate-900"
                >
                  ← Back to prompt
                </button>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      onEditInModal(proposedScenario);
                    }}
                    className="px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    Edit Myself
                  </button>
                  <button
                    type="button"
                    onClick={() => onAccept(proposedScenario)}
                    className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-xs transition-colors"
                  >
                    <Check className="h-3.5 w-3.5" /> Accept & Add to Suite
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── 6. Duplicate Scenario Dialog ─────────────────────────────────────────────

export function DuplicateScenarioModal({
  isOpen,
  onClose,
  scenario,
  allScenarios,
  onConfirmDuplicate,
  isLoading,
}) {
  const [duplicateOfId, setDuplicateOfId] = useState("");
  const [reason, setReason] = useState("");

  const candidates = (allScenarios || []).filter(
    (s) => s.test_case_id !== scenario?.test_case_id
  );

  useEffect(() => {
    if (isOpen && candidates.length > 0) {
      setDuplicateOfId(candidates[0].test_case_id);
      setReason(`Consolidated into ${candidates[0].test_case_id}`);
    }
  }, [isOpen, scenario]);

  if (!isOpen || !scenario) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose-100 text-rose-700">
              <Ban className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Mark Scenario as Duplicate</h3>
              <p className="text-xs text-slate-500 font-mono">{scenario.test_case_id}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <p className="text-xs text-slate-600 leading-relaxed">
            Marking this scenario as a duplicate links it to the primary scenario and sets its review status to <strong className="text-rose-700">Rejected</strong> without destroying any data.
          </p>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block">
              Duplicate of Retained Scenario:
            </label>
            <select
              value={duplicateOfId}
              onChange={(e) => {
                setDuplicateOfId(e.target.value);
                setReason(`Consolidated into ${e.target.value}`);
              }}
              className="w-full h-9 px-3 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
            >
              {candidates.map((c) => (
                <option key={c.test_case_id} value={c.test_case_id}>
                  {c.test_case_id} — {c.test_case_title || c.category}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 block">
              Notes / Rationale:
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full h-9 px-3 bg-white border border-slate-200 rounded-lg text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
            />
          </div>

          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isLoading || !duplicateOfId}
              onClick={() => onConfirmDuplicate({ duplicateOfId, reason })}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white text-xs font-bold shadow-xs transition-colors"
            >
              {isLoading ? "Saving..." : "Confirm Duplicate"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
