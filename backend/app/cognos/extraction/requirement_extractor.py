"""
Requirement extraction orchestrator.

Coordinates all section-specific extractors to transform a parsed DOCX
into a complete set of traceable Cognos requirements.

Each requirement gets a deterministic ID following the pattern:
    REQ-{REPORT_ID_ABBREV}-{CATEGORY_ABBREV}-{SEQUENCE}

Requirements are deduplicated across sections (the same requirement may
appear in Report Definition, Report Layout, and Report Specification).
"""

from __future__ import annotations

import re
from typing import Any

from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import (
    CognosRequirement,
    RequirementCategory,
    RequirementConfidence,
    RequirementSet,
)
from app.services.cognos_docx_parser import CognosParsedDocument

from app.cognos.extraction.metadata_extractor import extract_metadata
from app.cognos.extraction.column_extractor import extract_columns
from app.cognos.extraction.sort_extractor import extract_sorts_and_groups
from app.cognos.extraction.special_processing_extractor import extract_special_processing
from app.cognos.extraction.selection_criteria_extractor import extract_selection_criteria
from app.cognos.extraction.layout_extractor import extract_layout


# Category abbreviations for requirement IDs
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


def _make_report_id_prefix(report_id: str) -> str:
    """
    Create a short prefix from the report ID for requirement/test IDs.

    Example: OPR-TPL-016 -> OPR016, OPR-SRA-139 -> OPR139
    """
    if not report_id:
        return "UNKNOWN"
    
    parts = report_id.split("-")
    if len(parts) >= 3:
        # Take first and last parts (e.g. OPR and 139)
        return (parts[0] + parts[-1]).upper()
    return report_id.replace(" ", "-").upper()


def _make_requirement_id(
    report_id_prefix: str,
    category: RequirementCategory,
    sequence: int,
) -> str:
    """Generate a deterministic requirement ID."""
    abbrev = _CATEGORY_ABBREV.get(category, "UNK")
    return f"REQ-{report_id_prefix}-{abbrev}-{sequence:03d}"


def extract_requirements(
    doc: CognosParsedDocument,
    source_document_name: str = "",
) -> tuple[ReportDefinition, RequirementSet]:
    """
    Main orchestrator: extract all requirements from a parsed Cognos DOCX.

    Returns (ReportDefinition, RequirementSet).
    """
    report_def = ReportDefinition(source_document=source_document_name)
    all_warnings: list[str] = []

    # --- 1. Extract metadata ---
    metadata, meta_warnings = extract_metadata(doc, source_document_name)
    report_def.metadata = metadata
    all_warnings.extend(meta_warnings)

    report_id_prefix = _make_report_id_prefix(metadata.report_id)

    # --- 2. Extract columns/fields ---
    fields, col_warnings = extract_columns(doc, source_document_name, metadata.report_id)
    report_def.report_fields = fields
    all_warnings.extend(col_warnings)

    # --- 3. Extract sorts, control breaks, totals, counts ---
    sorts, control_breaks, totals, counts, sort_warnings = extract_sorts_and_groups(
        doc, source_document_name
    )
    report_def.sort_definitions = sorts
    report_def.control_break_definitions = control_breaks
    report_def.total_definitions = totals
    report_def.count_definitions = counts
    all_warnings.extend(sort_warnings)

    # --- 4. Extract special processing ---
    special_processing, sp_warnings = extract_special_processing(
        doc, source_document_name
    )
    report_def.special_processing = special_processing
    all_warnings.extend(sp_warnings)

    # --- Extract selection criteria & parameters ---
    sc, sc_warnings = extract_selection_criteria(doc, source_document_name, metadata.report_id)
    report_def.selection_criteria = sc
    all_warnings.extend(sc_warnings)

    # --- 6. Extract layout ---
    layout, layout_warnings = extract_layout(doc, source_document_name)
    report_def.layout = layout
    all_warnings.extend(layout_warnings)
    
    # --- 6.5. Cross-check Report Body against Report Layout ---
    # Clean the body field labels and layout element names for basic matching
    body_labels = {re.sub(r'[^a-zA-Z0-9]', '', f.business_label.lower()) for f in fields if f.business_label}
    layout_labels = {re.sub(r'[^a-zA-Z0-9]', '', e.element_name.lower()) for e in layout.body_elements if e.element_name}
    
    for field in fields:
        if not field.business_label or field.business_label.lower() in ("n/a", "review_required", "unknown"):
            continue
        clean_label = re.sub(r'[^a-zA-Z0-9]', '', field.business_label.lower())
        if clean_label and clean_label not in layout_labels:
            # Layout might be very visual, don't trigger for purely calculated hidden fields or metadata
            if field.field_type.value != "Derived":
                all_warnings.append(f"Validation Warning: Field '{field.business_label}' found in Report Body but missing from Report Layout.")

    # --- 7. Store warnings ---
    report_def.parse_warnings = all_warnings

    # --- 8. Build the requirement set ---
    req_set = _build_requirement_set(
        report_def, report_id_prefix, source_document_name
    )

    return report_def, req_set


