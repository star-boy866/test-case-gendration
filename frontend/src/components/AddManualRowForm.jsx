import { useState } from "react";
import { Plus, X } from "lucide-react";
import { addManualRow } from "../services/api";

const EMPTY = { test_scenario: "", detailed_test_steps: "", expected_results: "", verification_sql: "" };

export default function AddManualRowForm({ sessionId, onAdded }) {
  const [open, setOpen] = useState(false);
  const [fields, setFields] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      await addManualRow(sessionId, {
        testScenario: fields.test_scenario,
        detailedTestSteps: fields.detailed_test_steps,
        expectedResults: fields.expected_results,
        verificationSql: fields.verification_sql,
      });
      setFields(EMPTY);
      setOpen(false);
      onAdded();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not add scenario.");
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1 rounded-md border border-dashed border-slate-300 px-3 py-2 text-sm text-slate-600 hover:border-brand-500 hover:text-brand-600"
      >
        <Plus className="h-4 w-4" />
        Add a manual scenario
      </button>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">New manual scenario</p>
        <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-slate-600">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs">
          <span className="mb-1 block font-medium text-slate-600">Test Scenario</span>
          <textarea
            value={fields.test_scenario}
            onChange={(e) => setFields((f) => ({ ...f, test_scenario: e.target.value }))}
            rows={2}
            className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
        </label>
        <label className="text-xs">
          <span className="mb-1 block font-medium text-slate-600">Detailed Test Steps</span>
          <textarea
            value={fields.detailed_test_steps}
            onChange={(e) => setFields((f) => ({ ...f, detailed_test_steps: e.target.value }))}
            rows={2}
            className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
        </label>
        <label className="text-xs">
          <span className="mb-1 block font-medium text-slate-600">Expected Results</span>
          <textarea
            value={fields.expected_results}
            onChange={(e) => setFields((f) => ({ ...f, expected_results: e.target.value }))}
            rows={2}
            className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
        </label>
        <label className="text-xs">
          <span className="mb-1 block font-medium text-slate-600">Verification SQL</span>
          <textarea
            value={fields.verification_sql}
            onChange={(e) => setFields((f) => ({ ...f, verification_sql: e.target.value }))}
            rows={2}
            className="w-full rounded-md border border-slate-300 px-2 py-1 font-mono text-sm"
          />
        </label>
      </div>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={saving || Object.values(fields).some((v) => !v.trim())}
        className="mt-3 rounded-md bg-brand-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {saving ? "Adding…" : "Add scenario"}
      </button>
    </div>
  );
}
