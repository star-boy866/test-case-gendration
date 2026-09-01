"""
North Dakota MMIS Requirement Builder.

Constructs canonical CognosRequirement models and builds a comprehensive
RequirementSet from an NdMmisDsd AST.
"""

from typing import List, Dict, Optional
from app.cognos.extraction.nd_mmis_dsd_models import NdMmisDsd
from app.domain.cognos_requirement import (
    CognosRequirement,
    RequirementCategory,
    RequirementConfidence,
    RequirementSet,
    SourceLogicType,
    TestOrigin,
)
from app.domain.cognos_models import SourceReference


_CATEGORY_ABBREV = {
    RequirementCategory.REPORT_METADATA: "META",
    RequirementCategory.REPORT_ID: "ID",
    RequirementCategory.REPORT_TITLE: "TITL",
    RequirementCategory.REPORT_DESCRIPTION: "DESC",
    RequirementCategory.REPORT_SOURCE: "SRC",
    RequirementCategory.REPORT_GENERATED_BY: "GEN",
    RequirementCategory.REPORT_FREQUENCY: "FREQ",
    RequirementCategory.SELECTION_CRITERIA: "SEL",
    RequirementCategory.PROMPT: "PRMT",
    RequirementCategory.PARAMETER: "PARAM",
    RequirementCategory.HEADER: "HDR",
    RequirementCategory.COLUMN: "COL",
    RequirementCategory.COLUMN_LABEL: "LBL",
    RequirementCategory.COLUMN_SOURCE: "CSRC",
    RequirementCategory.COLUMN_LOGIC: "LOGIC",
    RequirementCategory.COLUMN_FORMAT: "FMT",
    RequirementCategory.SORT: "SORT",
    RequirementCategory.CONTROL_BREAK: "CB",
    RequirementCategory.TOTAL: "TOT",
    RequirementCategory.COUNT: "CNT",
    RequirementCategory.LAYOUT: "LAY",
    RequirementCategory.REPORT_HEADER: "RHDR",
    RequirementCategory.SECTION_HEADING: "SECH",
    RequirementCategory.PAGINATION: "PAGE",
    RequirementCategory.FOOTER: "FTR",
    RequirementCategory.OUTPUT_FORMAT: "OUT",
    RequirementCategory.DISTRIBUTION: "DIST",
    RequirementCategory.RETENTION: "RET",
    RequirementCategory.SPECIAL_PROCESSING: "SPEC",
    RequirementCategory.BUSINESS_RULE: "RULE",
    RequirementCategory.DATA_MAPPING: "DMAP",
    RequirementCategory.DATABASE_MAPPING: "DBMAP",
}


