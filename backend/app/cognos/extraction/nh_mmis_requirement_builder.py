from typing import Dict

from app.domain.cognos_requirement import (
    CognosRequirement,
    RequirementCategory,
    RequirementConfidence,
    RequirementSet,
    TestOrigin
)
from app.cognos.schema.nh_mmis_dsd_models import NhMmisDsd

_CATEGORY_ABBREV = {
    RequirementCategory.REPORT_METADATA: "META",
    RequirementCategory.REPORT_ID: "ID",
    RequirementCategory.REPORT_TITLE: "TITLE",
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

class NhMmisRequirementBuilder:
    def __init__(self, dsd: NhMmisDsd, generated_pages: dict[int, str] | None = None):
        self.dsd = dsd
        self.generated_pages = generated_pages or {}
        report_id_full = dsd.report_definition.client_report_id if dsd.report_definition else "UNKNOWN"
        self.report_id = report_id_full
        
        parts = report_id_full.split("-")
        if len(parts) >= 3:
            self.report_id_prefix = (parts[0] + parts[-1]).upper()
        else:
            self.report_id_prefix = report_id_full.replace(" ", "-").upper()
            
        self.req_set = RequirementSet(report_id=self.report_id)
        if dsd.report_definition:
            self.req_set.source_document = dsd.report_definition.source_document
            
        self.seq_counters: Dict[RequirementCategory, int] = {}

    def _next_seq(self, cat: RequirementCategory) -> int:
        self.seq_counters[cat] = self.seq_counters.get(cat, 0) + 1
        return self.seq_counters[cat]

    def _add_req(self, category: RequirementCategory, field: str, text: str, source_obj) -> CognosRequirement:
        seq = self._next_seq(category)
        abbrev = _CATEGORY_ABBREV.get(category, "UNK")
        req_id = f"REQ-{self.report_id_prefix}-{abbrev}-{seq:03d}"
        
        req = CognosRequirement(
            requirement_id=req_id,
            report_id=self.report_id,
            category=category,
            field=field,
            requirement_text=text,
            source_document=source_obj.source_document if source_obj else self.req_set.source_document,
            source_section=source_obj.source_section if source_obj else "",
            source_page=source_obj.source_page if source_obj else None,
            status="EXTRACTED",
            origin=TestOrigin.DIRECT_SPECIFICATION,
            confidence=RequirementConfidence.HIGH
        )
        
        from app.domain.cognos_models import SourceReference
        if source_obj:
            page = source_obj.source_page
            req.evidence_references.append(SourceReference(
                document_name=source_obj.source_document,
                page=page,
                section=source_obj.source_section,
                table_index=source_obj.table_index if hasattr(source_obj, 'table_index') else None,
                source_text=text,
                snapshot_path=self.generated_pages.get(page, "") if page else ""
            ))
            
        self.req_set.requirements.append(req)
        return req

    def build(self) -> RequirementSet:
        self._build_report_definition()
        self._build_report_generation()
        self._build_selection_criteria()
        self._build_parameters()
        self._build_sorts_breaks_totals_counts()
        self._build_output()
        self._build_retention()
        self._build_layout()
        self._build_report_specification()
        
        self.req_set.compute_summary()
        return self.req_set

    def _build_report_definition(self):
        rd = self.dsd.report_definition
        if not rd:
            return
            
        if rd.client_report_id:
            self._add_req(RequirementCategory.REPORT_ID, "Report ID", f"Report must display Report ID: {rd.client_report_id}", rd)
        if rd.report_title:
            self._add_req(RequirementCategory.REPORT_TITLE, "Report Title", f"Report must display title: {rd.report_title}", rd)
        if rd.report_description:
            self._add_req(RequirementCategory.REPORT_DESCRIPTION, "Report Description", f"Report description/business purpose: {rd.report_description}", rd)
        if rd.report_source_type:
            self._add_req(RequirementCategory.REPORT_SOURCE, "Report Source Type", f"Report source type is: {rd.report_source_type}", rd)
        if rd.report_source_type_component:
            self._add_req(RequirementCategory.REPORT_SOURCE, "Report Source Component", f"Report source component is: {rd.report_source_type_component}", rd)
        if rd.client_lob:
            self._add_req(RequirementCategory.HEADER, "LOB", f"Report LOB/Line of Business: {rd.client_lob}", rd)
        if rd.client_division_department:
            self._add_req(RequirementCategory.HEADER, "Department", f"Report department: {rd.client_division_department}", rd)

    def _build_report_generation(self):
        rg = self.dsd.report_generation
        if not rg:
            return
            
        if rg.report_generated_by:
            self._add_req(RequirementCategory.REPORT_GENERATED_BY, "Report Generated By", f"Report generated by: {rg.report_generated_by}", rg)
        if rg.report_frequency_type:
            freq_text = f"Report frequency: {rg.report_frequency_type}"
            if rg.scheduled_timeframe and "scheduled" in rg.report_frequency_type.lower():
                freq_text += f" ({rg.scheduled_timeframe})"
            self._add_req(RequirementCategory.REPORT_FREQUENCY, "Report Frequency", freq_text, rg)

    def _build_selection_criteria(self):
        for sc in self.dsd.selection_criteria:
            if sc.report_selection_criteria and sc.report_selection_criteria.lower().strip() not in ("report field", "criteria", ""):
                text = f"Selection criterion: {sc.report_selection_criteria}"
                if sc.report_field and sc.report_field.lower().strip() not in ("report field", ""):
                    text += f". Filter logic: {sc.report_field}"
                self._add_req(RequirementCategory.SELECTION_CRITERIA, sc.report_field or sc.report_selection_criteria, text, sc)

    def _build_parameters(self):
        for p in self.dsd.parameters:
            if p.parameter_description:
                text = f"Parameter: {p.parameter_description}"
                if p.prompt:
                    text += " (prompted)"
                self._add_req(RequirementCategory.PARAMETER, p.parameter_description, text, p)

    def _build_sorts_breaks_totals_counts(self):
        for s in self.dsd.sorts:
            if s.sort_by and not s.sort_by.lower().strip() in ("sort by:", "sort by", "", "n/a"):
                direction = s.direction if s.direction else "Not Specified"
                self._add_req(RequirementCategory.SORT, s.sort_by, f"Sort by {s.sort_by} ({direction})", s)
            
        for cb in self.dsd.control_breaks:
            if cb.control_break and not cb.control_break.lower().strip() in ("page:", "page", "section:", "section", "", "n/a"):
                level = cb.level if cb.level else "Not Specified"
                self._add_req(RequirementCategory.CONTROL_BREAK, cb.control_break, f"Control break on {cb.control_break} ({level})", cb)
            
        for t in self.dsd.totals:
            if t.total and not t.total.lower().strip() in ("grand:", "grand", "page:", "page", "section:", "section", "", "n/a"):
                level = t.level if t.level else "Not Specified"
                self._add_req(RequirementCategory.TOTAL, t.total, f"Total for {t.total} ({level})", t)
            
        for c in self.dsd.counts:
            if c.count and not c.count.lower().strip() in ("grand:", "grand", "page:", "page", "section:", "section", "", "n/a"):
                level = c.level if c.level else "Not Specified"
                self._add_req(RequirementCategory.COUNT, c.count, f"Count for {c.count} ({level})", c)

    def _build_output(self):
        out = self.dsd.output
        if not out:
            return
            
        if out.report_output_format:
            self._add_req(RequirementCategory.OUTPUT_FORMAT, "Output Format", f"Report output format: {out.report_output_format}", out)
        if out.reporting_portal:
            self._add_req(RequirementCategory.OUTPUT_FORMAT, "Reporting Portal", f"Delivery destination: {out.reporting_portal}", out)
        if out.report_output_distribution_groups:
            self._add_req(RequirementCategory.OUTPUT_FORMAT, "Distribution Groups", f"Distribution groups: {out.report_output_distribution_groups}", out)

    def _build_retention(self):
        ret = self.dsd.retention
        if not ret:
            return
            
        if ret.report_retention_type:
            self._add_req(RequirementCategory.RETENTION, "Retention Type", f"Report retention type: {ret.report_retention_type}", ret)
        if ret.report_output_versions:
            self._add_req(RequirementCategory.RETENTION, "Retention Duration", f"Report retention duration: {ret.report_output_versions}", ret)

    def _build_layout(self):
        lay = self.dsd.layout
        if not lay:
            return
            
        if lay.report_section_label_names:
            self._add_req(RequirementCategory.LAYOUT, "Layout Sections", f"Report layout sections: {lay.report_section_label_names}", lay)

    def _build_report_specification(self):
        for rsr in self.dsd.report_specification:
            req_text = f"Report field '{rsr.business_label}' must be formatted and mapped to {rsr.source_table or 'NOT_DEFINED'}.{rsr.source_column or 'NOT_DEFINED'}"
            if rsr.processing_rules:
                req_text += f". Processing Rule: {rsr.processing_rules}"
                
            req = self._add_req(RequirementCategory.COLUMN, rsr.business_label, req_text, rsr)
            req.business_label = rsr.business_label
            req.description = rsr.field_description
            req.source_table = rsr.source_table
            if rsr.source_column:
                req.source_columns = [rsr.source_column]
            req.processing_rule = rsr.processing_rules
