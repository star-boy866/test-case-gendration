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

from typing import List, Optional, Any
from dataclasses import dataclass, field

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
        processing_rule: str = "",
        formatting_rule: str = "",
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
            processing_rule=processing_rule,
            formatting_rule=formatting_rule,
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

    def expand(self, patterns: List[ApplicablePattern]) -> List[CognosTestCase]:
        """Expand all applicable patterns into granular test scenarios."""
        cases: List[CognosTestCase] = []
        for pattern in patterns:
            expander = self._get_expander(pattern.pattern)
            if expander:
                cases.extend(expander(pattern))
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

        test_steps = (
            f"1. Generate report {self.rid} and open in Cognos viewer.\n"
            f"2. Verify the report uses '{presentation}' presentation type (as specified in DSD).\n"
            f"3. Verify the report header contains the correct elements: {header_elements or 'per DSD layout specification'}.\n"
            f"4. Verify the report footer (if applicable) contains run date, page number, and run time.\n"
            f"5. Verify report title line matches the DSD layout exactly.\n"
            f"6. Capture full-page screenshot as evidence."
        )
        return [self._make_tc(
            pattern=pattern,
            category="Layout Validation",
            title=f"Verify report layout and presentation for {self.rid}",
            objective=f"Verify the report '{self.rid}' layout, header structure, and presentation type match the DSD layout specification.",
            preconditions=self._base_precondition(),
            test_data="N/A — layout verification is structural, no specific data required.",
            test_steps=test_steps,
            expected_result=(
                f"Report layout matches the DSD specification. "
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
        test_steps = (
            f"1. Generate report {self.rid} with qualifying data.\n"
            f"2. Open the report output and inspect all column header labels.\n"
            f"3. For each column, compare the report label against the DSD Business Label:\n"
            f"{label_list}\n"
            f"4. Verify exact label text (case-sensitive, no extra spaces).\n"
            f"5. Capture a screenshot showing all column headers as evidence."
        )
        return [self._make_tc(
            pattern=pattern,
            category="Label Validation",
            title=f"Verify all report body column labels for {self.rid}",
            objective=f"Verify every report body column header label in '{self.rid}' matches the DSD Business Label specification exactly.",
            preconditions=self._base_precondition(self.primary_table),
            test_data=f"Report with qualifying records to display all {len(labels)} columns.",
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
    # C. SORT VALIDATION — One test per explicit Sort By entry
    # -----------------------------------------------------------------------
    def _expand_sorts(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        cases = []
        sort_reqs = [r for r in self.req_set.requirements if r.category == RequirementCategory.SORT]

        if not sort_reqs:
            # Fallback: use pattern requirements
            sort_reqs = [r for r in pattern.requirements if r.category == RequirementCategory.SORT]

        # Deduplicate by field
        seen_fields = set()
        unique_sort_reqs = []
        for r in sort_reqs:
            key = (r.field or r.business_label or "").lower().strip()
            if key and key not in seen_fields:
                seen_fields.add(key)
                unique_sort_reqs.append(r)

        evidences = [
            self._ev("REPORT", "Report output showing record ordering"),
        ]

        for req in unique_sort_reqs:
            field_name = req.field or req.business_label or "NOT_DEFINED"
            direction = req.processing_rule or "Ascending"
            src_table = req.source_table or self.primary_table

            test_steps = (
                f"1. Load test records into '{src_table}' with multiple distinct values for '{field_name}'.\n"
                f"2. Execute report {self.rid} in Cognos.\n"
                f"3. Inspect the ordering of all records in the output.\n"
                f"4. Verify that records are sorted by '{field_name}' in {direction} order.\n"
                f"5. Verify that when '{field_name}' values are equal, the secondary sort (if defined) applies.\n"
                f"6. Capture a screenshot of the ordered output as evidence."
            )
            cases.append(self._make_tc(
                pattern=pattern,
                category="Sort Validation",
                title=f"Verify sort order by '{field_name}' ({direction}) for {self.rid}",
                objective=f"Verify report '{self.rid}' records are sorted by '{field_name}' in {direction} order as specified in the DSD.",
                preconditions=self._base_precondition(src_table),
                test_data=f"Records in '{src_table}' with multiple distinct '{field_name}' values to verify ordering.",
                test_steps=test_steps,
                expected_result=f"All records in report {self.rid} are sorted by '{field_name}' in {direction} order. Identical '{field_name}' values are handled per the secondary sort rule.",
                evidences=evidences,
                req_ids=[req.requirement_id] if req.requirement_id else [],
                source_table=src_table,
                source_column=field_name,
                source_section="Report Control Breaks, Totals, Counts, and Sorts",
                dsd_reference=f"DSD § Sort By: {field_name} ({direction})",
                ev_refs=self._gather_ev_refs([req], "DSD_EVIDENCE"),
            ))

        if not cases:
            # Generic fallback when no sort requirements mapped
            evidences_fb = [self._ev("REPORT", "Report output showing record ordering")]
            cases.append(self._make_tc(
                pattern=pattern,
                category="Sort Validation",
                title=f"Verify report data sort order for {self.rid}",
                objective=f"Verify report '{self.rid}' records are sorted as specified in the DSD.",
                preconditions=self._base_precondition(),
                test_data="Records with varied sort key values.",
                test_steps=(
                    f"1. Execute report {self.rid}.\n"
                    f"2. Inspect the ordering of all records.\n"
                    f"3. Verify sort order matches all DSD-specified sort keys.\n"
                    f"4. Capture screenshot as evidence."
                ),
                expected_result="Records are sorted correctly according to the DSD.",
                evidences=evidences_fb,
                req_ids=[],
                source_section="Report Control Breaks, Totals, Counts, and Sorts",
            ))
        return cases

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
        cases.append(self._make_tc(
            pattern=pattern,
            category="Script Output Validation",
            title=f"Verify report output format for {self.rid}",
            objective=f"Verify report '{self.rid}' generates output in the DSD-specified format ({format_str}).",
            preconditions=self._base_precondition(),
            test_data=f"Expected output format: {format_str}",
            test_steps=(
                f"1. Execute report {self.rid} in Cognos.\n"
                f"2. Locate the generated output file.\n"
                f"3. Verify the file format is '{format_str}'.\n"
                f"4. Open the output and confirm it renders correctly without corruption.\n"
                f"5. Capture screenshot of successful download/output as evidence."
            ),
            expected_result=f"Report {self.rid} generates a valid '{format_str}' output file without errors.",
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
                preconditions=self._base_precondition(),
                test_data=f"Expected retention type: {ret_type}",
                test_steps=(
                    f"1. Execute report {self.rid}.\n"
                    f"2. Navigate to the report run history or EDMS/Cognos storage.\n"
                    f"3. Verify the report instance is stored under '{ret_type}'.\n"
                    f"4. Verify retention duration matches the DSD specification.\n"
                    f"5. Capture evidence of the stored report instance."
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
        test_steps = (
            f"1. Log into the Cognos portal.\n"
            f"2. Navigate to the folder containing report '{report_id}'.\n"
            f"3. Open report properties / report header.\n"
            f"4. Verify Report ID is: '{report_id}'.\n"
            f"5. Verify Report Title is: '{title}'.\n"
            f"6. Verify Report Description matches: '{desc[:80]}...' (see DSD).\n"
            f"7. Verify Generated By: '{generated_by}'.\n"
            f"8. Capture screenshot of report properties as evidence."
        )
        return [self._make_tc(
            pattern=pattern,
            category="Report Name Description Validation",
            title=f"Verify report ID, title, and description for {report_id}",
            objective=f"Verify report metadata (ID, Title, Description, Generated By) for '{report_id}' matches the DSD specification exactly.",
            preconditions=self._base_precondition(),
            test_data=f"Expected Report ID: {report_id}\nExpected Title: {title}\nExpected Description: {desc[:120]}",
            test_steps=test_steps,
            expected_result=(
                f"Cognos portal shows Report ID '{report_id}', "
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
        # Find COLUMN requirements with date formatting
        col_reqs = self._col_reqs()
        date_reqs = [
            r for r in col_reqs
            if r.formatting_rule and ("date" in r.formatting_rule.lower() or "mm/" in r.formatting_rule.lower())
            or r.processing_rule and ("date" in r.processing_rule.lower() or "mm/" in r.processing_rule.lower() or "format" in r.processing_rule.lower())
        ]

        if not date_reqs:
            date_reqs = [r for r in pattern.requirements if r.category in (RequirementCategory.COLUMN_FORMAT, RequirementCategory.COLUMN)]
            date_reqs = _clean_col_requirements(date_reqs)

        evidences = [
            self._ev("REPORT", "Report screenshot showing date column"),
            self._ev("DB", "Source database date value for comparison"),
        ]

        for req in date_reqs:
            field_name = req.business_label or req.field or "NOT_DEFINED"
            proc_rule = req.processing_rule or req.formatting_rule or ""
            date_fmt = _get_date_format_from_rule(proc_rule) or "MM/DD/YYYY"
            src_table = req.source_table or self.primary_table
            src_col = (req.source_columns[0] if req.source_columns else "") or req.source_column or "NOT_DEFINED"

            test_steps = (
                f"1. Query source table '{src_table}' for test records with known '{src_col}' date values.\n"
                f"2. Note the raw date values from the database (source format).\n"
                f"3. Execute report {self.rid} in Cognos.\n"
                f"4. Locate column '{field_name}' in the report output.\n"
                f"5. Verify each date value is displayed in '{date_fmt}' format.\n"
                f"6. Cross-check: report date matches the corresponding '{src_col}' database value.\n"
                f"7. Test boundary dates (first/last of month, leap year if applicable).\n"
                f"8. Capture screenshot of the formatted date column as evidence."
            )
            cases.append(self._make_tc(
                pattern=pattern,
                category="Date Format Validation",
                title=f"Verify date format '{date_fmt}' for '{field_name}' in {self.rid}",
                objective=f"Verify column '{field_name}' in report '{self.rid}' displays dates in '{date_fmt}' format as specified in the DSD processing rules.",
                preconditions=self._base_precondition(src_table),
                test_data=f"Records in '{src_table}' with known '{src_col}' date values including boundary dates.",
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
                preconditions=self._base_precondition(self.primary_table),
                test_data="Records with known date values.",
                test_steps=(
                    f"1. Execute report {self.rid}.\n"
                    f"2. Inspect all date columns.\n"
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

        def build_cb_test(req, break_type_label):
            field_name = req.field or req.business_label or "NOT_DEFINED"
            src_table = req.source_table or self.primary_table

            test_steps = (
                f"1. Load test records into '{src_table}' with multiple distinct '{field_name}' values.\n"
                f"2. Execute report {self.rid} in Cognos.\n"
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
                preconditions=self._base_precondition(src_table),
                test_data=f"Records in '{src_table}' with at least 3 distinct '{field_name}' values spanning multiple {break_type_label.lower()} breaks.",
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
                preconditions=self._base_precondition(),
                test_data="Records spanning multiple control break values.",
                test_steps=(
                    f"1. Execute report {self.rid}.\n"
                    f"2. Review the boundaries between groups.\n"
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

        for req in count_reqs:
            field_name = req.field or req.business_label or "NOT_DEFINED"
            count_type = "Count" if req.category == RequirementCategory.COUNT else "Total"
            src_table = req.source_table or self.primary_table
            src_col = (req.source_columns[0] if req.source_columns else "") or ""

            sql_hint = ""
            if src_table and src_table != "NOT_DEFINED":
                if src_col:
                    sql_hint = f"\n   SQL: SELECT COUNT({src_col}) FROM {src_table} WHERE <selection_criteria>;"
                else:
                    sql_hint = f"\n   SQL: SELECT COUNT(*) FROM {src_table} WHERE <selection_criteria>;"

            test_steps = (
                f"1. Execute the following SQL against the source database to get expected {count_type.lower()}:{sql_hint}\n"
                f"2. Note the database {count_type.lower()} result for '{field_name}'.\n"
                f"3. Execute report {self.rid} in Cognos with the same selection criteria.\n"
                f"4. Locate the '{field_name}' {count_type.lower()} in the report output.\n"
                f"5. Compare: report {count_type.lower()} must equal the database {count_type.lower()}.\n"
                f"6. Capture screenshots of both the DB query and the report output as evidence."
            )
            cases.append(self._make_tc(
                pattern=pattern,
                category="DB Count Validation",
                title=f"Verify '{field_name}' {count_type} in {self.rid} matches database",
                objective=f"Verify the '{field_name}' {count_type.lower()} in report '{self.rid}' matches the database {count_type.lower()} for the same record set.",
                preconditions=self._base_precondition(src_table),
                test_data=f"Known set of records in '{src_table}' with a predictable {count_type.lower()} for '{field_name}'.",
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
                dsd_reference=f"DSD § {count_type}: {field_name}",
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
                preconditions=self._base_precondition(self.primary_table),
                test_data="Known set of records with predictable count.",
                test_steps=(
                    f"1. Run an aggregate SQL query on the source database.\n"
                    f"2. Execute report {self.rid}.\n"
                    f"3. Compare database count against report total.\n"
                    f"4. Capture both as evidence."
                ),
                expected_result="Database count matches report total exactly.",
                evidences=evidences_fb,
                req_ids=[],
                source_section="Report Control Breaks, Totals, Counts, and Sorts",
            ))

        return cases

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

        test_steps = (
            f"1. Identify records in '{src_table}' that could produce duplicates "
            f"(e.g., multiple rows with the same {pk_str}).\n"
            f"2. Execute the following SQL to check for potential duplicate combinations:\n"
            f"   SELECT {pk_str}, COUNT(*) cnt FROM {src_table} "
            f"WHERE <selection_criteria> GROUP BY {pk_str} HAVING cnt > 1;\n"
            f"3. Generate report {self.rid} in Cognos.\n"
            f"4. Verify the report does NOT display duplicate rows for the same record.\n"
            f"5. Cross-reference report row count against expected DISTINCT record count in database.\n"
            f"6. Capture evidence of both the DB query and the report output."
        )
        return [self._make_tc(
            pattern=pattern,
            category="Duplicate Validation",
            title=f"Verify no duplicate records in {self.rid}",
            objective=f"Verify report '{self.rid}' suppresses duplicate records and displays only distinct records.",
            preconditions=self._base_precondition(src_table),
            test_data=f"Database setup with potential duplicate rows in '{src_table}' to verify deduplication logic.",
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
            or ("description" in (r.requirement_text or "").lower() and r.category in (RequirementCategory.COLUMN_LOGIC, RequirementCategory.COLUMN))
        ]

        if not lookup_reqs:
            lookup_reqs = [r for r in pattern.requirements if not _is_template_placeholder(r.field or r.business_label or "")]

        evidences = [
            self._ev("DB", "Source table and lookup table query results"),
            self._ev("REPORT", "Report output showing resolved description"),
        ]

        for req in lookup_reqs:
            field_name = req.business_label or req.field or "NOT_DEFINED"
            src_table = req.source_table or self.primary_table
            src_col = (req.source_columns[0] if req.source_columns else "") or req.source_column or "NOT_DEFINED"
            proc = req.processing_rule or req.description or ""

            # Extract lookup table hint if available
            import re
            lookup_table_match = re.search(r'[A-Z][_A-Z0-9]+_TB\b', proc)
            lookup_table = lookup_table_match.group(0) if lookup_table_match else "lookup table"

            test_steps = (
                f"1. Query source table '{src_table}' for test records with '{src_col}' code values.\n"
                f"2. Note the code values (e.g., '01', 'A', etc.) from the database.\n"
                f"3. Query the lookup table '{lookup_table}' for the expected descriptions for each code.\n"
                f"4. Execute report {self.rid} in Cognos.\n"
                f"5. Locate column '{field_name}' in the report output.\n"
                f"6. Verify that each code has been resolved to its correct description.\n"
                f"7. Verify unknown/null codes display appropriately (per business rules).\n"
                f"8. Capture screenshots of DB codes, lookup table, and report output."
            )
            cases.append(self._make_tc(
                pattern=pattern,
                category="Lookup Validation",
                title=f"Verify lookup/code resolution for '{field_name}' in {self.rid}",
                objective=f"Verify column '{field_name}' in report '{self.rid}' correctly resolves code values to descriptions via '{lookup_table}'.",
                preconditions=self._base_precondition(src_table),
                test_data=f"Records in '{src_table}' with known '{src_col}' code values that have corresponding descriptions in '{lookup_table}'.",
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
                processing_rule=proc,
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
                preconditions=self._base_precondition(self.primary_table),
                test_data="Records with code values that require lookup resolution.",
                test_steps=(
                    f"1. Query source table for records with code values.\n"
                    f"2. Query lookup table for expected descriptions.\n"
                    f"3. Execute report {self.rid}.\n"
                    f"4. Verify codes are resolved correctly.\n"
                    f"5. Capture evidence."
                ),
                expected_result="All code values are resolved to correct descriptions.",
                evidences=evidences_fb,
                req_ids=[],
                source_section="Report Body",
            ))

        return cases

    # -----------------------------------------------------------------------
    # L. SCHEDULED EXECUTION VALIDATION
    # -----------------------------------------------------------------------
    def _expand_scheduled(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        req_ids = [r.requirement_id for r in pattern.requirements if r.requirement_id]

        # Determine scheduling tool from evidence
        reason = pattern.applicable_reason.lower()
        req_texts = " ".join(r.requirement_text.lower() for r in pattern.requirements)
        combined = reason + " " + req_texts

        if "box" in combined:
            tool = "Box"
        elif "scheduler" in combined:
            tool = "Cognos Scheduler"
        else:
            tool = "Scheduler"

        # Extract frequency from requirements
        freq_reqs = [r for r in self.req_set.requirements if r.category == RequirementCategory.REPORT_FREQUENCY]
        freq_text = freq_reqs[0].requirement_text if freq_reqs else "per DSD frequency specification"

        evidences = [
            self._ev("EXECUTION", f"{tool} execution log or job history"),
            self._ev("REPORT", "Generated report instance evidence"),
        ]
        test_steps = (
            f"1. Log into the {tool} job scheduler.\n"
            f"2. Navigate to the scheduled job for report '{self.rid}'.\n"
            f"3. Verify the job is configured per the DSD frequency: {freq_text}.\n"
            f"4. Trigger or wait for the scheduled execution.\n"
            f"5. Verify the job completes successfully (exit code 0 / SUCCESS status).\n"
            f"6. Verify the output report instance was generated and stored correctly.\n"
            f"7. Capture the {tool} execution log and report output as evidence."
        )
        return [self._make_tc(
            pattern=pattern,
            category="Scheduled Execution Validation",
            title=f"Verify scheduled execution of {self.rid} via {tool}",
            objective=f"Verify report '{self.rid}' executes successfully on schedule via {tool}.",
            preconditions=f"Report '{self.rid}' is configured in {tool}. Scheduled job is active and accessible.",
            test_data=f"Expected frequency: {freq_text}",
            test_steps=test_steps,
            expected_result=(
                f"Report {self.rid} executes successfully via {tool}. "
                f"Job completes without error. "
                f"Report instance is generated and available for download."
            ),
            evidences=evidences,
            req_ids=req_ids,
            source_section="Report Generation",
            dsd_reference=f"DSD § Report Generation: {freq_text}",
        )]

    # -----------------------------------------------------------------------
    # M. OUTPUT DELIVERY VALIDATION — Per delivery destination
    # -----------------------------------------------------------------------
    def _expand_delivery(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        req_ids = [r.requirement_id for r in pattern.requirements if r.requirement_id]
        req_texts = " ".join(r.requirement_text.lower() for r in pattern.requirements)
        reason = pattern.applicable_reason.lower()
        combined = reason + " " + req_texts

        # Determine delivery destinations from evidence
        destinations = []
        if "edms" in combined:
            destinations.append("EDMS")
        if "sdr" in combined:
            destinations.append("SDR")
        if "web portal" in combined or "reporting portal" in combined or "web" in combined:
            destinations.append("Web Portal / Reporting Portal")
        if not destinations:
            destinations.append("Delivery Destination")

        cases = []
        for dest in destinations:
            evidences = [
                self._ev("DELIVERY", f"{dest} delivery confirmation"),
                self._ev("REPORT", "Report output evidence"),
            ]
            test_steps = (
                f"1. Execute report {self.rid} in Cognos.\n"
                f"2. Navigate to '{dest}' and search for the report output.\n"
                f"3. Verify the report was delivered successfully to '{dest}'.\n"
                f"4. Verify the delivered report is the correct version and report ID.\n"
                f"5. Verify the delivered file is not corrupted and opens correctly.\n"
                f"6. Capture evidence of the successful delivery in '{dest}'."
            )
            cases.append(self._make_tc(
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
            ))

        return cases

    # -----------------------------------------------------------------------
    # N. DB REPORT DATA VALIDATION — Per-field mapping test
    # -----------------------------------------------------------------------
    def _expand_db_report_data(self, pattern: ApplicablePattern) -> List[CognosTestCase]:
        cases = []
        col_reqs = self._col_reqs()
        # Only include fields with actual source mappings
        mapped_reqs = [r for r in col_reqs if r.source_table and (r.source_columns or r.source_table)]

        if not mapped_reqs:
            mapped_reqs = _clean_col_requirements(pattern.requirements)

        evidences = [
            self._ev("DB", "Database query result for the field"),
            self._ev("REPORT", "Report output showing the field value"),
        ]

        for req in mapped_reqs:
            field_name = req.business_label or req.field or "NOT_DEFINED"
            src_table = req.source_table or self.primary_table
            src_cols = req.source_columns if req.source_columns else []
            src_col_str = ", ".join(src_cols) if src_cols else "NOT_DEFINED"
            proc_rule = req.processing_rule or ""
            field_desc = req.description or ""

            sql_hint = f"SELECT {src_col_str} FROM {src_table} WHERE <selection_criteria>;"
            step5_proc = f"\n5. Verify processing rule: {proc_rule}." if proc_rule else ""
            step6 = 6 if proc_rule else 5

            test_steps = (
                f"1. Query the source database:\n   {sql_hint}\n"
                f"2. Note the '{src_col_str}' values for a representative set of test records.\n"
                f"3. Execute report {self.rid} in Cognos.\n"
                f"4. Locate column '{field_name}' in the report output."
                f"{step5_proc}\n"
                f"{step6}. Compare each report value against the corresponding '{src_col_str}' database value.\n"
                f"{step6+1}. Verify null handling: null database values display per business rules (blank or N/A).\n"
                f"{step6+2}. Capture screenshots of both the DB query and report column as evidence."
            )
            cases.append(self._make_tc(
                pattern=pattern,
                category="DB Report Data Validation",
                title=f"Verify DB mapping for '{field_name}' ({src_col_str}) in {self.rid}",
                objective=(
                    f"Verify report '{self.rid}' column '{field_name}' correctly maps to "
                    f"'{src_table}'.'{src_col_str}'. "
                    f"{('Field: ' + field_desc) if field_desc else ''}"
                ).strip(),
                preconditions=self._base_precondition(src_table),
                test_data=f"Records in '{src_table}' with known '{src_col_str}' values.",
                test_steps=test_steps,
                expected_result=(
                    f"Report '{self.rid}' column '{field_name}' displays values that exactly match "
                    f"'{src_table}'.'{src_col_str}' for each record. "
                    f"No transformation errors, no missing values, no data truncation."
                ),
                evidences=evidences,
                req_ids=[req.requirement_id] if req.requirement_id else [],
                source_table=src_table,
                source_column=src_col_str,
                processing_rule=proc_rule,
                source_section="Report Body",
                dsd_reference=f"DSD § Report Body: {field_name} → {src_table}.{src_col_str}",
                ev_refs=self._gather_ev_refs([req], "DSD_EVIDENCE"),
            ))

        if not cases:
            evidences_fb = [
                self._ev("DB", "Database query result"),
                self._ev("REPORT", "Report output"),
            ]
            cases.append(self._make_tc(
                pattern=pattern,
                category="DB Report Data Validation",
                title=f"Verify DB-to-report data mapping for {self.rid}",
                objective=f"Verify all report fields in '{self.rid}' correctly map to their source database columns.",
                preconditions=self._base_precondition(self.primary_table),
                test_data=f"Records in '{self.primary_table}' with known values.",
                test_steps=(
                    f"1. Query source database for test records.\n"
                    f"2. Execute report {self.rid}.\n"
                    f"3. Compare all column values against DB values.\n"
                    f"4. Capture evidence."
                ),
                expected_result="All report column values match the source database values exactly.",
                evidences=evidences_fb,
                req_ids=[],
                source_section="Report Body",
            ))

        return cases