class NdMmisRequirementBuilder:
    """
    Translates NdMmisDsd AST into canonical CognosRequirement objects.
    """

    def __init__(self, dsd: NdMmisDsd):
        self.dsd = dsd
        report_id_full = dsd.definition.report_id or "OPR-TPL-188"
        self.report_id = report_id_full

        parts = report_id_full.split("-")
        if len(parts) >= 3:
            self.report_id_prefix = (parts[0] + parts[-1]).upper()
        else:
            self.report_id_prefix = report_id_full.replace(" ", "-").upper()

        self.seq_counters: Dict[RequirementCategory, int] = {}

    def _next_seq(self, cat: RequirementCategory) -> int:
        self.seq_counters[cat] = self.seq_counters.get(cat, 0) + 1
        return self.seq_counters[cat]

    def _create_req(
        self,
        category: RequirementCategory,
        field: str,
        text: str,
        section: str,
        business_label: str = "",
        source_table: str = "",
        source_column: str = "",
        processing_rule: str = "",
        source_logic_type: SourceLogicType = SourceLogicType.DIRECT_SOURCE,
    ) -> CognosRequirement:
        seq = self._next_seq(category)
        abbrev = _CATEGORY_ABBREV.get(category, "UNK")
        req_id = f"REQ-{self.report_id_prefix}-{abbrev}-{seq:03d}"

        req = CognosRequirement(
            requirement_id=req_id,
            report_id=self.report_id,
            category=category,
            field=field,
            business_label=business_label or field,
            requirement_text=text,
            source_section=section,
            status="EXTRACTED",
            origin=TestOrigin.DIRECT_SPECIFICATION,
            confidence=RequirementConfidence.HIGH,
            source_table=source_table,
            source_column=source_column,
            source_columns=[source_column] if source_column else [],
            processing_rule=processing_rule,
            source_logic_type=source_logic_type,
        )
        req.evidence_references.append(SourceReference(
            section=section,
            source_text=text,
        ))
        return req

    def build(self) -> RequirementSet:
        reqs: List[CognosRequirement] = []

        # 1. Report Title & Description
        if self.dsd.definition.report_name:
            desc_text = self.dsd.definition.report_description or ""
            reqs.append(self._create_req(
                category=RequirementCategory.REPORT_DESCRIPTION,
                field="Report Name and Description",
                text=(
                    f"Report Name: '{self.dsd.definition.report_name}'. "
                    f"Report ID: '{self.dsd.definition.report_id}'. "
                    f"Description: {desc_text}"
                ),
                section="Report Definition",
                business_label=self.dsd.definition.report_name,
            ))

        # 2. Output Format
        if self.dsd.output.output_formats:
            fmt_str = ", ".join(self.dsd.output.output_formats)
            portal_str = f" via {self.dsd.output.portal}" if self.dsd.output.portal else ""
            reqs.append(self._create_req(
                category=RequirementCategory.OUTPUT_FORMAT,
                field="Report Output",
                text=f"Report must generate in {fmt_str} format{portal_str}.",
                section="Report Output",
                business_label="Output Format",
            ))

        # 3. Distribution & Scheduling
        freq = self.dsd.definition.frequency_type or "On Request"
        freq_expl = self.dsd.definition.frequency_explanation or ""
        reqs.append(self._create_req(
            category=RequirementCategory.DISTRIBUTION,
            field="Report Frequency",
            text=f"Report frequency: {freq}. Trigger details: {freq_expl}",
            section="Report Generation",
            business_label="Execution Schedule",
        ))

        # 4. Layout
        pres_type = self.dsd.presentation_type or "List Object"
        reqs.append(self._create_req(
            category=RequirementCategory.LAYOUT,
            field="Report Layout",
            text=f"Report layout must render as a {pres_type}.",
            section="Report Specification",
            business_label="Layout Structure",
        ))

        # 5. Section Headings
        for sh in self.dsd.section_headings:
            proc = sh.processing_rules or ""
            is_lookup = "R_VV" in proc or "lookup" in proc.lower() or "Code-Description" in proc
            reqs.append(self._create_req(
                category=RequirementCategory.SECTION_HEADING,
                field=sh.label,
                text=f"Report section heading '{sh.label}': {sh.description or ''}" + (f" (Processing: {proc})" if proc else ""),
                section="Report Section Heading",
                business_label=sh.label,
                processing_rule=proc,
                source_logic_type=SourceLogicType.LOOKUP if is_lookup else SourceLogicType.DIRECT_SOURCE,
            ))

        # 5B. Selection Criteria
        for sc in self.dsd.selection_criteria:
            if sc.field_name and sc.field_name.upper() not in ("N/A", "NONE", "REPORT FIELD"):
                crit_text = f"Report selection criteria for '{sc.field_name}'"
                if sc.parameters:
                    crit_text += f": {sc.parameters}"
                if sc.default_value:
                    crit_text += f" (Default: {sc.default_value})"
                if sc.prompt:
                    crit_text += f" (Prompt: {sc.prompt})"

                reqs.append(self._create_req(
                    category=RequirementCategory.SELECTION_CRITERIA,
                    field=sc.field_name,
                    text=crit_text,
                    section="Report Selection Criteria",
                    business_label=sc.field_name,
                    processing_rule=sc.parameters or "",
                ))

        # 6. Sorts
        for s in self.dsd.sorts:
            reqs.append(self._create_req(
                category=RequirementCategory.SORT,
                field=s.field_name,
                text=f"Sort by {s.field_name} ({s.direction})",
                section="Report Control Breaks, Totals, Counts, and Sorts",
                business_label=s.field_name,
                source_column=s.field_name,
            ))

        # 6B. Control Breaks
        for cb in self.dsd.control_breaks:
            for fname in cb.field_names:
                if fname and fname.upper() not in ("N/A", "NONE", ""):
                    reqs.append(self._create_req(
                        category=RequirementCategory.CONTROL_BREAK,
                        field=fname,
                        text=f"Report control break on '{fname}' ({cb.break_type} level)",
                        section="Report Control Breaks, Totals, Counts, and Sorts",
                        business_label=fname,
                    ))

        # 6C. Totals & Counts
        for tc in self.dsd.totals_and_counts:
            cat = RequirementCategory.COUNT if tc.total_type == "Count" else RequirementCategory.TOTAL
            for fname in tc.field_names:
                if fname and fname.upper() not in ("N/A", "NONE", ""):
                    t_text = f"{tc.total_type} for '{fname}' ({tc.scope} level)"
                    if tc.processing_rules:
                        t_text += f": {tc.processing_rules}"
                    reqs.append(self._create_req(
                        category=cat,
                        field=fname,
                        text=t_text,
                        section="Report Control Breaks, Totals, Counts, and Sorts",
                        business_label=fname,
                        processing_rule=tc.processing_rules or "",
                    ))

        # 6D. Special Processing & Calculations
        for sp in self.dsd.special_processing:
            if sp.label and sp.label.upper() not in ("N/A", "NONE", ""):
                sp_text = f"Special processing rule for '{sp.label}'"
                if sp.description:
                    sp_text += f": {sp.description}"
                if sp.processing_rules:
                    sp_text += f" (Processing: {sp.processing_rules})"
                reqs.append(self._create_req(
                    category=RequirementCategory.SPECIAL_PROCESSING,
                    field=sp.label,
                    text=sp_text,
                    section="Report Special Processing",
                    business_label=sp.label,
                    source_table=sp.source_table or "",
                    source_column=sp.source_column or "",
                    processing_rule=sp.processing_rules or "",
                ))

        # 7. Report Body Fields
        for rf in self.dsd.report_body:
            proc = rf.source_column_processing_rules or ""
            col_name = rf.source_column or ""
            is_lookup = (
                "R_VV" in proc
                or "lookup" in proc.lower()
                or "valid values" in proc.lower()
            )
            cat = RequirementCategory.COLUMN_LOGIC if is_lookup else RequirementCategory.COLUMN
            logic_type = SourceLogicType.LOOKUP if is_lookup else SourceLogicType.DIRECT_SOURCE

            req_text = f"Report field '{rf.field_label}' must be formatted and mapped to {rf.source_table or 'NOT_DEFINED'}.{col_name or 'NOT_DEFINED'}"
            if proc:
                req_text += f". Processing Rule: {proc}"

            req = self._create_req(
                category=cat,
                field=rf.field_label,
                text=req_text,
                section="Report Body",
                business_label=rf.field_label,
                source_table=rf.source_table or "",
                source_column=col_name,
                processing_rule=proc,
                source_logic_type=logic_type,
            )
            req.description = rf.field_description or ""
            reqs.append(req)

        # 8. Footnotes
        for fn in self.dsd.footnotes:
            reqs.append(self._create_req(
                category=RequirementCategory.FOOTER,
                field=fn.label,
                text=f"Report footnote '{fn.label}' rule: {fn.processing_rules or ''}",
                section="Report Footnote",
                business_label=fn.label,
                processing_rule=fn.processing_rules or "",
            ))

        req_set = RequirementSet(
            requirements=reqs,
            report_id=self.report_id,
        )
        return req_set
