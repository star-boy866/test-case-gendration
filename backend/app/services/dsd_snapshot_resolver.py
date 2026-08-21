"""
DSD Snapshot Resolver — PHASE 11.4

Produces a second evidence reference of type SOURCE_DSD_SNAPSHOT for each
test case. This reference points to the ACTUAL original uploaded DOCX document
and its section/page, rather than generating a synthetic image.

Design rules
────────────
• NEVER replaces the existing DSD_SEMANTIC_PROOF reference.
• Provides source_document_id and source_document_url for frontend retrieval.
• Returns None silently when no relevant DSD data exists — pipeline continues.
• Every section/page reference is resolved from the live DSD model's
  ProvenanceMixin.source_page field, which was extracted by the parser.

Methodology → DSD section mapping
───────────────────────────────────
LABEL_VALIDATION          → Report Layout  (layout.source_page / report_specification[0].source_page)
LAYOUT_VALIDATION         → Report Layout  (same)
SORT_VALIDATION           → Sorts          (sorts[0].source_page)
DATE_FORMAT_VALIDATION    → Report Specification  (report_specification[0].source_page)
DB_REPORT_DATA_VALIDATION → Report Specification / Report Body
CONTROL_BREAK_VALIDATION  → Control Breaks / Totals / Counts
DB_COUNT_VALIDATION       → Counts & Totals
REPORT_NAME_DESCRIPTION   → Report Definition
SCRIPT_OUTPUT_VALIDATION  → Report Output / Retention
NO_DATA_VALIDATION        → Selection Criteria
SCHEDULED_EXECUTION       → Report Generation
OUTPUT_DELIVERY           → Report Output
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List

from app.domain.cognos_test_case import EvidenceReference
from app.cognos.schema.nh_mmis_dsd_models import NhMmisDsd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal data carrier
# ---------------------------------------------------------------------------

class _SectionData:
    """Resolved DSD section content for snapshot rendering."""
    def __init__(
        self,
        section_name: str,
        source_page: Optional[int],
        headers: List[str],
        rows: List[List[str]],
        highlights: List[int],
        accent_color: tuple = (15, 80, 170),
    ):
        self.section_name = section_name
        self.source_page = source_page
        self.headers = headers
        self.rows = rows
        self.highlights = highlights
        self.accent_color = accent_color


# ---------------------------------------------------------------------------
# Public resolver
# ---------------------------------------------------------------------------

class DSDSnapshotResolver:
    """
    Resolves a SOURCE_DSD_SNAPSHOT evidence card for a given methodology
    pattern using the NhMmisDsd semantic model. It links to the actual DOCX.

    Usage
    -----
        resolver = DSDSnapshotResolver(output_dir=Path("jobs/xyz/evidence"))
        snapshot_ref = resolver.resolve(dsd, methodology="LABEL_VALIDATION",
                                        target_labels={"oplc term date"},
                                        test_case_id="PRV-INT-027-LBL-01")
        # Returns EvidenceReference or None
    """

    # Methodology patterns that get a SOURCE_DSD_SNAPSHOT
    SUPPORTED = {
        "LABEL_VALIDATION",
        "LAYOUT_VALIDATION",
        "SORT_VALIDATION",
        "DATE_FORMAT_VALIDATION",
        "DB_REPORT_DATA_VALIDATION",
        "CONTROL_BREAK_VALIDATION",
        "DB_COUNT_VALIDATION",
        "REPORT_NAME_DESCRIPTION_VALIDATION",
        "SCRIPT_OUTPUT_VALIDATION",
        "NO_DATA_VALIDATION",
        "SCHEDULED_EXECUTION_VALIDATION",
        "OUTPUT_DELIVERY_VALIDATION",
        "DUPLICATE_VALIDATION",
        "LOOKUP_VALIDATION",
    }

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(
        self,
        dsd: NhMmisDsd,
        methodology: str,
        target_labels: set[str] | None = None,
        source_column: str | None = None,
        test_case_id: str = "",
    ) -> Optional[EvidenceReference]:
        """
        Return a SOURCE_DSD_SNAPSHOT EvidenceReference or None.
        Never raises an exception.
        """
        try:
            if methodology not in self.SUPPORTED:
                return None

            section = self._extract_section(dsd, methodology, target_labels or set(), source_column or "")
            if section is None:
                return None
            if not section.rows:
                return None

            page_label = f"Page {section.source_page}" if section.source_page else "DSD"
            description = (
                f"Source DSD snapshot — {section.section_name}"
                + (f" (p. {section.source_page})" if section.source_page else "")
            )

            # In the future, doc_id could be resolved correctly from db/file-system context
            doc_name = dsd.report_definition.source_document if dsd.report_definition and dsd.report_definition.source_document else "DSD"
            # Providing a mock url for now, to be integrated with real endpoint if present
            doc_url = f"/api/documents/{doc_name}" if doc_name != "DSD" else ""

            return EvidenceReference(
                evidence_id=f"snapshot_{test_case_id}_{methodology[:6]}",
                evidence_type="SOURCE_DSD_SNAPSHOT",
                section=section.section_name,
                page_number=section.source_page,
                description=description,
                document_name=doc_name,
                source_document_id="",
                source_document_url=doc_url,
                snapshot_path="",  # Intentionally blank - we don't synthesize images anymore
                snapshot_url="",
                source_text=f"{section.section_name} source reference",
            )

        except Exception as exc:
            logger.warning(
                "DSDSnapshotResolver: failed for tc=%s method=%s: %s",
                test_case_id, methodology, exc,
            )
            return None

    # ------------------------------------------------------------------
    # Section extraction — per-methodology
    # ------------------------------------------------------------------

    def _extract_section(
        self,
        dsd: NhMmisDsd,
        methodology: str,
        target_labels: set[str],
        source_column: str,
    ) -> Optional[_SectionData]:

        m = methodology

        # ── Report Layout (Label & Layout validation) ──────────────────
        if m in ("LABEL_VALIDATION", "LAYOUT_VALIDATION"):
            rows: List[List[str]] = []
            highlights: List[int] = []
            page = None
            if dsd.report_specification:
                page = dsd.report_specification[0].source_page
            elif dsd.layout and dsd.layout.source_page:
                page = dsd.layout.source_page

            valid = [r for r in dsd.report_specification if r.business_label and r.business_label.strip()]
            for idx, row in enumerate(valid):
                rows.append([
                    row.business_label or "",
                    row.source_table or "",
                    row.source_column or "",
                    (row.processing_rules or "")[:60],
                ])
                label_lower = (row.business_label or "").strip().lower()
                if label_lower in target_labels or (source_column and source_column in label_lower):
                    highlights.append(idx)

            if not rows:
                return None
            return _SectionData(
                section_name="Report Layout",
                source_page=page,
                headers=["Business Label", "Source Table", "Source Column", "Processing Rules"],
                rows=rows,
                highlights=highlights,
                accent_color=(10, 70, 150),
            )

        # ── Sorts ──────────────────────────────────────────────────────
        if m == "SORT_VALIDATION":
            rows = []
            highlights = []
            page = dsd.sorts[0].source_page if dsd.sorts else None
            valid = [s for s in dsd.sorts if s.sort_by and s.sort_by.strip()]
            for idx, s in enumerate(valid):
                rows.append([s.sort_by, s.direction or ""])
                s_lower = (s.sort_by or "").strip().lower()
                if s_lower in target_labels or (source_column and source_column in s_lower):
                    highlights.append(idx)
            if not rows:
                return None
            return _SectionData(
                "Sorts", page,
                ["Sort By", "Direction"], rows, highlights,
                accent_color=(70, 30, 140),
            )

        # ── Report Specification (Date & DB data) ──────────────────────
        if m in ("DATE_FORMAT_VALIDATION", "DB_REPORT_DATA_VALIDATION"):
            rows = []
            highlights = []
            page = dsd.report_specification[0].source_page if dsd.report_specification else None
            valid = [r for r in dsd.report_specification if r.business_label and r.business_label.strip()]
            for idx, row in enumerate(valid):
                proc = row.processing_rules or ""
                lbl_lower = (row.business_label or "").strip().lower()
                # For date: show only date-related rows; for DB: show all
                if m == "DATE_FORMAT_VALIDATION":
                    if not ("date" in proc.lower() or "mm/" in proc.lower() or lbl_lower in target_labels):
                        continue
                rows.append([
                    row.business_label or "",
                    row.source_table or "",
                    row.source_column or "",
                    proc[:60],
                ])
                if lbl_lower in target_labels or (source_column and source_column in lbl_lower):
                    highlights.append(len(rows) - 1)
            if not rows:
                return None
            section_name = "Report Specification"
            if m == "DB_REPORT_DATA_VALIDATION":
                section_name = "Report Specification / Report Body"
            return _SectionData(
                section_name, page,
                ["Business Label", "Source Table", "Source Column", "Processing Rules"],
                rows, highlights,
                accent_color=(10, 100, 60),
            )

        # ── Control Breaks ─────────────────────────────────────────────
        if m == "CONTROL_BREAK_VALIDATION":
            rows = []
            highlights = []
            page = dsd.control_breaks[0].source_page if dsd.control_breaks else None
            valid = [cb for cb in dsd.control_breaks if cb.control_break and cb.control_break.strip()]
            for idx, cb in enumerate(valid):
                rows.append([cb.control_break, cb.level or ""])
                if source_column and source_column in (cb.control_break or "").lower():
                    highlights.append(idx)
            if not rows:
                return None
            return _SectionData(
                "Control Breaks", page,
                ["Control Break Field", "Level"], rows, highlights,
                accent_color=(140, 60, 10),
            )

        # ── Counts & Totals ────────────────────────────────────────────
        if m == "DB_COUNT_VALIDATION":
            rows = []
            highlights = []
            page = None
            if dsd.counts:
                page = dsd.counts[0].source_page
            elif dsd.totals:
                page = dsd.totals[0].source_page
            for c in dsd.counts:
                if c.count and c.count.strip():
                    rows.append(["Count", c.count, c.level or ""])
            for t in dsd.totals:
                if t.total and t.total.strip():
                    rows.append(["Total", t.total, t.level or ""])
            if not rows:
                return None
            return _SectionData(
                "Counts & Totals", page,
                ["Type", "Field / Label", "Level"], rows, highlights,
                accent_color=(120, 20, 80),
            )

        # ── Report Definition (metadata) ───────────────────────────────
        if m == "REPORT_NAME_DESCRIPTION_VALIDATION":
            rd = dsd.report_definition
            if not rd:
                return None
            rows = [
                ["Report ID", rd.client_report_id or ""],
                ["Report Title", (rd.report_title or "")[:80]],
                ["Description", (rd.report_description or "")[:80]],
                ["Division/Dept", rd.client_division_department or ""],
                ["Source Type", rd.report_source_type or ""],
            ]
            rows = [r for r in rows if r[1]]
            if not rows:
                return None
            return _SectionData(
                "Report Definition", rd.source_page,
                ["Field", "Value"], rows, [],
                accent_color=(30, 100, 140),
            )

        # ── Output / Script ────────────────────────────────────────────
        if m in ("SCRIPT_OUTPUT_VALIDATION", "OUTPUT_DELIVERY_VALIDATION"):
            out = dsd.output
            ret = dsd.retention
            rows = []
            page = out.source_page if out else (ret.source_page if ret else None)
            if out:
                if out.report_output_format:
                    rows.append(["Output Format", (out.report_output_format or "")[:80]])
                if out.reporting_portal:
                    rows.append(["Reporting Portal", out.reporting_portal])
                if out.report_output_distribution_groups:
                    rows.append(["Distribution Groups", out.report_output_distribution_groups])
            if ret:
                if ret.report_retention_type:
                    rows.append(["Retention Type", ret.report_retention_type])
                if ret.report_output_versions:
                    rows.append(["Output Versions", ret.report_output_versions])
            if not rows:
                return None
            return _SectionData(
                "Report Output / Retention", page,
                ["Property", "Value"], rows, [],
                accent_color=(80, 80, 10),
            )

        # ── Selection Criteria / No-Data ───────────────────────────────
        if m == "NO_DATA_VALIDATION":
            rows = []
            page = dsd.selection_criteria[0].source_page if dsd.selection_criteria else None
            for sc in dsd.selection_criteria:
                if sc.report_field and sc.report_field.strip():
                    rows.append(["Selection Field", sc.report_field])
            for p in dsd.parameters:
                if p.parameter_description and p.parameter_description.strip():
                    rows.append(["Parameter", p.parameter_description])
            if not rows:
                return None
            return _SectionData(
                "Selection Criteria", page,
                ["Type", "Value"], rows, [],
                accent_color=(30, 100, 100),
            )

        # ── Report Generation (Scheduled) ──────────────────────────────
        if m == "SCHEDULED_EXECUTION_VALIDATION":
            rg = dsd.report_generation
            if not rg:
                return None
            rows = []
            if rg.report_frequency_type:
                rows.append(["Frequency Type", rg.report_frequency_type])
            if rg.scheduled_timeframe:
                rows.append(["Scheduled Timeframe", rg.scheduled_timeframe])
            if rg.other_explain:
                rows.append(["Other/Explain", rg.other_explain])
            if rg.report_data_accumulation_type:
                rows.append(["Data Accumulation", rg.report_data_accumulation_type])
            if not rows:
                return None
            return _SectionData(
                "Report Generation", rg.source_page,
                ["Property", "Value"], rows, [],
                accent_color=(10, 80, 120),
            )

        # ── Duplicate / Lookup — use report spec as fallback ──────────
        if m in ("DUPLICATE_VALIDATION", "LOOKUP_VALIDATION"):
            rows = []
            highlights = []
            page = dsd.report_specification[0].source_page if dsd.report_specification else None
            valid = [r for r in dsd.report_specification if r.business_label and r.business_label.strip()]
            for idx, row in enumerate(valid):
                rows.append([row.business_label or "", row.source_table or "", row.source_column or ""])
                if (row.business_label or "").strip().lower() in target_labels:
                    highlights.append(idx)
            if not rows:
                return None
            return _SectionData(
                "Report Specification", page,
                ["Business Label", "Source Table", "Source Column"],
                rows, highlights,
                accent_color=(80, 40, 120),
            )

        return None

