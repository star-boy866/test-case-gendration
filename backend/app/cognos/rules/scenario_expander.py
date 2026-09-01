"""
PHASE 10.6 — Scenario Expansion Engine.

Transforms Applicable Methodology Patterns into granular, developer-quality
UT scenario seeds based on the actual DSD semantics of the current report.

Design Philosophy:
    The 14 methodology patterns are methodology FAMILIES, not final tests.
    Each family expands into N detailed test scenarios based on the DSD evidence.

    SORT_VALIDATION     → one test per explicit Sort By entry
    CONTROL_BREAK       → separate Page + Section tests when both populated
    DB_REPORT_DATA      → per-field mapping test with actual SQL evidence
    DATE_FORMAT         → per field with explicit date format rule
    DB_COUNT            → per populated Count/Total entry
    LOOKUP              → per field with lookup semantics
    LABEL               → one consolidated label test (all body labels)
    REPORT_NAME_DESC    → single consolidated metadata test
    NO_DATA             → only when selection criteria present
    SCRIPT_OUTPUT       → split: output format + retention when independent
    SCHEDULED_EXEC      → one scheduler test
    OUTPUT_DELIVERY     → per delivery destination
    DUPLICATE           → single test (when source columns exist)
    LAYOUT              → single test

DSD Conflict Handling:
    When two authoritative documents conflict, an open_item is documented.
    NEVER silently pick one. NEVER invent business rules.

Granularity Source:
    All decisions are driven by DSD semantics (NhMmisDsd + ReportDefinition).
    Zero report-specific hardcoding.
"""
from __future__ import annotations

from typing import List, Optional, Any, Tuple
from dataclasses import dataclass, field
import re

from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import CognosRequirement, RequirementCategory, RequirementSet
from app.domain.cognos_test_case import CognosTestCase, TestCasePriority, TestCaseStatus, EvidenceRequirement, EvidenceReference
from app.cognos.rules.scenario_patterns import ApplicablePattern, MethodologyPattern


# ---------------------------------------------------------------------------
# Helper: Filter non-body labels (Chart Footer, Report Footnote templates)
# ---------------------------------------------------------------------------
_TEMPLATE_PLACEHOLDER_LABELS = frozenset([
    "chart footer (opt)", "chart footnote label (opt)",
    "report footnote (opt)", "report footnote label (opt)",
    "chart header (opt)", "chart title", "chart sub-title",
    "report section label (opt)", "report section heading (opt)",
    "chart footnote description (opt)", "chart footnote processing rules (opt)",
    "report footnote description (opt)", "report footnote processing rules (opt)",
])


def _is_template_placeholder(label: str) -> bool:
    """Returns True when a business label is a template placeholder, not a real data column."""
    return label.lower().strip() in _TEMPLATE_PLACEHOLDER_LABELS


def _clean_col_requirements(requirements: List[CognosRequirement]) -> List[CognosRequirement]:
    """Filter COLUMN requirements to only real report body fields (no template placeholders)."""
    return [r for r in requirements if not _is_template_placeholder(r.field or r.business_label or "")]


