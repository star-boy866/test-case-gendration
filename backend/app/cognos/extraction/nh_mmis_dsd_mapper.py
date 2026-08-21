from app.cognos.schema.nh_mmis_dsd_models import NhMmisDsd
from app.domain.cognos_models import (
    ReportDefinition as DomainReportDefinition,
    ReportMetadata,
    SelectionCriterion,
    SortDefinition,
    ControlBreakDefinition,
    TotalDefinition,
    CountDefinition,
    OutputDefinition,
    LayoutDefinition,
    ReportField,
    SourceReference,
    SortDirection,
    FieldType,
    SourceLogicType,
    PresentationType
)

def map_dsd_to_domain(dsd: NhMmisDsd, source_document_name: str) -> DomainReportDefinition:
    domain_rd = DomainReportDefinition(source_document=source_document_name)
    
    # Metadata
    if dsd.report_definition:
        meta = ReportMetadata()
        meta.report_id = dsd.report_definition.client_report_id
        meta.client_report_id = dsd.report_definition.client_report_id
        meta.report_title = dsd.report_definition.report_title
        meta.report_description = dsd.report_definition.report_description
        meta.client = dsd.report_definition.client_name
        meta.lob = dsd.report_definition.client_lob
        meta.division_department = dsd.report_definition.client_division_department
        meta.source_type = dsd.report_definition.report_source_type
        meta.source_component = dsd.report_definition.report_source_type_component
        meta.source = SourceReference(
            document_name=dsd.report_definition.source_document,
            page=dsd.report_definition.source_page,
            section=dsd.report_definition.source_section,
            table_index=dsd.report_definition.table_index
        )
        domain_rd.metadata = meta

    if dsd.report_generation:
        domain_rd.metadata.generated_by = dsd.report_generation.report_generated_by
        domain_rd.metadata.screen_tip = dsd.report_generation.report_screen_tip
        domain_rd.metadata.calendar_type = dsd.report_generation.report_calendar_type
        domain_rd.metadata.frequency_type = dsd.report_generation.report_frequency_type
        domain_rd.metadata.frequency = dsd.report_generation.scheduled_timeframe
        domain_rd.metadata.trigger = dsd.report_generation.triggered_by
        domain_rd.metadata.data_accumulation_type = dsd.report_generation.report_data_accumulation_type

    # Selection Criteria & Parameters
    for sc in dsd.selection_criteria:
        crit = SelectionCriterion(
            field=sc.report_field or sc.report_selection_criteria,
            filter_logic=sc.report_selection_criteria,
            source=SourceReference(
                document_name=sc.source_document,
                page=sc.source_page,
                section=sc.source_section,
                table_index=sc.table_index
            )
        )
        domain_rd.selection_criteria.append(crit)

    for p in dsd.parameters:
        param = SelectionCriterion(
            field=p.parameter_description,
            prompt=p.prompt,
            source=SourceReference(
                document_name=p.source_document,
                page=p.source_page,
                section=p.source_section,
                table_index=p.table_index
            )
        )
        domain_rd.parameters.append(param)

    # Sorts
    for i, s in enumerate(dsd.sorts):
        domain_rd.sort_definitions.append(SortDefinition(
            priority=i+1,
            field=s.sort_by,
            direction=SortDirection.ASCENDING if "asc" in s.direction.lower() else (SortDirection.DESCENDING if "desc" in s.direction.lower() else SortDirection.UNKNOWN),
            source=SourceReference(
                document_name=s.source_document,
                page=s.source_page,
                section=s.source_section,
                table_index=s.table_index
            )
        ))

    # Control Breaks
    for cb in dsd.control_breaks:
        domain_rd.control_break_definitions.append(ControlBreakDefinition(
            field=cb.control_break,
            break_type=cb.level,
            source=SourceReference(
                document_name=cb.source_document,
                page=cb.source_page,
                section=cb.source_section,
                table_index=cb.table_index
            )
        ))

    # Totals
    for t in dsd.totals:
        domain_rd.total_definitions.append(TotalDefinition(
            total_type=t.level,
            field=t.total,
            source=SourceReference(
                document_name=t.source_document,
                page=t.source_page,
                section=t.source_section,
                table_index=t.table_index
            )
        ))

    # Counts
    for c in dsd.counts:
        domain_rd.count_definitions.append(CountDefinition(
            count_type=c.level,
            field=c.count,
            source=SourceReference(
                document_name=c.source_document,
                page=c.source_page,
                section=c.source_section,
                table_index=c.table_index
            )
        ))

    # Output
    if dsd.output:
        out_def = OutputDefinition(
            reporting_portal=dsd.output.reporting_portal,
            source=SourceReference(
                document_name=dsd.output.source_document,
                page=dsd.output.source_page,
                section=dsd.output.source_section,
                table_index=dsd.output.table_index
            )
        )
        if dsd.output.report_output_format:
            out_def.formats.append(dsd.output.report_output_format)
        if dsd.output.report_output_distribution_groups:
            out_def.distribution_groups.append(dsd.output.report_output_distribution_groups)
            out_def.distribution_enabled = True
        
        if dsd.retention:
            out_def.retention_type = dsd.retention.report_retention_type
            out_def.output_versions = dsd.retention.report_output_versions
            out_def.run_history = dsd.retention.report_run_history_log
            
        domain_rd.output = out_def

    # Layout
    if dsd.layout:
        domain_rd.layout.presentation_type = PresentationType.LIST_OBJECT
        domain_rd.layout.source = SourceReference(
            document_name=dsd.layout.source_document,
            page=dsd.layout.source_page,
            section=dsd.layout.source_section,
            table_index=dsd.layout.table_index
        )

    # Report Specification Fields
    for rsr in dsd.report_specification:
        rf = ReportField(
            field_name=rsr.business_label,
            business_label=rsr.business_label,
            description=rsr.field_description,
            source_table=rsr.source_table,
            source_column=rsr.source_column,
            processing_rule=rsr.processing_rules,
            field_type=FieldType.DIRECT,
            source_logic_type=SourceLogicType.DIRECT_SOURCE,
            section="Body",
            source=SourceReference(
                document_name=rsr.source_document,
                page=rsr.source_page,
                section=rsr.source_section,
                table_index=rsr.table_index
            )
        )
        if rsr.source_column:
            rf.source_columns.append(rsr.source_column)
        domain_rd.report_fields.append(rf)

    return domain_rd
