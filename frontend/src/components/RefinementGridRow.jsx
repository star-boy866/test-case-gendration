import { useState } from "react";
import { Trash2, Save, Sparkles, Pencil, User } from "lucide-react";
import { updateRefinementRow, deleteRefinementRow } from "../services/api";

const SOURCE_BADGE = {
  ai_generated: { label: "AI Generated", className: "bg-blue-100 text-blue-700", Icon: Sparkles },
  ai_generated_edited: { label: "AI + Edited", className: "bg-amber-100 text-amber-700", Icon: Pencil },
  manual: { label: "Manual", className: "bg-purple-100 text-purple-700", Icon: User },
};

const FIELDS = [
  { key: "test_scenario", label: "Test Scenario" },
  { key: "detailed_test_steps", label: "Detailed Test Steps" },
  { key: "expected_results", label: "Expected Results" },
  { key: "verification_sql", label: "Verification SQL", mono: true },
];

export default function RefinementGridRow({ row, sessionId, onChanged }) {
  const [local, setLocal] = useState(row);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const badge = SOURCE_BADGE[local.source] || SOURCE_BADGE.manual;
  const BadgeIcon = badge.Icon;

  const handleFieldChange = (key, value) => {
    setLocal((prev) => ({ ...prev, [key]: value }));
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateRefinementRow(
        sessionId,
        row.row_id,
        {
          test_scenario: local.test_scenario,
          detailed_test_steps: local.detailed_test_steps,
          expected_results: local.expected_results,
          verification_sql: local.verification_sql,
        }
      );
      setDirty(false);
      onChanged();
    } catch (err) {
      alert(err.response?.data?.detail || "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Remove scenario "${local.test_scenario}"?`)) return;
    try {
      await deleteRefinementRow(sessionId, row.row_id);
      onChanged();
    } catch (err) {
      alert(err.response?.data?.detail || "Delete failed.");
    }
  };

  return (
    <tr className="border-t border-slate-100 align-top">
      <td className="px-3 py-3 text-sm text-slate-500">{row.sl_no}</td>
      <td className="px-3 py-3">
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}>
          <BadgeIcon className="h-3 w-3" />
          {badge.label}
        </span>
        {row.requirement_text && (
          <p className="mt-1 max-w-[10rem] truncate text-[10px] text-slate-400" title={row.requirement_text}>
            from: {row.requirement_text}
          </p>
        )}
      </td>
      {FIELDS.map(({ key, label, mono }) => (
        <td key={key} className="px-3 py-3">
          <textarea
            value={local[key]}
            onChange={(e) => handleFieldChange(key, e.target.value)}
            aria-label={label}
            rows={key === "test_scenario" ? 2 : 3}
            className={`w-full min-w-[12rem] resize-y rounded-md border border-slate-200 px-2 py-1 text-xs focus:border-brand-500 focus:outline-none ${
              mono ? "font-mono" : ""
            }`}
          />
        </td>
      ))}
      <td className="px-3 py-3">
        <div className="flex flex-col gap-1">
          <button
            onClick={handleSave}
            disabled={!dirty || saving}
            className="flex items-center gap-1 rounded-md bg-brand-500 px-2 py-1 text-xs font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
          >
            <Save className="h-3 w-3" />
            {saving ? "Saving…" : dirty ? "Save" : "Saved"}
          </button>
          <button
            onClick={handleDelete}
            className="flex items-center gap-1 rounded-md border border-red-200 px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
          >
            <Trash2 className="h-3 w-3" />
            Remove
          </button>
        </div>
      </td>
    </tr>
  );
}