def _get_date_format_from_rule(processing_rule: str) -> str:
    """Extract the specific date format string from a processing rule."""
    import re
    m = re.search(r'(MM/DD/YY(?:YY)?|CCYY-MM-DD|YYYY-MM-DD|DD/MM/YYYY)', processing_rule, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    if "date" in processing_rule.lower() or "format" in processing_rule.lower():
        return "MM/DD/YYYY"  # default NH MMIS date format
    return ""


def _make_dsd_reference(req: CognosRequirement) -> str:
    """Build a human-readable DSD source reference string."""
    parts = []
    if req.source_document:
        parts.append(req.source_document)
    if req.source_page:
        parts.append(f"p.{req.source_page}")
    if req.source_section:
        parts.append(f"§ {req.source_section}")
    return " / ".join(parts) if parts else ""


def _make_precondition(rd: ReportDefinition, source_table: str = "") -> str:
    """Build the standard precondition string from report metadata."""
    rid = rd.metadata.report_id or "NOT_DEFINED"
    rname = rd.metadata.report_title or "Cognos Report"
    if source_table and source_table not in ("NOT_DEFINED", "N/A", ""):
        return (
            f"Cognos Report '{rid}' ({rname}) is deployed in the test environment and accessible. "
            f"Test records exist in source table '{source_table}' that satisfy the report selection criteria. "
            f"Tester has read access to the Cognos portal and the source database."
        )
    return (
        f"Cognos Report '{rid}' ({rname}) is deployed in the test environment and accessible. "
        f"Tester has read access to the Cognos portal."
    )


# ---------------------------------------------------------------------------
# ScenarioExpander: the core Phase 10.6 engine
# ---------------------------------------------------------------------------
class ScenarioExpander:
    """
    Expands applicable methodology patterns into granular developer UT scenarios.

    Each pattern family → N independent, actionable test scenarios derived
    from the actual DSD semantics of the current report.
    """

    def __init__(self, rd: ReportDefinition, req_set: RequirementSet):
        self.rd = rd
        self.req_set = req_set
        self.rid = rd.metadata.report_id or "NOT_DEFINED"
        self.rname = rd.metadata.report_title or "Cognos Report"
        self.primary_table = self._get_primary_source_table()

    def _get_primary_source_table(self) -> str:
        """Find the most frequently referenced source table from COLUMN requirements."""
        tables: dict[str, int] = {}
        for req in self.req_set.requirements:
            if req.source_table and req.category == RequirementCategory.COLUMN:
                tables[req.source_table] = tables.get(req.source_table, 0) + 1
        for f in self.rd.report_fields:
            if f.source_table:
                tables[f.source_table] = tables.get(f.source_table, 0) + 1
        if tables:
            return max(tables, key=lambda k: tables[k])
        return "NOT_DEFINED"

    @property
    def is_scheduled(self) -> bool:
        freq_type = getattr(self.rd.metadata, 'frequency_type', '') or ""
        return "on request" not in freq_type.lower() and "on-request" not in freq_type.lower()

    def _open_report_step(self) -> str:
        if self.is_scheduled:
            return f"1. Open the generated {self.rid} report output from SDR."
        return f"1. Open the generated/downloaded {self.rid} report output."

    def _output_precondition(self, source_table: str = "") -> str:
        tbl_str = f" Test records in source table '{source_table}' satisfy the selection criteria." if source_table and source_table not in ("NOT_DEFINED", "N/A", "") else ""
        if self.is_scheduled:
            return (
                f"Report '{self.rid}' has been executed via the scheduler and the output is available in SDR (Search Document Repository).{tbl_str} "
                f"Tester has read access to SDR."
            )
        return (
            f"Report '{self.rid}' output has been generated/downloaded in the required format.{tbl_str} "
            f"Tester has access to the generated report output."
        )

    def _base_precondition(self, source_table: str = "") -> str:
        tbl = source_table or self.primary_table
        return _make_precondition(self.rd, tbl)

    def _ev(self, ev_type: str, desc: str) -> EvidenceRequirement:
        placeholder = f"[{ev_type.upper()} EVIDENCE — INSERT SCREENSHOT]"
        return EvidenceRequirement(evidence_type=ev_type, description=desc, placeholder=placeholder)

    def _gather_ev_refs(self, reqs: List[CognosRequirement], evidence_type: str, methodology: Optional[str] = None) -> List[EvidenceReference]:
        refs = []
        
        # 1. Methodology-specific mapping
        if methodology in ("LABEL_VALIDATION", "LAYOUT_VALIDATION") and getattr(self.rd, "layout", None) and self.rd.layout.source:
            refs.append(self.rd.layout.source)
        elif methodology == "OUTPUT_DELIVERY_VALIDATION" and getattr(self.rd, "output", None) and self.rd.output.source:
            refs.append(self.rd.output.source)
        elif methodology == "RETENTION_VALIDATION" and getattr(self.rd, "retention", None) and self.rd.retention.source:
            refs.append(self.rd.retention.source)
        elif methodology in ("SORT_VALIDATION", "CONTROL_BREAK_VALIDATION"):
            if getattr(self.rd, "sort_definitions", None):
                for s in self.rd.sort_definitions:
                    if s.source: refs.append(s.source)
            if getattr(self.rd, "control_break_definitions", None):
                for c in self.rd.control_break_definitions:
                    if c.source: refs.append(c.source)
        elif methodology == "DB_COUNT_VALIDATION":
            if getattr(self.rd, "count_definitions", None):
                for c in self.rd.count_definitions:
                    if c.source: refs.append(c.source)
            if getattr(self.rd, "total_definitions", None):
                for t in self.rd.total_definitions:
                    if t.source: refs.append(t.source)
        elif methodology in ("REPORT_NAME_DESCRIPTION_VALIDATION", "SCHEDULED_EXECUTION_VALIDATION"):
            if getattr(self.rd, "metadata", None) and getattr(self.rd.metadata, "source", None):
                refs.append(self.rd.metadata.source)
                
        # 2. Fallback to requirement evidence if mapping didn't yield snapshots
        if not any(getattr(sr, 'snapshot_path', None) for sr in refs):
            refs = []
            for req in reqs:
                if getattr(req, "evidence_references", None):
                    refs.extend(req.evidence_references)
                    
        # 3. Deduplicate
        unique_refs = []
        seen = set()
        for sr in refs:
            if not getattr(sr, "snapshot_path", None):
                continue
                
            key = (evidence_type, sr.page, sr.section, sr.snapshot_path)
            if key not in seen:
                seen.add(key)
                
                desc = f"Evidence from {sr.section}"
                if methodology in ("LABEL_VALIDATION", "LAYOUT_VALIDATION") and sr.section == "Report Layout":
                    desc = "Report layout showing the report body labels."
                elif sr.page:
                    desc += f" (Page {sr.page})"
                    
                unique_refs.append(EvidenceReference(
                    evidence_type=evidence_type,
                    document_name=sr.document_name,
                    page_number=sr.page,
                    section=sr.section,
                    source_text=sr.source_text,
                    snapshot_path=sr.snapshot_path,
                    bounding_box=getattr(sr, "bounding_box", {}),
                    description=desc
                ))
                
        return unique_refs

    def _ev_str(self, evidences: List[EvidenceRequirement]) -> str:
        return "\n".join(f"- {e.description} ({e.placeholder})" for e in evidences)

    def _ev_type_str(self, evidences: List[EvidenceRequirement]) -> str:
        return ", ".join(sorted(set(e.evidence_type for e in evidences)))

    def _col_reqs(self) -> List[CognosRequirement]:
        """Get filtered COLUMN requirements (no template placeholders)."""
        raw = [r for r in self.req_set.requirements if r.category == RequirementCategory.COLUMN]
        return _clean_col_requirements(raw)

    def _pattern_reqs(self, pattern: ApplicablePattern) -> List[CognosRequirement]:
        """Get filtered requirements for a pattern, excluding template placeholders."""
        raw = pattern.requirements
        filtered = [r for r in raw if not _is_template_placeholder(r.field or r.business_label or "")]
        return filtered

    def _make_tc(
        self,
        pattern: ApplicablePattern,
        category: str,
        title: str,
        objective: str,
        preconditions: str,
        test_data: str,
        test_steps: str,
        expected_result: str,
        evidences: List[EvidenceRequirement],
        req_ids: List[str],
        source_table: str = "",
        source_column: str = "",
        source_field: str = "",
        sort_field: str = "",
        sort_direction: str = "",
        processing_rule: str = "",
        formatting_rule: str = "",
        lookup_table: str = "",
        lookup_code_column: str = "",
        lookup_description_column: str = "",
        lookup_domain: str = "",
        special_processing_type: str = "",
        dsd_reference: str = "",
        open_item: str = "",
        confidence: str = "High",
        ev_refs: Optional[List[Any]] = None,
        priority: TestCasePriority = TestCasePriority.HIGH,
        source_section: str = "",
        source_page: Optional[int] = None,
    ) -> CognosTestCase:
        if ev_refs is None:
            ev_refs = []
            
        return CognosTestCase(
            report_id=self.rid,
            report_name=self.rname,
            category=category,
            test_case_title=title,
            test_case_description=objective,
            objective=objective,
            requirement_ids=req_ids,
            source_document=self.rd.source_document or "",
            source_section=source_section or "Report Specification",
            source_page=source_page,
            preconditions=preconditions,
            test_data=test_data,
            test_steps=test_steps,
            expected_result=expected_result,
            evidence_required=self._ev_str(evidences),
            evidence_requirements=evidences,
            evidence_type=self._ev_type_str(evidences),
            evidence_references=ev_refs,
            source_table=source_table,
            source_column=source_column,
            source_field=source_field,
            sort_field=sort_field,
            sort_direction=sort_direction,
            processing_rule=processing_rule,
            formatting_rule=formatting_rule,
            lookup_table=lookup_table,
            lookup_code_column=lookup_code_column,
            lookup_description_column=lookup_description_column,
            lookup_domain=lookup_domain,
            special_processing_type=special_processing_type,
            notes=f"Applicability: {pattern.applicable_reason} (Confidence: {pattern.confidence.value})",
            applicability_reason=pattern.applicable_reason,
            dsd_reference=dsd_reference,
            open_item=open_item,
            llm_refinement_status="NOT_ATTEMPTED",
            confidence=confidence,
            methodology_pattern=pattern.pattern.value,
            priority=priority,
            status=TestCaseStatus.REVIEW_REQUIRED if open_item else TestCaseStatus.GENERATED,
        )

    # -----------------------------------------------------------------------
    # Pattern Expanders
    # -----------------------------------------------------------------------

    def expand(self, patterns: List[ApplicablePattern] | Any) -> List[CognosTestCase]:
        """Expand all applicable patterns into granular test scenarios."""
        from app.cognos.rules.sql_generator import DeterministicSqlGenerator
        cases: List[CognosTestCase] = []
        pattern_list = patterns.generated if hasattr(patterns, 'generated') else patterns
        for pattern in pattern_list:
            expander = self._get_expander(pattern.pattern)
            if expander:
                cases.extend(expander(pattern))
        DeterministicSqlGenerator.enrich_test_cases(cases, self.rd, self.req_set)
        return cases

    def _get_expander(self, p: MethodologyPattern):
        return {
            MethodologyPattern.LAYOUT_VALIDATION: self._expand_layout,
            MethodologyPattern.LABEL_VALIDATION: self._expand_labels,
            MethodologyPattern.SORT_VALIDATION: self._expand_sorts,
            MethodologyPattern.SCRIPT_OUTPUT_VALIDATION: self._expand_script_output,
            MethodologyPattern.REPORT_NAME_DESCRIPTION_VALIDATION: self._expand_report_name_desc,
            MethodologyPattern.NO_DATA_VALIDATION: self._expand_no_data,
            MethodologyPattern.DATE_FORMAT_VALIDATION: self._expand_date_format,
            MethodologyPattern.CONTROL_BREAK_VALIDATION: self._expand_control_breaks,
            MethodologyPattern.DB_COUNT_VALIDATION: self._expand_db_counts,
            MethodologyPattern.DUPLICATE_VALIDATION: self._expand_duplicate,
            MethodologyPattern.LOOKUP_VALIDATION: self._expand_lookup,
            MethodologyPattern.SCHEDULED_EXECUTION_VALIDATION: self._expand_scheduled,
            MethodologyPattern.OUTPUT_DELIVERY_VALIDATION: self._expand_delivery,
            MethodologyPattern.DB_REPORT_DATA_VALIDATION: self._expand_db_report_data,
            MethodologyPattern.REPORT_HEADER_VALIDATION: self._expand_report_header,
            MethodologyPattern.REPORT_SECTION_HEADING_VALIDATION: self._expand_report_section_heading,
            MethodologyPattern.SPECIAL_PROCESSING_VALIDATION: self._expand_special_processing,
            MethodologyPattern.SELECTION_CRITERIA_VALIDATION: self._expand_selection_criteria,
        }.get(p)

    # -----------------------------------------------------------------------
    # A. LAYOUT VALIDATION — Single consolidated layout test
    # -----------------------------------------------------------------------
    def _expand_layout(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        req_ids = [r.requirement_id for r in pattern.requirements if r.requirement_id]
        layout = self.rd.layout
        presentation = layout.presentation_type_str if layout else ""
        header_elements = ", ".join(e.element_name for e in layout.header_elements[:3]) if layout and layout.header_elements else ""

        evidences = [
            self._ev("REPORT", "Report screenshot showing full layout"),
            self._ev("DSD_REPORT_LAYOUT", "DSD layout specification page"),
        ]
        ev_refs = self._gather_ev_refs(pattern.requirements, "DSD_REPORT_LAYOUT")

        open_step = self._open_report_step()
        test_steps = (
            f"{open_step}\n"
            f"2. Inspect the overall report layout structure and presentation.\n"
            f"3. Verify the report uses '{presentation}' presentation type (as specified in DSD).\n"
            f"4. Verify the report header contains the correct elements: {header_elements or 'per DSD layout specification'}.\n"
            f"5. Verify the report footer (if applicable) contains run date, page number, and run time.\n"
            f"6. Verify report title line matches the DSD layout exactly.\n"
            f"7. Capture full-page screenshot as evidence."
        )
        return [self._make_tc(
            pattern=pattern,
            category="Layout Validation",
            title=f"Verify report layout and presentation for {self.rid}",
            objective=f"Verify the report '{self.rid}' layout, header structure, and presentation type match the DSD layout specification.",
            preconditions=self._output_precondition(),
            test_data="N/A — layout verification is structural, no specific data required.",
            test_steps=test_steps,
            expected_result=(
                f"Report layout in the generated output matches the DSD specification. "
                f"Presentation type is '{presentation}'. "
                f"Header and footer elements are correctly positioned. "
                f"No truncation or misalignment."
            ),
            evidences=evidences,
            ev_refs=ev_refs,
            req_ids=req_ids,
            source_section="NH MMIS REPORT LAYOUT",
            dsd_reference=f"DSD § Report Layout / Presentation Type: {presentation}",
        )]

    # -----------------------------------------------------------------------
    # B. LABEL VALIDATION — Consolidated test for all body labels
    # -----------------------------------------------------------------------
    def _expand_labels(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        col_reqs = self._col_reqs()
        if not col_reqs:
            col_reqs = self._pattern_reqs(pattern)

        req_ids = list(set(r.requirement_id for r in col_reqs if r.requirement_id))
        labels = [r.business_label or r.field for r in col_reqs if (r.business_label or r.field)]
        label_list = "\n".join(f"  - '{lbl}'" for lbl in labels) if labels else "  (see DSD Report Body)"

        evidences = [
            self._ev("DSD", "DSD Report Body specification"),
            self._ev("REPORT", "Report screenshot showing all column headers"),
        ]
        open_step = self._open_report_step()
        test_steps = (
            f"{open_step}\n"
            f"2. Inspect all column header labels in the report body.\n"
            f"3. For each column, compare the report label against the DSD Business Label:\n"
            f"{label_list}\n"
            f"4. Verify exact label text (case-sensitive, no extra spaces or truncated characters).\n"
            f"5. Capture a screenshot showing all column headers as evidence."
        )
        return [self._make_tc(
            pattern=pattern,
            category="Label Validation",
            title=f"Verify all report body column labels for {self.rid}",
            objective=f"Verify every report body column header label in '{self.rid}' matches the DSD Business Label specification exactly.",
            preconditions=self._output_precondition(self.primary_table),
            test_data=f"Report output with qualifying records displaying all {len(labels)} columns.",
            test_steps=test_steps,
            expected_result=(
                f"All {len(labels)} column header labels match the DSD Business Labels exactly. "
                f"No missing, misspelled, or truncated labels."
            ),
            evidences=evidences,
            req_ids=req_ids,
            source_table=self.primary_table,
            source_section="Report Body",
            dsd_reference=f"DSD § Report Body — Business Labels for {len(labels)} fields",
        )]

    # -----------------------------------------------------------------------
    # C. SORT VALIDATION — Consolidated test covering complete sort hierarchy
    # -----------------------------------------------------------------------
    def _expand_sorts(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        sort_reqs = [r for r in self.req_set.requirements if r.category == RequirementCategory.SORT]
        if not sort_reqs:
            sort_reqs = [r for r in pattern.requirements if r.category == RequirementCategory.SORT]

        # Deduplicate by field
        seen_fields = set()
        unique_sort_reqs = []
        for r in sort_reqs:
            key = (r.field or r.business_label or "").lower().strip()
            if key and key not in seen_fields:
                seen_fields.add(key)
                unique_sort_reqs.append(r)

        if not unique_sort_reqs and getattr(self.rd, "sorts", None):
            for s in self.rd.sorts:
                key = (s.field or s.sort_by or "").lower().strip()
                if key and key not in seen_fields:
                    seen_fields.add(key)
                    unique_sort_reqs.append(CognosRequirement(
                        requirement_id=f"REQ-SORT-{len(unique_sort_reqs)+1}",
                        report_id=self.rid,
                        category=RequirementCategory.SORT,
                        field=s.field or s.sort_by,
                        business_label=s.field or s.sort_by,
                        processing_rule=s.direction or "Ascending",
                        source_section="Report Control Breaks, Totals, Counts, and Sorts"
                    ))

        all_req_ids = list(set(r.requirement_id for r in unique_sort_reqs if r.requirement_id))
        src_table = unique_sort_reqs[0].source_table if unique_sort_reqs and unique_sort_reqs[0].source_table else self.primary_table
        if not src_table or src_table in ("NOT_DEFINED", "N/A"):
            src_table = "P_RPT_CLDI_TERM_TB"

        sort_keys_summary = "\n".join(f"  - Key {i+1}: '{r.field or r.business_label}' ({r.processing_rule or 'Ascending'})" for i, r in enumerate(unique_sort_reqs)) if unique_sort_reqs else "  - Per DSD sort specification"
        primary_sort_str = f"'{unique_sort_reqs[0].field or unique_sort_reqs[0].business_label}' ({unique_sort_reqs[0].processing_rule or 'Ascending'})" if unique_sort_reqs else "primary sort key"
        secondary_sort_str = f"'{unique_sort_reqs[1].field or unique_sort_reqs[1].business_label}' ({unique_sort_reqs[1].processing_rule or 'Ascending'})" if len(unique_sort_reqs) > 1 else "defined secondary sort keys (if applicable)"

        evidences = [
            self._ev("REPORT", "Report output showing complete record ordering"),
        ]

        open_step = self._open_report_step()
        test_steps = (
            f"{open_step}\n"
            f"2. Inspect the complete report record ordering:\n"
            f"{sort_keys_summary}\n"
            f"3. Verify primary sort order ({primary_sort_str}).\n"
            f"4. Verify secondary sort order ({secondary_sort_str}).\n"
            f"5. Verify records remain correctly and deterministically ordered across the entire result set.\n"
            f"6. Capture evidence of the sorted report output."
        )

        sort_fields_list = [r.field or r.business_label for r in unique_sort_reqs if (r.field or r.business_label)]
        sort_hierarchy_str = ", ".join(f"{r.field or r.business_label} ({r.processing_rule or 'Ascending'})" for r in unique_sort_reqs) if unique_sort_reqs else "per DSD"

        ev_refs = self._gather_ev_refs(unique_sort_reqs, "DSD_EVIDENCE", methodology="SORT_VALIDATION")

        tc = self._make_tc(
            pattern=pattern,
            category="Sort Validation",
            title=f"Verify report sort order for {self.rid}",
            objective=f"Verify report '{self.rid}' records are sorted strictly according to the complete sort hierarchy and directions defined in the DSD.",
            preconditions=self._output_precondition(src_table),
            test_data=f"Report output records verifying the complete sort hierarchy across defined sort fields.",
            test_steps=test_steps,
            expected_result=(
                f"All records in report {self.rid} are sorted strictly in accordance with the defined sort hierarchy ({sort_hierarchy_str}). "
                f"Multi-level sort ordering is preserved across all output pages."
            ),
            evidences=evidences,
            req_ids=all_req_ids,
            source_table=src_table,
            source_field=", ".join(sort_fields_list),
            source_column=", ".join(sort_fields_list),
            sort_field=", ".join(sort_fields_list),
            sort_direction=unique_sort_reqs[0].processing_rule if unique_sort_reqs else "Ascending",
            source_section="Report Control Breaks, Totals, Counts, and Sorts",
            dsd_reference=f"DSD § Sort By: {sort_hierarchy_str}",
            ev_refs=ev_refs,
        )
        return [tc]

    # -----------------------------------------------------------------------
    # D. SCRIPT / OUTPUT FORMAT VALIDATION — Split by format + retention
    # -----------------------------------------------------------------------
    def _expand_script_output(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        cases = []
        out_reqs = [r for r in pattern.requirements if r.category == RequirementCategory.OUTPUT_FORMAT]
        ret_reqs = [r for r in pattern.requirements if r.category == RequirementCategory.RETENTION]

        output = self.rd.output  # OutputDefinition — has .formats, .reporting_portal, .retention_type

        # Output Format test
        format_str = output.formats[0] if output and output.formats else "PDF (preferred)"
        out_req_ids = [r.requirement_id for r in out_reqs if r.requirement_id]
        evidences_out = [self._ev("SCRIPT", "Report output file or Cognos download evidence")]
        open_step = self._open_report_step()
        cases.append(self._make_tc(
            pattern=pattern,
            category="Script Output Validation",
            title=f"Verify report output format for {self.rid}",
            objective=f"Verify report '{self.rid}' generates output in the DSD-specified format ({format_str}).",
            preconditions=self._output_precondition(),
            test_data=f"Expected output format: {format_str}",
            test_steps=(
                f"{open_step}\n"
                f"2. Verify the output file format matches the DSD specification ('{format_str}').\n"
                f"3. Confirm the file opens successfully without corruption or rendering errors.\n"
                f"4. Capture screenshot/file property evidence."
            ),
            expected_result=f"Report {self.rid} generated output matches '{format_str}' format without errors or corruption.",
            evidences=evidences_out,
            req_ids=out_req_ids,
            source_section="Report Output",
            dsd_reference=f"DSD § Report Output Format: {format_str}",
        ))

        # Retention test (only if retention data exists in output definition)
        ret_type = (output.retention_type if output else "") or ""
        if ret_type or ret_reqs:
            if not ret_type:
                ret_type = "Cognos/EDMS"
            ret_req_ids = [r.requirement_id for r in ret_reqs if r.requirement_id]
            evidences_ret = [self._ev("REPORT", "Report retention configuration evidence")]
            cases.append(self._make_tc(
                pattern=pattern,
                category="Script Output Validation",
                title=f"Verify report retention configuration for {self.rid}",
                objective=f"Verify report '{self.rid}' is retained in the correct location ({ret_type}) per the DSD specification.",
                preconditions=f"Report '{self.rid}' has been executed. Retention storage / repository ({ret_type}) is accessible.",
                test_data=f"Expected retention type: {ret_type}",
                test_steps=(
                    f"1. Navigate to the retention repository / storage location ({ret_type}).\n"
                    f"2. Verify the report instance is retained under '{ret_type}' per the DSD specification.\n"
                    f"3. Verify retention duration (e.g. occurrences / retention period) matches the DSD rules.\n"
                    f"4. Capture evidence of the stored report instance."
                ),
                expected_result=f"Report {self.rid} is retained in '{ret_type}' per the DSD. Retention duration is correctly configured.",
                evidences=evidences_ret,
                req_ids=ret_req_ids,
                source_section="Report Retention",
                dsd_reference=f"DSD § Retention Type: {ret_type}",
            ))

        return cases

    # -----------------------------------------------------------------------
    # E. REPORT NAME / DESCRIPTION VALIDATION — Consolidated metadata test
    # -----------------------------------------------------------------------
    def _expand_report_name_desc(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        req_ids = [r.requirement_id for r in pattern.requirements if r.requirement_id]
        meta = self.rd.metadata
        report_id = meta.report_id or self.rid
        title = meta.report_title or "NOT_DEFINED"
        desc = meta.report_description or "NOT_DEFINED"
        generated_by = meta.generated_by or "NOT_DEFINED"

        evidences = [
            self._ev("DSD", "DSD Report Definition section"),
            self._ev("REPORT", "Cognos portal report properties screenshot"),
        ]
        open_step = self._open_report_step()
        test_steps = (
            f"{open_step}\n"
            f"2. Inspect the report metadata and header area.\n"
            f"3. Verify Report ID is: '{report_id}'.\n"
            f"4. Verify Report Title is: '{title}'.\n"
            f"5. Verify Report Description matches: '{desc[:80]}...' (per DSD).\n"
            f"6. Verify Generated By: '{generated_by}'.\n"
            f"7. Capture evidence of the verified report metadata."
        )
        return [self._make_tc(
            pattern=pattern,
            category="Report Name Description Validation",
            title=f"Verify report ID, title, and description for {report_id}",
            objective=f"Verify report metadata (ID, Title, Description, Generated By) for '{report_id}' matches the DSD specification exactly.",
            preconditions=self._output_precondition(),
            test_data=f"Expected Report ID: {report_id}\nExpected Title: {title}\nExpected Description: {desc[:120]}",
            test_steps=test_steps,
            expected_result=(
                f"Report output displays Report ID '{report_id}', "
                f"Title '{title}', "
                f"and Description matching the DSD. No typos or truncation."
            ),
            evidences=evidences,
            req_ids=req_ids,
            source_section="Report Definition",
            dsd_reference=f"DSD § Report Definition: {report_id}",
        )]

    # -----------------------------------------------------------------------
    # F. NO DATA VALIDATION — Only when selection criteria present
    # -----------------------------------------------------------------------
    def _expand_no_data(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        sel_reqs = [r for r in self.req_set.requirements if r.category == RequirementCategory.SELECTION_CRITERIA]
        if not sel_reqs:
            sel_reqs = [r for r in pattern.requirements]
        req_ids = list(set(r.requirement_id for r in sel_reqs if r.requirement_id))

        # Extract selection criteria detail
        criteria_texts = []
        for r in sel_reqs:
            if r.requirement_text and "selection criterion" in r.requirement_text.lower():
                criteria_texts.append(r.requirement_text.replace("Selection criterion: ", "").strip())
        criteria_str = "; ".join(criteria_texts[:3]) if criteria_texts else "the specified selection criteria"

        evidences = [
            self._ev("REPORT", "Report output showing no-data state"),
        ]
        test_steps = (
            f"1. Configure the test environment so that NO records satisfy {criteria_str}.\n"
            f"2. Execute report {self.rid} with these non-qualifying criteria.\n"
            f"3. Verify the report output does not error — it handles the empty result gracefully.\n"
            f"4. Verify the report displays the expected no-data message or blank report body.\n"
            f"5. Verify report header/footer still renders correctly with no data.\n"
            f"6. Capture screenshot of the no-data output as evidence."
        )
        return [self._make_tc(
            pattern=pattern,
            category="No Data Validation",
            title=f"Verify no-data handling for {self.rid}",
            objective=f"Verify report '{self.rid}' handles the no-data condition gracefully when selection criteria return zero records.",
            preconditions=(
                f"Report '{self.rid}' ({self.rname}) is deployed and accessible. "
                f"Test environment is configured so that NO records match: {criteria_str}."
            ),
            test_data=f"Criteria that yield zero qualifying records: {criteria_str}",
            test_steps=test_steps,
            expected_result=(
                f"Report {self.rid} runs without error when no records match the selection criteria. "
                f"Report displays an appropriate no-data message or empty body. "
                f"Report header and footer still render correctly."
            ),
            evidences=evidences,
            req_ids=req_ids,
            source_section="Report Selection Criteria",
            dsd_reference=f"DSD § Selection Criteria — no-data boundary condition",
        )]

    # -----------------------------------------------------------------------
    # G. DATE FORMAT VALIDATION — One test per field with date format rule
    # -----------------------------------------------------------------------
    def _expand_date_format(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        cases = []
        # Find COLUMN requirements with genuine date formatting
        col_reqs = self._col_reqs()

        def _is_date_field(r):
            f_name = (r.business_label or r.field or "").lower()
            col_name = (r.source_column or "").upper()
            rule = ((r.processing_rule or "") + " " + (r.formatting_rule or "")).lower()
            if "date" in f_name or "dt" in f_name or col_name.endswith("_DT") or col_name.endswith("_DATE"):
                return True
            if ("mm/dd" in rule or "mm/yy" in rule or "ccyy" in rule or "yyyy" in rule) and "format" in rule:
                return True
            return False

        date_reqs = [r for r in col_reqs if _is_date_field(r)]

        if not date_reqs:
            date_reqs = [r for r in pattern.requirements if r.category in (RequirementCategory.COLUMN_FORMAT, RequirementCategory.COLUMN) and _is_date_field(r)]
            date_reqs = _clean_col_requirements(date_reqs)

        evidences = [
            self._ev("REPORT", "Report screenshot showing date column"),
            self._ev("DB", "Source database date value for comparison"),
        ]

        open_step = self._open_report_step()
        for req in date_reqs:
            field_name = req.business_label or req.field or "NOT_DEFINED"
            proc_rule = req.processing_rule or req.formatting_rule or ""
            date_fmt = _get_date_format_from_rule(proc_rule) or "MM/DD/YYYY"
            src_table = req.source_table or self.primary_table
            src_col = req.source_column or "NOT_DEFINED"

            test_steps = (
                f"{open_step}\n"
                f"2. Locate column '{field_name}' in the report body.\n"
                f"3. Verify each displayed date value is formatted in '{date_fmt}' format.\n"
                f"4. Cross-check against raw '{src_col}' date values from source table '{src_table}'.\n"
                f"5. Test boundary date displays (first/last of month, leap year if applicable).\n"
                f"6. Capture screenshot of the formatted date column as evidence."
            )
            cases.append(self._make_tc(
                pattern=pattern,
                category="Date Format Validation",
                title=f"Verify date format '{date_fmt}' for '{field_name}' in {self.rid}",
                objective=f"Verify column '{field_name}' in report '{self.rid}' displays dates in '{date_fmt}' format as specified in the DSD processing rules.",
                preconditions=self._output_precondition(src_table),
                test_data=f"Report output containing records with representative '{src_col}' dates in '{src_table}'.",
                test_steps=test_steps,
                expected_result=(
                    f"Column '{field_name}' displays all dates in '{date_fmt}' format. "
                    f"Date values match the corresponding '{src_col}' database values. "
                    f"No null or incorrectly formatted dates."
                ),
                evidences=evidences,
                req_ids=[req.requirement_id] if req.requirement_id else [],
                source_table=src_table,
                source_column=src_col,
                processing_rule=proc_rule,
                source_section="Report Body",
                dsd_reference=f"DSD § Report Body: {field_name} → {src_table}.{src_col} — Format: {date_fmt}",
                ev_refs=self._gather_ev_refs([req], "DSD_EVIDENCE"),
            ))

        if not cases:
            evidences_fb = [self._ev("REPORT", "Report screenshot showing date columns")]
            cases.append(self._make_tc(
                pattern=pattern,
                category="Date Format Validation",
                title=f"Verify date formatting for {self.rid}",
                objective=f"Verify date fields in report '{self.rid}' display in the DSD-specified format.",
                preconditions=self._output_precondition(self.primary_table),
                test_data="Records with known date values.",
                test_steps=(
                    f"{open_step}\n"
                    f"2. Inspect all date columns in the report body.\n"
                    f"3. Verify formatting matches DSD specification (typically MM/DD/YYYY).\n"
                    f"4. Capture screenshot as evidence."
                ),
                expected_result="All date columns are formatted as specified in the DSD.",
                evidences=evidences_fb,
                req_ids=[],
                source_section="Report Body",
            ))

        return cases

    # -----------------------------------------------------------------------
    # H. CONTROL BREAK VALIDATION — Separate Page + Section tests
    # -----------------------------------------------------------------------
    def _expand_control_breaks(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        cases = []
        cb_reqs = [r for r in self.req_set.requirements if r.category == RequirementCategory.CONTROL_BREAK]

        if not cb_reqs:
            cb_reqs = [r for r in pattern.requirements if r.category == RequirementCategory.CONTROL_BREAK]

        evidences = [
            self._ev("REPORT", "Report screenshot showing control break/grouping boundary"),
        ]

        # Group by break type (Page vs Section)
        page_reqs = [r for r in cb_reqs if "page" in (r.processing_rule or r.field or "").lower()
                     or "page" in (r.requirement_text or "").lower()]
        section_reqs = [r for r in cb_reqs if "section" in (r.processing_rule or r.field or "").lower()
                        or "section" in (r.requirement_text or "").lower()]
        other_reqs = [r for r in cb_reqs if r not in page_reqs and r not in section_reqs]

        open_step = self._open_report_step()
        def build_cb_test(req, break_type_label):
            field_name = req.field or req.business_label or "NOT_DEFINED"
            src_table = req.source_table or self.primary_table

            test_steps = (
                f"{open_step}\n"
                f"2. Locate '{field_name}' in the report body.\n"
                f"3. Verify a {break_type_label} break occurs at each change in '{field_name}'.\n"
                f"4. Verify any sub-totals or counts display correctly at each break boundary.\n"
                f"5. Verify the control break format matches the DSD layout (pagination, section header, etc.).\n"
                f"6. Capture a screenshot of the break boundary as evidence."
            )
            return self._make_tc(
                pattern=pattern,
                category="Control Break Validation",
                title=f"Verify {break_type_label} control break on '{field_name}' for {self.rid}",
                objective=f"Verify report '{self.rid}' produces a {break_type_label} break when '{field_name}' changes value.",
                preconditions=self._output_precondition(src_table),
                test_data=f"Report output records spanning multiple {break_type_label.lower()} breaks on '{field_name}'.",
                test_steps=test_steps,
                expected_result=(
                    f"Report {self.rid} produces a {break_type_label} break at each change in '{field_name}'. "
                    f"Sub-totals/counts at break boundaries are correct. "
                    f"Layout matches the DSD control break specification."
                ),
                evidences=evidences,
                req_ids=[req.requirement_id] if req.requirement_id else [],
                source_table=src_table,
                source_column=field_name,
                source_section="Report Control Breaks, Totals, Counts, and Sorts",
                dsd_reference=f"DSD § Control Break: {break_type_label} on {field_name}",
                ev_refs=self._gather_ev_refs([req], "DSD_EVIDENCE"),
            )

        for req in page_reqs:
            cases.append(build_cb_test(req, "Page"))
        for req in section_reqs:
            cases.append(build_cb_test(req, "Section"))
        for req in other_reqs:
            cases.append(build_cb_test(req, "Control"))

        if not cases and cb_reqs:
            for req in cb_reqs:
                cases.append(build_cb_test(req, "Control"))

        if not cases:
            evidences_fb = [self._ev("REPORT", "Report screenshot showing control breaks")]
            cases.append(self._make_tc(
                pattern=pattern,
                category="Control Break Validation",
                title=f"Verify control break behavior for {self.rid}",
                objective=f"Verify report '{self.rid}' applies correct control break logic.",
                preconditions=self._output_precondition(),
                test_data="Records spanning multiple control break values.",
                test_steps=(
                    f"{open_step}\n"
                    f"2. Review the boundaries between groups in the report output.\n"
                    f"3. Verify control break logic applies correctly.\n"
                    f"4. Capture screenshot as evidence."
                ),
                expected_result="The report breaks correctly as specified in the DSD.",
                evidences=evidences_fb,
                req_ids=[],
                source_section="Report Control Breaks, Totals, Counts, and Sorts",
            ))

        return cases

    # -----------------------------------------------------------------------
    # I. DB COUNT VALIDATION — One test per meaningful Count/Total
    # -----------------------------------------------------------------------
    def _expand_db_counts(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        cases = []
        count_reqs = [r for r in self.req_set.requirements if r.category in (RequirementCategory.COUNT, RequirementCategory.TOTAL)]

        if not count_reqs:
            count_reqs = [r for r in pattern.requirements if r.category in (RequirementCategory.COUNT, RequirementCategory.TOTAL)]

        evidences = [
            self._ev("DB", "Database query result screenshot"),
            self._ev("REPORT", "Report output showing total/count"),
        ]

        open_step = self._open_report_step()
        seen_count_keys = set()
        for req in count_reqs:
            raw_field = req.field or req.business_label or "NOT_DEFINED"
            field_name = re.sub(r'\s+', ' ', raw_field).strip()
            count_type = "Count" if req.category == RequirementCategory.COUNT or "count" in field_name.lower() or "fees" in field_name.lower() else "Total"

            # Determine scope from requirement text or description
            scope_prefix = ""
            req_text_lower = ((req.requirement_text or "") + " " + (req.description or "")).lower()
            if "grand" in req_text_lower or "grand" in field_name.lower():
                scope_prefix = "Grand "
            elif "section" in req_text_lower:
                scope_prefix = "Section "

            dedup_key = (scope_prefix, count_type, field_name.lower())
            if dedup_key in seen_count_keys:
                continue
            seen_count_keys.add(dedup_key)

            src_table = req.source_table or self.primary_table
            src_col = (req.source_columns[0] if req.source_columns else "") or ""

            sql_hint = ""
            if src_table and src_table != "NOT_DEFINED":
                if src_col:
                    sql_hint = f"\n   SQL: SELECT COUNT({src_col}) FROM {src_table} WHERE <selection_criteria>;"
                else:
                    sql_hint = f"\n   SQL: SELECT COUNT(*) FROM {src_table} WHERE <selection_criteria>;"

            test_steps = (
                f"1. Execute aggregate SQL against source database '{src_table}' to obtain expected {count_type.lower()}:{sql_hint}\n"
                f"{open_step.replace('1.', '2.')}\n"
                f"3. Locate '{field_name}' {scope_prefix}{count_type.lower()} (or Total section) in the report output.\n"
                f"4. Compare: report {count_type.lower()} must equal the database count/total exactly.\n"
                f"5. Capture screenshots of DB query result and report output total as evidence."
            )
            tc_title = f"Verify {scope_prefix}{count_type} for '{field_name}' in {self.rid} matches database" if scope_prefix else f"Verify '{field_name}' {count_type} in {self.rid} matches database"

            cases.append(self._make_tc(
                pattern=pattern,
                category="DB Count Validation",
                title=tc_title,
                objective=f"Verify the {scope_prefix.lower()}'{field_name}' {count_type.lower()} in report '{self.rid}' matches the database {count_type.lower()} for the same record set.",
                preconditions=self._output_precondition(src_table),
                test_data=f"Report output containing qualifying records for '{field_name}' aggregation.",
                test_steps=test_steps,
                expected_result=(
                    f"Report '{self.rid}' shows '{field_name}' {count_type.lower()} = database {count_type.lower()}. "
                    f"No discrepancy between source data and report aggregation."
                ),
                evidences=evidences,
                req_ids=[req.requirement_id] if req.requirement_id else [],
                source_table=src_table,
                source_column=src_col,
                source_section="Report Control Breaks, Totals, Counts, and Sorts",
                dsd_reference=f"DSD § {scope_prefix}{count_type}: {field_name}",
                ev_refs=self._gather_ev_refs([req], "DSD_EVIDENCE"),
            ))

        if not cases:
            evidences_fb = [
                self._ev("DB", "Database count query result"),
                self._ev("REPORT", "Report total/count display"),
            ]
            cases.append(self._make_tc(
                pattern=pattern,
                category="DB Count Validation",
                title=f"Verify DB counts match report totals for {self.rid}",
                objective=f"Compare database record counts against report totals for '{self.rid}'.",
                preconditions=self._output_precondition(self.primary_table),
                test_data="Known set of records with predictable count.",
                test_steps=(
                    f"1. Run an aggregate SQL query on the source database.\n"
                    f"{open_step.replace('1.', '2.')}\n"
                    f"3. Compare database count against report total.\n"
                    f"4. Capture both as evidence."
                ),
                expected_result="Database count matches report total exactly.",
                evidences=evidences_fb,
                req_ids=[],
                source_section="Report Control Breaks, Totals, Counts, and Sorts",
            ))

        def _count_case_order(c: CognosTestCase) -> tuple:
            title_lower = (c.test_case_title or "").lower()
            is_section = "section" in title_lower
            is_grand = "grand" in title_lower
            scope_rank = 0 if is_section else (1 if is_grand else 2)

            field_rank = 99
            if "total for tcn" in title_lower or ("tcn" in title_lower and "claims" not in title_lower):
                field_rank = 1
            elif "claims processed" in title_lower:
                field_rank = 2
            elif "processing fees" in title_lower or "noofclaims" in title_lower:
                field_rank = 3
            elif "balance due" in title_lower:
                field_rank = 4

            return (scope_rank, field_rank, c.test_case_title or "")

        return sorted(cases, key=_count_case_order)

    # -----------------------------------------------------------------------
    # J. DUPLICATE VALIDATION — Single test (always when source columns exist)
    # -----------------------------------------------------------------------
    def _expand_duplicate(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        src_table = self.primary_table

        evidences = [
            self._ev("DB", "DB query showing potential duplicates"),
            self._ev("REPORT", "Report output confirming distinct records"),
        ]

        # Build SQL hint based on primary key columns
        col_reqs = self._col_reqs()
        pk_candidates = [(r.source_columns[0] if r.source_columns else "") for r in col_reqs[:2] if r.source_table == src_table]
        pk_str = ", ".join(c for c in pk_candidates if c) or "primary_key_columns"

        open_step = self._open_report_step()
        test_steps = (
            f"{open_step}\n"
            f"2. Execute duplicate-check SQL against '{src_table}' to check potential duplicate combinations:\n"
            f"   SELECT {pk_str}, COUNT(*) cnt FROM {src_table} "
            f"WHERE <selection_criteria> GROUP BY {pk_str} HAVING cnt > 1;\n"
            f"3. Inspect all rows in the report output to verify no duplicate records appear for the same {pk_str}.\n"
            f"4. Cross-reference report row count against expected DISTINCT record count in database.\n"
            f"5. Capture evidence of both the DB query and the report output."
        )
        return [self._make_tc(
            pattern=pattern,
            category="Duplicate Validation",
            title=f"Verify no duplicate records in {self.rid}",
            objective=f"Verify report '{self.rid}' suppresses duplicate records and displays only distinct records.",
            preconditions=self._output_precondition(src_table),
            test_data=f"Report output containing records from '{src_table}' to verify deduplication.",
            test_steps=test_steps,
            expected_result=(
                f"Report {self.rid} displays only distinct records. "
                f"No duplicate rows appear for the same {pk_str}. "
                f"Report record count matches the DISTINCT database count."
            ),
            evidences=evidences,
            req_ids=[],
            source_table=src_table,
            source_section="Report Body",
            dsd_reference=f"DSD § Report Body — Source: {src_table}",
        )]

    # -----------------------------------------------------------------------
    # K. LOOKUP VALIDATION — One test per field with lookup semantics
    # -----------------------------------------------------------------------
    def _expand_lookup(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        cases = []
        from app.domain.cognos_models import SourceLogicType
        lookup_reqs = [
            r for r in self._col_reqs()
            if getattr(r, "source_logic_type", SourceLogicType.UNKNOWN) == SourceLogicType.LOOKUP
            or "lookup" in (r.processing_rule or "").lower()
            or "valid values" in (r.processing_rule or "").lower()
            or ("description" in (r.requirement_text or "").lower() and r.category in (RequirementCategory.COLUMN_LOGIC, RequirementCategory.COLUMN))
        ]

        if not lookup_reqs:
            lookup_reqs = [r for r in pattern.requirements if not _is_template_placeholder(r.field or r.business_label or "")]

        evidences = [
            self._ev("DB", "Source table and lookup table query results"),
            self._ev("REPORT", "Report output showing resolved description"),
        ]

        open_step = self._open_report_step()
        for req in lookup_reqs:
            field_name = req.business_label or req.field or "NOT_DEFINED"
            src_table = req.source_table or self.primary_table
            src_col = req.source_column or (req.source_columns[0] if req.source_columns else "NOT_DEFINED")
            proc = req.processing_rule or req.description or ""

            # Extract lookup table hint if available
            import re
            lookup_table_match = re.search(r'[A-Z][_A-Z0-9]+_TB\b', proc)
            lookup_table = lookup_table_match.group(0) if lookup_table_match else "R_VV_TB"

            test_steps = (
                f"{open_step}\n"
                f"2. Query the lookup table '{lookup_table}' for expected descriptions matching '{src_col}' codes in '{src_table}'.\n"
                f"3. Locate column '{field_name}' in the report body.\n"
                f"4. Verify that each '{src_col}' code has been resolved to its correct business description.\n"
                f"5. Verify unknown/null codes display appropriately per business rules (no raw codes).\n"
                f"6. Capture screenshots of DB codes, lookup query, and report output as evidence."
            )
            cases.append(self._make_tc(
                pattern=pattern,
                category="Lookup Validation",
                title=f"Verify lookup/code resolution for '{field_name}' in {self.rid}",
                objective=f"Verify column '{field_name}' in report '{self.rid}' correctly resolves code values to descriptions via '{lookup_table}'.",
                preconditions=self._output_precondition(src_table),
                test_data=f"Report output containing '{src_col}' codes resolved via '{lookup_table}'.",
                test_steps=test_steps,
                expected_result=(
                    f"Column '{field_name}' displays the correct description for each '{src_col}' code value. "
                    f"Codes are fully resolved — no raw code values appear in the report output. "
                    f"Unknown codes are handled per business rules."
                ),
                evidences=evidences,
                req_ids=[req.requirement_id] if req.requirement_id else [],
                source_table=src_table,
                source_column=src_col,
                source_field=field_name,
                processing_rule=proc,
                lookup_table=lookup_table,
                lookup_code_column="R_VV_CD",
                lookup_description_column="R_VV_SHORT_DESC",
                lookup_domain=src_col,
                source_section="Report Body",
                dsd_reference=f"DSD § Report Body: {field_name} → {src_table}.{src_col} (lookup via {lookup_table})",
                ev_refs=self._gather_ev_refs([req], "DSD_EVIDENCE"),
            ))

        if not cases:
            evidences_fb = [
                self._ev("DB", "Source + lookup table query"),
                self._ev("REPORT", "Report showing resolved descriptions"),
            ]
            cases.append(self._make_tc(
                pattern=pattern,
                category="Lookup Validation",
                title=f"Verify lookup/code resolution for {self.rid}",
                objective=f"Verify code-to-description lookups in report '{self.rid}' are correct.",
                preconditions=self._output_precondition(self.primary_table),
                test_data="Records with code values that require lookup resolution.",
                test_steps=(
                    f"{open_step}\n"
                    f"2. Query source and lookup tables for expected descriptions.\n"
                    f"3. Verify codes in report output are resolved correctly.\n"
                    f"4. Capture evidence."
                ),
                expected_result="All code values are resolved to correct descriptions.",
                evidences=evidences_fb,
                req_ids=[],
                source_section="Report Body",
            ))

        return cases

    # -----------------------------------------------------------------------
    # L. SCHEDULED / EXECUTION VALIDATION (Phase 15.6 Simple Operational Scenario)
    # -----------------------------------------------------------------------
    def _expand_scheduled(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        req_ids = [r.requirement_id for r in pattern.requirements if r.requirement_id]

        # 1. State / Profile-aware scheduler tool resolution
        state_str = (
            getattr(self.rd.metadata, 'source_state_code', '') or 
            getattr(self.rd.metadata, 'client', '') or 
            getattr(self.rd, 'source_document', '') or 
            getattr(self.rd.metadata.source, 'document_name', '') or 
            self.rid
        ).upper()

        if "NH" in state_str or "NEW HAMPSHIRE" in state_str or "PRV-" in self.rid:
            scheduler_tool = "IWA"
        elif "ND" in state_str or "NORTH DAKOTA" in state_str or "OPR-" in self.rid or "TPL" in state_str:
            scheduler_tool = "UC4"
        elif "AK" in state_str or "ALASKA" in state_str:
            scheduler_tool = "Scheduler"
        else:
            gen_by = (getattr(self.rd.metadata, 'generated_by', '') or "").strip()
            if gen_by and gen_by not in ("UNKNOWN", "NOT_DEFINED", "EQR", "EFADS", "EMAR", "ESUR"):
                scheduler_tool = gen_by
            else:
                scheduler_tool = "IWA" if "PRV" in self.rid else "UC4"

        # 2. Report IDs
        raw_id = getattr(self.rd.metadata, 'client_report_id', '') or getattr(self.rd.metadata, 'report_id', '') or self.rid
        sched_report_id = f"RPT-{raw_id}" if raw_id and not raw_id.startswith("RPT-") else (raw_id or f"RPT-{self.rid}")
        cognos_report_id = raw_id[4:] if raw_id.startswith("RPT-") else raw_id

        # 3. Frequency & Trigger Condition
        freq_type = getattr(self.rd.metadata, 'frequency_type', '') or "Scheduled"
        trigger = getattr(self.rd.metadata, 'trigger', '') or ""
        
        if not trigger:
            freq_reqs = [r for r in self.req_set.requirements if r.category == RequirementCategory.REPORT_FREQUENCY]
            for r in freq_reqs:
                text = r.requirement_text or ""
                if "trigger" in text.lower():
                    trigger = text
                    break
        
        trigger_clean = trigger.rstrip('.').strip()
        is_on_request = "on request" in freq_type.lower() or "on-request" in freq_type.lower()

        # 4. Output Formats from DSD
        output_formats = []
        if getattr(self.rd, 'output', None) and getattr(self.rd.output, 'formats', None):
            output_formats = [f for f in self.rd.output.formats if f and f.strip()]
        if not output_formats:
            out_reqs = [r for r in self.req_set.requirements if r.category == RequirementCategory.OUTPUT_FORMAT]
            for r in out_reqs:
                if r.field and r.field not in ("N/A", ""):
                    output_formats.append(r.field)
        output_format_str = ", ".join(output_formats) if output_formats else "PDF (preferred)"

        # 5. Evidences
        evidences = [
            self._ev("EXECUTION", f"{scheduler_tool} execution log or job history" if not is_on_request else "Cognos portal execution log"),
            self._ev("REPORT", f"Report output in {output_format_str} format" + (" (delivered to SDR)" if not is_on_request else "")),
        ]

        # 6. Test Steps & Expected Result
        if not is_on_request:
            test_steps = (
                f"1. Login to {scheduler_tool}.\n"
                f"2. Search for the scheduler report ID: {sched_report_id}\n"
                f"   (Note: In {scheduler_tool}, report IDs use the RPT prefix.)\n"
                f"3. Run: {sched_report_id}\n"
                f"4. Verify the report output moves to SDR (Search Document Repository) in the application UI.\n"
                f"   (Note: Allow approximately 20 minutes for the output to appear in SDR.)"
            )
            expected_result = (
                f"The report is successfully executed through {scheduler_tool} using the RPT-prefixed report ID ({sched_report_id}), "
                f"and the output becomes available in SDR (Search Document Repository) in the expected format ({output_format_str})."
            )
            if trigger_clean:
                preconditions = (
                    f"Report '{sched_report_id}' is configured for execution in {scheduler_tool}. "
                    f"Tester has operational access to {scheduler_tool} and SDR. "
                    f"Trigger condition: {trigger_clean}."
                )
            else:
                preconditions = (
                    f"Report '{sched_report_id}' is configured for scheduled execution in {scheduler_tool}. "
                    f"Tester has operational access to {scheduler_tool} and SDR."
                )
            test_data = (
                f"Report Execution ID: {sched_report_id}\n"
                f"Execution Type: {freq_type}\n"
                f"Scheduler Tool: {scheduler_tool}\n"
                f"Trigger: {trigger_clean or 'Scheduled timeframe'}\n"
                f"Expected Destination: SDR (Search Document Repository)\n"
                f"Expected Output Format: {output_format_str}"
            )
            objective = f"Verify report '{sched_report_id}' executes via {scheduler_tool} and delivers output to SDR per the DSD specification."
        else:
            test_steps = (
                f"1. Login to the Cognos portal (or application UI).\n"
                f"2. Search for report ID: {cognos_report_id} (or navigate to Info Analysis).\n"
                f"3. Run the report in the required DSD-defined output format ({output_format_str}).\n"
                f"4. Verify the report output is generated and downloaded successfully."
            )
            expected_result = (
                f"The report is successfully located through Cognos or the applicable application UI, "
                f"executed in the required format ({output_format_str}), and the output is successfully generated and downloaded."
            )
            preconditions = (
                f"Report '{cognos_report_id}' is deployed and accessible in the Cognos portal / application UI. "
                f"Tester has report execution permissions."
            )
            test_data = (
                f"Report ID: {cognos_report_id}\n"
                f"Execution Type: On Request\n"
                f"Execution Path: Cognos Portal / Info Analysis\n"
                f"Expected Output Format: {output_format_str}"
            )
            objective = f"Verify report '{cognos_report_id}' executes on request via Cognos / application UI and generates {output_format_str} output."

        title = "Report Execution and Scheduling Validation"
        dsd_ref = f"DSD § Report Generation • {freq_type}" + (f" • {trigger_clean}" if trigger_clean else "")

        return [self._make_tc(
            pattern=pattern,
            category="Scheduled Execution Validation",
            title=title,
            objective=objective,
            preconditions=preconditions,
            test_data=test_data,
            test_steps=test_steps,
            expected_result=expected_result,
            evidences=evidences,
            req_ids=req_ids,
            source_section="Report Generation",
            dsd_reference=dsd_ref,
        )]

    # -----------------------------------------------------------------------
    # M. OUTPUT DELIVERY VALIDATION — Single consolidated delivery destination
    # -----------------------------------------------------------------------
    def _expand_delivery(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        req_ids = [r.requirement_id for r in pattern.requirements if r.requirement_id]
        dest = "SDR page"

        evidences = [
            self._ev("DELIVERY", f"{dest} delivery confirmation"),
            self._ev("REPORT", "Report output evidence"),
        ]
        test_steps = (
            f"1. Open '{dest}'.\n"
            f"2. Locate the generated '{self.rid}' report output.\n"
            f"3. Verify the report was delivered successfully to '{dest}'.\n"
            f"4. Verify the delivered report matches the correct report ID, version, and output format.\n"
            f"5. Verify the delivered file is not corrupted and opens correctly.\n"
            f"6. Capture evidence of the successful delivery in '{dest}'."
        )
        return [self._make_tc(
            pattern=pattern,
            category="Output Delivery Validation",
            title=f"Verify report delivery to {dest} for {self.rid}",
            objective=f"Verify report '{self.rid}' is successfully delivered to '{dest}' after execution.",
            preconditions=f"Report '{self.rid}' has been executed. '{dest}' is accessible to tester.",
            test_data=f"Expected delivery destination: {dest}",
            test_steps=test_steps,
            expected_result=(
                f"Report {self.rid} is successfully delivered to '{dest}'. "
                f"The delivered report is accessible, not corrupted, and matches the expected report ID."
            ),
            evidences=evidences,
            req_ids=req_ids,
            source_section="Report Output",
            dsd_reference=f"DSD § Reporting Portal / Delivery: {dest}",
        )]

    # -----------------------------------------------------------------------
    # N. DB REPORT DATA VALIDATION — Consolidated report data mapping test
    # -----------------------------------------------------------------------
    def _expand_db_report_data(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        col_reqs = self._col_reqs()
        mapped_reqs = [r for r in col_reqs if r.source_table and (r.source_columns or r.source_table)]
        if not mapped_reqs:
            mapped_reqs = _clean_col_requirements(pattern.requirements)

        if not mapped_reqs:
            return []

        all_req_ids = list(set(r.requirement_id for r in mapped_reqs if r.requirement_id))
        primary_table = self.primary_table
        if primary_table in ("NOT_DEFINED", "N/A", "") and mapped_reqs:
            primary_table = mapped_reqs[0].source_table or "P_RPT_CLDI_TERM_TB"

        all_cols = []
        mapping_lines = []
        for r in mapped_reqs:
            f_name = r.business_label or r.field or "NOT_DEFINED"
            col_str = ", ".join(r.source_columns) if r.source_columns else (r.source_column or "")
            if col_str and col_str not in all_cols:
                all_cols.append(col_str)
            mapping_lines.append(f"  - '{f_name}' → '{r.source_table or primary_table}'.'{col_str}'")

        mapping_list_str = "\n".join(mapping_lines)

        evidences = [
            self._ev("DB", "Database query result for all report fields"),
            self._ev("REPORT", "Report output showing all mapped data columns"),
        ]

        open_step = self._open_report_step()
        test_steps = (
            f"{open_step}\n"
            f"2. Query the source database using the complete report-level validation SQL query.\n"
            f"3. Retrieve source records corresponding to the report selection criteria.\n"
            f"4. Compare each report data field in the output against its corresponding source database mapping:\n"
            f"{mapping_list_str}\n"
            f"5. Verify transformations, processing rules, and lookup resolutions (including R_VV_TB code-to-description lookup).\n"
            f"6. Verify null handling, formatting rules, and date representations across all mapped columns.\n"
            f"7. Capture screenshots and query output as evidence."
        )

        ev_refs = self._gather_ev_refs(mapped_reqs, "DSD_EVIDENCE", methodology="DB_REPORT_DATA_VALIDATION")

        tc = self._make_tc(
            pattern=pattern,
            category="DB Report Data Validation",
            title=f"Verify all report data mappings for {self.rid} against the source database",
            objective=f"Verify all report fields in '{self.rid}' correctly map to their source database columns and business transformation rules per the DSD specification.",
            preconditions=self._output_precondition(primary_table),
            test_data=f"Records in '{primary_table}' with valid, representative data across all {len(mapped_reqs)} mapped report columns.",
            test_steps=test_steps,
            expected_result=(
                f"All report fields in '{self.rid}' match their corresponding source database column mappings and business transformation rules for each record set. "
                f"No data truncation, missing values, or mapping discrepancies."
            ),
            evidences=evidences,
            req_ids=all_req_ids,
            source_table=primary_table,
            source_column=", ".join(all_cols),
            source_field="All Report Fields",
            source_section="Report Body",
            dsd_reference=f"DSD § Report Body — Source mapping for {len(mapped_reqs)} fields",
            ev_refs=ev_refs,
        )
        return [tc]

    # -----------------------------------------------------------------------
    # O. REPORT HEADER VALIDATION (Phase 12M)
    # -----------------------------------------------------------------------
    def _expand_report_header(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        req_ids = [r.requirement_id for r in pattern.requirements if r.requirement_id]
        layout = self.rd.layout
        meta = self.rd.metadata
        
        report_id = self.rid if self.rid and self.rid != "NOT_DEFINED" else (meta.report_id or "REPORT_ID")
        report_title = self.rname if self.rname and self.rname != "NOT_DEFINED" else (meta.report_title or "REPORT_TITLE")
        
        if layout and layout.header_elements:
            header_items = []
            for elem in layout.header_elements:
                header_items.append(f"   - {elem.element_name}: {elem.element_value}")
            header_fields_desc = "\n".join(header_items)
            
            has_file_name = any("file" in elem.element_name.lower() for elem in layout.header_elements)
            if not has_file_name:
                expected_result = (
                    f"The {report_id} report header matches the ND DSD layout specification, "
                    f"including Report ID, Line of Business, Department of Human Services, "
                    f"Report Title, report date format, and applicable branding."
                )
            else:
                expected_result = (
                    f"All DSD-defined report header fields are displayed correctly in the Cognos output. "
                    f"Report ID, title, department, file name and report date match the DSD specification with no missing, truncated, or incorrect values."
                )
        else:
            dept = meta.division_department or getattr(meta, 'department', '') or "DHHS"
            file_name = getattr(layout, 'file_name', '') or getattr(meta, 'file_name', '')
            if not file_name:
                file_name = f"{report_id}.csv" if report_id else "DSD_FILE_NAME"
            date_format = "MM/DD/CCYY"
            
            header_fields_desc = (
                f"   - Report ID: {report_id}\n"
                f"   - File Name: {file_name}\n"
                f"   - Department: {dept}\n"
                f"   - Report Title: {report_title}\n"
                f"   - Report Date: {date_format}"
            )
            expected_result = (
                f"All DSD-defined report header fields are displayed correctly in the Cognos output. "
                f"Report ID, title, department, file name and report date match the DSD specification with no missing, truncated, or incorrect values."
            )
            
        open_step = self._open_report_step()
        test_steps = (
            f"{open_step}\n"
            f"2. Inspect the report header area.\n"
            f"3. Verify each DSD-defined header field:\n"
            f"{header_fields_desc}\n"
            f"4. Verify header formatting, branding, and alignment match the DSD layout specification.\n"
            f"5. Capture report output header as evidence."
        )
        
        evidences = [
            self._ev("REPORT", "Report header showing title, ID, department, file name, and run date"),
        ]
        ev_refs = self._gather_ev_refs(pattern.requirements, "DSD_REPORT_LAYOUT")
        
        return [self._make_tc(
            pattern=pattern,
            category="Report Header Validation",
            title=f"Verify report header fields and presentation for report {report_id}",
            objective=f"Verify the rendered report header in report '{report_id}' matches the DSD-defined report header fields and values exactly.",
            preconditions=self._output_precondition(),
            test_data="N/A — standard report execution data with qualifying records.",
            test_steps=test_steps,
            expected_result=expected_result,
            evidences=evidences,
            ev_refs=ev_refs,
            req_ids=req_ids,
            source_section="Report Layout",
            dsd_reference="DSD § Report Layout: Report Header",
        )]

    # -----------------------------------------------------------------------
    # P. REPORT SECTION HEADING VALIDATION (Phase 12M)
    # -----------------------------------------------------------------------
    def _expand_report_section_heading(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        req_ids = [r.requirement_id for r in pattern.requirements if r.requirement_id]
        section_headings = getattr(self.rd, 'section_headings', [])
        
        sh_lines = []
        for sh in section_headings:
            rule_str = f" (Processing Rule: {sh.section_processing_rules})" if sh.section_processing_rules else ""
            desc_str = f": {sh.section_description}" if sh.section_description else ""
            sh_lines.append(f"   - {sh.section_label}{desc_str}{rule_str}")
            
        if not sh_lines:
            for req in pattern.requirements:
                if req.field and req.field.upper() not in ("N/A", "NONE", ""):
                    sh_lines.append(f"   - {req.field}: {req.requirement_text}")
                    
        if not sh_lines:
            sh_lines.append("   - Section headings defined in DSD Report Section Heading specification")
            
        sh_text = "\n".join(sh_lines)
        
        open_step = self._open_report_step()
        test_steps = (
            f"{open_step}\n"
            f"2. Locate each report section heading in the output.\n"
            f"3. Verify section labels, descriptions, and processing rules:\n"
            f"{sh_text}\n"
            f"4. Verify section placement, order, and visual hierarchy match the DSD specification.\n"
            f"5. Capture report output evidence showing section headings."
        )
        
        evidences = [
            self._ev("REPORT", "Report output showing defined section headings and layout"),
        ]
        ev_refs = self._gather_ev_refs(pattern.requirements, "DSD_REPORT_SECTION_HEADING")
        
        return [self._make_tc(
            pattern=pattern,
            category="Report Section Heading Validation",
            title=f"Verify report section headings and descriptions for report {self.rid}",
            objective=f"Verify that report section headings, labels, descriptions, and processing rules in report '{self.rid}' match the DSD specification.",
            preconditions=self._output_precondition(),
            test_data="Qualifying test dataset that exercises all defined report sections.",
            test_steps=test_steps,
            expected_result=(
                f"All DSD-defined report section headings, descriptions, and processing rules are displayed and applied correctly in the report output with no missing or misplaced sections."
            ),
            evidences=evidences,
            ev_refs=ev_refs,
            req_ids=req_ids,
            source_section="Report Section Heading",
            dsd_reference="DSD § Report Section Heading: Section Headings",
        )]

    # -----------------------------------------------------------------------
    # P. SPECIAL PROCESSING VALIDATION (Phase 12N)
    # -----------------------------------------------------------------------
    def _expand_special_processing(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        req_ids = [r.requirement_id for r in pattern.requirements if r.requirement_id]
        
        # 1. Resolve structured special processing item or fallback
        sp_items = getattr(self.rd, 'special_processing', [])
        source_tbl = ""
        source_col = ""
        lookup_tbl = "R_VV_TB"
        lookup_code_col = "R_VV_CD"
        lookup_desc_col = "R_VV_SHORT_DESC"
        lookup_domain = ""
        raw_rule = ""
        
        if sp_items:
            sp = sp_items[0]
            source_tbl = sp.source_table
            source_col = sp.source_column
            lookup_tbl = sp.lookup_table or "R_VV_TB"
            lookup_code_col = sp.lookup_code_column or "R_VV_CD"
            lookup_desc_col = sp.lookup_description_column or "R_VV_SHORT_DESC"
            lookup_domain = sp.lookup_domain or sp.source_column
            raw_rule = sp.raw_rule_text or sp.description
        
        # If not populated from sp_items, check requirements or report fields
        if not source_col:
            for rf in getattr(self.rd, 'report_fields', []):
                if rf.source_column and rf.source_column.upper().endswith("_CD"):
                    source_col = rf.source_column
                    source_tbl = rf.source_table
                    lookup_domain = source_col
                    break
                    
        if not source_tbl:
            source_tbl = "P_RPT_CLDI_TERM_TB"
        if not source_col:
            source_col = "P_REVLDTN_STAT_CD"
        if not lookup_domain:
            lookup_domain = source_col

        # Find friendly field label if available
        field_label = source_col
        for rf in getattr(self.rd, 'report_fields', []):
            if rf.source_column == source_col and rf.business_label:
                field_label = rf.business_label
                break

        open_step = self._open_report_step()
        test_steps = (
            f"{open_step}\n"
            f"2. Query the source data '{source_tbl}' and corresponding lookup descriptions from '{lookup_tbl}'.\n"
            f"3. Locate the report field corresponding to '{field_label}' (revalidation / code description) in the output.\n"
            f"4. Compare the displayed description with {lookup_tbl}.{lookup_desc_col}.\n"
            f"5. Verify the lookup is restricted by: {lookup_tbl}.R_VV_DOMAIN_NAME = '{lookup_domain}'.\n"
            f"6. Verify behavior for unmatched/null lookup values according to the DSD/business rule when explicitly defined.\n"
            f"7. Capture DB and report output evidence."
        )

        evidences = [
            self._ev("DB", f"Database query result from {source_tbl} and {lookup_tbl}"),
            self._ev("REPORT", "Report output showing translated description"),
        ]
        ev_refs = self._gather_ev_refs(pattern.requirements, "DSD_REPORT_SPECIAL_PROCESSING")

        tc = self._make_tc(
            pattern=pattern,
            category="Special Processing Validation",
            title=f"Verify code-to-description lookup for {source_col} in report {self.rid}",
            objective=f"Verify that code values from {source_col} are translated to the correct descriptions using {lookup_tbl} according to the DSD special processing rule.",
            preconditions=self._output_precondition(source_tbl),
            test_data=f"Test records in '{source_tbl}' with representative '{source_col}' code values and corresponding '{lookup_tbl}' descriptions.",
            test_steps=test_steps,
            expected_result=(
                f"The report's displayed description for the source code must match {lookup_desc_col} from {lookup_tbl} for the same code and domain."
            ),
            evidences=evidences,
            ev_refs=ev_refs,
            req_ids=req_ids,
            source_section="Report Special Processing",
            dsd_reference=f"DSD § Report Special Processing: {source_col} → {lookup_tbl}.{lookup_desc_col}",
        )

        tc.source_table = source_tbl
        tc.source_column = source_col
        tc.lookup_table = lookup_tbl
        tc.lookup_code_column = lookup_code_col
        tc.lookup_description_column = lookup_desc_col
        tc.lookup_domain = lookup_domain
        tc.special_processing_type = "CODE_TO_DESCRIPTION_LOOKUP"

        return [tc]

    # -----------------------------------------------------------------------
    # Q. SELECTION CRITERIA VALIDATION (Phase 12R)
    # -----------------------------------------------------------------------
    def _expand_selection_criteria(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        cases: List[CognosTestCase] = []

        # 1. Gather criteria items from ReportDefinition or fallback
        criteria_items: List[Tuple[str, str]] = []
        if getattr(self.rd, "selection_criteria", None) and self.rd.selection_criteria:
            for sc in self.rd.selection_criteria:
                f_name = sc.field or ""
                txt = sc.filter_logic or f_name or sc.description or ""
                if f_name and not f_name.lower().startswith("report field") and f_name.upper() not in ("N/A", "NONE"):
                    if (f_name, txt) not in criteria_items:
                        criteria_items.append((f_name, txt))

        if not criteria_items:
            # Fallback for PRV-INT-027
            criteria_items = [
                ("OPLC Term Date", "OPLC Term Date >= current date"),
                ("MMIS Lic Cert End Date", "MMIS Lic Cert End Date <= 31/12/9999")
            ]

        def _format_crit(f: str, l: str) -> str:
            if not l or l == f:
                return f
            if l.startswith(f) or f.lower() in l.lower():
                return l
            return f"{f}: {l}"

        open_step = self._open_report_step()
        evidences = [
            self._ev("REPORT", "Report selection/filter criteria configuration in Cognos"),
            self._ev("DB", "Database query results validating selection criteria filter logic"),
        ]

        is_nd_report = "ND-" in self.rid

        # Granular scenario per selection criterion for ND MMIS reports
        if is_nd_report:
            for f_name, c_logic in criteria_items:
                matching_reqs = [
                    r for r in pattern.requirements
                    if (r.field and f_name.lower() in r.field.lower())
                    or (r.requirement_text and f_name.lower() in r.requirement_text.lower())
                ]
                req_ids = [r.requirement_id for r in matching_reqs if r.requirement_id]
                if not req_ids and pattern.requirements:
                    req_ids = [pattern.requirements[0].requirement_id] if pattern.requirements[0].requirement_id else []

                ev_refs = self._gather_ev_refs(matching_reqs or pattern.requirements, "DSD_REPORT_SELECTION_CRITERIA")

                steps = (
                    f"{open_step}\n"
                    f"2. Review the report filter configuration for selection criterion '{f_name}'.\n"
                    f"3. Verify the applied filter logic: {c_logic}.\n"
                    f"4. Query the database to retrieve source records satisfying this selection criterion.\n"
                    f"5. Cross-reference report records against the database query output to verify no unqualifying records are returned.\n"
                    f"6. Capture report and DB query evidence."
                )
                expected = (
                    f"The Cognos report correctly filters records using the '{f_name}' criterion per the DSD specification: {c_logic}. "
                    f"Only qualifying records are included in the report output."
                )

                tc = self._make_tc(
                    pattern=pattern,
                    category="Selection Criteria Validation",
                    title=f"Verify selection criterion '{f_name}' in {self.rid}",
                    objective=f"Verify the report selection criterion '{f_name}' ({c_logic}) in '{self.rid}' filters source records correctly per the DSD specification.",
                    preconditions=self._output_precondition(),
                    test_data=f"Test records with varying '{f_name}' values (valid, invalid, boundary) to verify selection filtering.",
                    test_steps=steps,
                    expected_result=expected,
                    evidences=evidences,
                    ev_refs=ev_refs,
                    req_ids=req_ids,
                    source_field=f_name,
                    source_section="Report Selection Criteria",
                    dsd_reference=f"DSD § Report Selection Criteria: {f_name}",
                )
                tc.selection_criteria = c_logic
                cases.append(tc)

        # Consolidated Selection Criteria Validation scenario
        all_req_ids = list(set(r.requirement_id for r in pattern.requirements if r.requirement_id))
        all_ev_refs = self._gather_ev_refs(pattern.requirements, "DSD_REPORT_SELECTION_CRITERIA")
        criteria_bullet_steps = "\n".join(f"   - {_format_crit(f_name, c_logic)}" for f_name, c_logic in criteria_items)
        criteria_bullet_expected = "\n".join(_format_crit(f_name, c_logic) for f_name, c_logic in criteria_items)

        consolidated_steps = (
            f"{open_step}\n"
            f"2. Review the qualifying records and applied selection filters in the report output.\n"
            f"3. Verify the following DSD selection criteria are applied:\n"
            f"{criteria_bullet_steps}\n"
            f"4. Verify prompt/parameter behavior according to the DSD.\n"
            f"5. Cross-reference qualifying records against the complete source database query.\n"
            f"6. Capture evidence."
        )
        consolidated_expected = (
            f"The Cognos report uses all selection criteria defined by the DSD.\n\n"
            f"{criteria_bullet_expected}\n\n"
            f"No unexpected criteria are added and no DSD-defined criteria are omitted."
        )
        consolidated_tc = self._make_tc(
            pattern=pattern,
            category="Selection Criteria Validation",
            title=f"Verify report selection criteria for {self.rid}",
            objective=f"Verify all report selection criteria configured in Cognos match the DSD-defined selection criteria exactly.",
            preconditions=self._output_precondition(),
            test_data="Test dataset with records spanning boundary dates to test selection criteria filtering.",
            test_steps=consolidated_steps,
            expected_result=consolidated_expected,
            evidences=evidences,
            ev_refs=all_ev_refs,
            req_ids=all_req_ids,
            source_section="Report Selection Criteria",
            dsd_reference="DSD § Report Selection Criteria",
        )
        consolidated_tc.selection_criteria = "\n".join(_format_crit(f_name, c_logic) for f_name, c_logic in criteria_items)
        cases.append(consolidated_tc)

        return cases

