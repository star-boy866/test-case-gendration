"""
North Dakota MMIS DSD Mapper.

Maps an NdMmisDsd AST to the canonical domain ReportDefinition model.
"""

from typing import List, Optional
from app.cognos.extraction.nd_mmis_dsd_models import NdMmisDsd
from app.domain.cognos_models import (
    ReportDefinition as DomainReportDefinition,
    ReportMetadata,
    SelectionCriterion,
    SortDefinition,
    ControlBreakDefinition,
    TotalDefinition,
    CountDefinition,
    SpecialProcessingItem,
    OutputDefinition,
    LayoutDefinition,
    LayoutElement,
    SectionHeadingDefinition,
    ReportField,
    SourceReference,
    SortDirection,
    FieldType,
    SourceLogicType,
    PresentationType,
)


def map_nd_dsd_to_domain(dsd: NdMmisDsd, source_document_name: str = "") -> DomainReportDefinition:
    """Transforms NdMmisDsd AST into canonical ReportDefinition."""
    domain_rd = DomainReportDefinition(source_document=source_document_name)

    rid = dsd.definition.report_id or "ND-REP-001"
    rtitle = dsd.definition.report_name or "North Dakota MMIS Report"

    # Metadata
    meta = ReportMetadata(
        report_id=rid,
        client_report_id=rid,
        report_title=rtitle,
        report_description=dsd.definition.report_description or "",
        lob=dsd.definition.state_lob or "Medicaid",
        division_department="Department of Human Services",
        source_component=dsd.definition.generated_from or "EOR Transactional (OLTP)",
        calendar_type=dsd.definition.calendar_type or "Calendar",
        frequency_type=dsd.definition.frequency_type or "On Request",
        trigger=dsd.definition.frequency_explanation or "",
        source=SourceReference(document_name=source_document_name or rtitle, section="Report Definition"),
    )
    domain_rd.metadata = meta

    # Selection Criteria
    for sc in dsd.selection_criteria:
        if sc.field_name and sc.field_name.upper() not in ("N/A", "NONE", "REPORT FIELD"):
            crit = SelectionCriterion(
                field=sc.field_name,
                filter_logic=sc.parameters or sc.field_name,
                default_value=sc.default_value or "",
                prompt=sc.prompt == "Yes" if sc.prompt else False,
                source=SourceReference(document_name=source_document_name, section="Report Selection Criteria"),
            )
            domain_rd.selection_criteria.append(crit)

    # Sort Definitions
    for i, s in enumerate(dsd.sorts):
        direction = (
            SortDirection.ASCENDING
            if "asc" in s.direction.lower()
            else (SortDirection.DESCENDING if "desc" in s.direction.lower() else SortDirection.UNKNOWN)
        )
        domain_rd.sort_definitions.append(SortDefinition(
            priority=i + 1,
            field=s.field_name,
            direction=direction,
            source=SourceReference(document_name=source_document_name, section="Report Control Breaks, Totals, Counts, and Sorts"),
        ))

    # Control Breaks
    for cb in dsd.control_breaks:
        for fname in cb.field_names:
            if fname and fname.upper() not in ("N/A", "NONE", ""):
                domain_rd.control_break_definitions.append(ControlBreakDefinition(
                    field=fname,
                    break_type=cb.break_type,
                    source=SourceReference(document_name=source_document_name, section="Report Control Breaks, Totals, Counts, and Sorts"),
                ))

    # Totals & Counts
    for tc in dsd.totals_and_counts:
        for fname in tc.field_names:
            if fname and fname.upper() not in ("N/A", "NONE", ""):
                if tc.total_type == "Count":
                    domain_rd.count_definitions.append(CountDefinition(
                        field=fname,
                        count_type=tc.scope,
                        description=tc.description or fname,
                        source=SourceReference(document_name=source_document_name, section="Report Control Breaks, Totals, Counts, and Sorts"),
                    ))
                else:
                    domain_rd.total_definitions.append(TotalDefinition(
                        field=fname,
                        total_type=tc.scope,
                        description=tc.description or fname,
                        source=SourceReference(document_name=source_document_name, section="Report Control Breaks, Totals, Counts, and Sorts"),
                    ))

    # Special Processing & Calculations
    for sp in dsd.special_processing:
        if sp.label and sp.label.upper() not in ("N/A", "NONE", ""):
            domain_rd.special_processing.append(SpecialProcessingItem(
                use_case=sp.label,
                description=sp.description or sp.label,
                source_table=sp.source_table or "",
                source_column=sp.source_column or "",
                raw_rule_text=sp.processing_rules or "",
                sql_example=sp.sql_example or "",
                source=SourceReference(document_name=source_document_name, section="Report Special Processing"),
            ))

    # Output Definition
    out_def = OutputDefinition(
        formats=dsd.output.output_formats or ["Excel"],
        reporting_portal=dsd.output.portal or "EDMS",
        retention=dsd.output.retention_duration or "7 Years",
        retention_type=dsd.output.retention_type or "EDMS",
        source=SourceReference(document_name=source_document_name, section="Report Output"),
    )
    domain_rd.output = out_def

    # Layout Header Elements (Phase 13C.1: Authoritative ND Report Layout)
    header_elements = [
        LayoutElement(element_name="Report ID", element_value=rid),
        LayoutElement(element_name="Line of Business", element_value=dsd.definition.state_lob or "<LOB Cd — Desc>"),
        LayoutElement(element_name="Department", element_value="Department of Human Services"),
        LayoutElement(element_name="Report Title", element_value=rtitle),
        LayoutElement(element_name="Report Date", element_value="MM/DD/CCYY"),
        LayoutElement(element_name="Branding", element_value="North Dakota Department of Human Services logo"),
    ]

    pres_type = PresentationType.LIST_OBJECT
    if dsd.presentation_type and "cross" in dsd.presentation_type.lower():
        pres_type = PresentationType.CROSSTAB_OBJECT
    domain_rd.layout = LayoutDefinition(
        presentation_type=pres_type,
        header_elements=header_elements,
        source=SourceReference(document_name=source_document_name, section="Report Layout"),
    )

    # Section Headings
    for sh in dsd.section_headings:
        domain_rd.section_headings.append(SectionHeadingDefinition(
            section_label=sh.label,
            section_description=sh.description or "",
            section_processing_rules=sh.processing_rules or "",
            source=SourceReference(document_name=source_document_name, section="Report Section Heading"),
        ))

    # Report Body Fields
    for idx, rf in enumerate(dsd.report_body):
        proc = rf.source_column_processing_rules or ""
        col_name = rf.source_column or ""
        is_lookup = (
            "R_VV" in proc
            or "lookup" in proc.lower()
            or "valid values" in proc.lower()
            or col_name.upper().endswith("_CD")
            or col_name.upper().endswith("_CODE")
        )
        domain_rd.report_fields.append(ReportField(
            field_name=rf.field_label,
            business_label=rf.field_label,
            description=rf.field_description or "",
            source_table=rf.source_table or "",
            source_column=col_name,
            source_columns=[col_name] if col_name else [],
            processing_rule=proc,
            field_type=FieldType.MAPPED if is_lookup else FieldType.DIRECT,
            source_logic_type=SourceLogicType.LOOKUP if is_lookup else SourceLogicType.DIRECT_SOURCE,
            position=idx + 1,
            section="Report Body",
            source=SourceReference(document_name=source_document_name, section="Report Body"),
        ))

    return domain_rd