def _build_requirement_set(
    report_def: ReportDefinition,
    report_id_prefix: str,
    source_document_name: str,
) -> RequirementSet:
    """
    Transform a ReportDefinition into a flat list of traceable requirements.
    """
    req_set = RequirementSet(
        report_id=report_def.metadata.report_id,
        source_document=source_document_name,
    )

    seq_counters: dict[RequirementCategory, int] = {}

    def _next_seq(cat: RequirementCategory) -> int:
        seq_counters[cat] = seq_counters.get(cat, 0) + 1
        return seq_counters[cat]

    def _add(
        category: RequirementCategory,
        field: str,
        text: str,
        section: str = "",
        page: int | None = None,
        source_table: str = "",
        source_columns: list[str] | None = None,
        processing_rule: str = "",
        formatting_rule: str = "",
        confidence: RequirementConfidence = RequirementConfidence.HIGH,
        is_ambiguous: bool = False,
        open_questions: list[str] | None = None,
        source_logic_type: Any = None,
    ) -> CognosRequirement:
        seq = _next_seq(category)
        
        # We need to import it here to avoid circular imports if needed, or just use the passed value
        from app.domain.cognos_models import SourceLogicType
        logic_type = source_logic_type if source_logic_type is not None else SourceLogicType.UNKNOWN

        req = CognosRequirement(
            requirement_id=_make_requirement_id(report_id_prefix, category, seq),
            report_id=report_def.metadata.report_id,
            category=category,
            field=field,
            requirement_text=text,
            source_document=source_document_name,
            source_section=section,
            source_page=page,
            source_table=source_table,
            source_columns=source_columns or [],
            processing_rule=processing_rule,
            formatting_rule=formatting_rule,
            confidence=confidence,
            is_ambiguous=is_ambiguous,
            open_questions=open_questions or [],
            source_logic_type=logic_type,
        )
        req_set.requirements.append(req)
        return req

    md = report_def.metadata

    # --- Metadata requirements ---
    if md.report_id:
        _add(RequirementCategory.REPORT_ID, "Report ID",
             f"Report must display Report ID: {md.report_id}",
             md.source.section, md.source.page)

    if md.report_title:
        _add(RequirementCategory.REPORT_TITLE, "Report Title",
             f"Report must display title: {md.report_title}",
             md.source.section, md.source.page)

    if md.report_description:
        _add(RequirementCategory.REPORT_DESCRIPTION, "Report Description",
             f"Report description/business purpose: {md.report_description}",
             md.source.section, md.source.page)

    if md.source_type:
        _add(RequirementCategory.REPORT_SOURCE, "Report Source Type",
             f"Report source type is: {md.source_type}",
             md.source.section, md.source.page)

    if md.source_component:
        _add(RequirementCategory.REPORT_SOURCE, "Report Source Component",
             f"Report source component is: {md.source_component}",
             md.source.section, md.source.page)

    if md.generated_by:
        _add(RequirementCategory.REPORT_GENERATED_BY, "Report Generated By",
             f"Report generated by: {md.generated_by}",
             md.source.section, md.source.page)

    if md.frequency:
        _add(RequirementCategory.REPORT_FREQUENCY, "Report Frequency",
             f"Report frequency: {md.frequency}",
             md.source.section, md.source.page)

    if md.lob:
        _add(RequirementCategory.HEADER, "LOB",
             f"Report LOB/Line of Business: {md.lob}",
             md.source.section, md.source.page)

    if md.division_department:
        _add(RequirementCategory.HEADER, "Department",
             f"Report department: {md.division_department}",
             md.source.section, md.source.page)

    # --- Selection criteria requirements ---
    for sc in report_def.selection_criteria:
        text = f"Selection criterion: {sc.field}"
        if sc.prompt:
            text += " (prompted)"
        if sc.filter_logic:
            text += f". Filter logic: {sc.filter_logic}"
        _add(RequirementCategory.SELECTION_CRITERIA, sc.field, text,
             sc.source.section, sc.source.page)

    # --- Column/field requirements ---
    for fld in report_def.report_fields:
        req_text = f"Report field '{fld.field_name}' must be formatted and mapped to {fld.source_table or 'NOT_DEFINED'}.{fld.source_column or 'NOT_DEFINED'}"
        if fld.processing_rule:
            req_text += f". Processing Rule: {fld.processing_rule}"
        if fld.formatting_rule:
            req_text += f". Formatting Rule: {fld.formatting_rule}"

        _add(RequirementCategory.COLUMN, fld.field_name, req_text,
             fld.source.section or "Report Specification", fld.source.page,
             source_table=fld.source_table or 'NOT_DEFINED',
             source_columns=fld.source_columns or ([fld.source_column] if fld.source_column else []),
             processing_rule=fld.processing_rule,
             formatting_rule=fld.formatting_rule,
             source_logic_type=fld.source_logic_type)

    # --- Sort requirements ---
    for sort in report_def.sort_definitions:
        level = _ordinal(sort.priority)
        _add(RequirementCategory.SORT, sort.field,
             f"{level} sort by {sort.field}"
             + (f" ({sort.direction.value})" if sort.direction.value != "Unknown" else ""),
             sort.source.section, sort.source.page)

    # --- Control break requirements ---
    for cb in report_def.control_break_definitions:
        _add(RequirementCategory.CONTROL_BREAK, cb.field,
             f"{cb.break_type} Control break on {cb.field}"
             + (f": {cb.description}" if cb.description else ""),
             cb.source.section, cb.source.page)

    # --- Total requirements ---
    for total in report_def.total_definitions:
        _add(RequirementCategory.TOTAL, total.field,
             f"{total.total_type} for {total.field}"
             + (f" ({total.scope})" if total.scope else ""),
             total.source.section, total.source.page)

    # --- Count requirements ---
    for count in report_def.count_definitions:
        _add(RequirementCategory.COUNT, count.field,
             f"{count.count_type} for {count.field}"
             + (f" ({count.scope})" if count.scope else ""),
             count.source.section, count.source.page)

    # --- Layout requirements ---
    for elem in report_def.layout.header_elements:
        _add(RequirementCategory.LAYOUT, elem.element_name,
             f"Header layout element: {elem.element_name}",
             "Report Layout", report_def.layout.source.page)

    for elem in report_def.layout.footer_elements:
        cat = RequirementCategory.FOOTER
        if "page" in elem.element_name.lower():
            cat = RequirementCategory.PAGINATION
        _add(cat, elem.element_name,
             f"Footer element: {elem.element_name}",
             "Report Layout", report_def.layout.source.page)

    # --- Output requirements ---
    for fmt in report_def.output.formats:
        _add(RequirementCategory.OUTPUT_FORMAT, fmt,
             f"Report output format: {fmt}",
             report_def.output.source.section, report_def.output.source.page)

    # --- Special processing requirements ---
    for sp in report_def.special_processing:
        text = f"Special processing: {sp.use_case}"
        if sp.naming_convention:
            text += f". Naming convention: {sp.naming_convention}"
        if sp.version:
            text += f". Version: {sp.version}"
        _add(RequirementCategory.SPECIAL_PROCESSING,
             sp.version or sp.use_case,
             text, sp.source.section, sp.source.page)

    # --- Compute summary ---
    req_set.compute_summary()

    return req_set


def _ordinal(n: int) -> str:
    """Convert integer to ordinal string (1 -> Primary, 2 -> Secondary, etc.)."""
    ordinals = {
        1: "Primary",
        2: "Secondary",
        3: "Tertiary",
        4: "Quaternary",
        5: "Quinary",
    }
    return ordinals.get(n, f"{n}th")
