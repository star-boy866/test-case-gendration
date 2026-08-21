from typing import List, Optional
from pydantic import BaseModel, Field

class ProvenanceMixin(BaseModel):
    source_document: str = ""
    source_page: Optional[int] = None
    source_section: str = ""
    table_index: Optional[int] = None
    row_index: Optional[int] = None
    cell_index: Optional[int] = None

class ReportDefinition(ProvenanceMixin):
    report_type: str = ""
    client_name: str = ""
    client_report_id: str = ""
    client_lob: str = ""
    client_division_department: str = ""
    report_title: str = ""
    report_description: str = ""
    report_source_type: str = ""
    report_source_type_component: str = ""

class ReportGeneration(ProvenanceMixin):
    report_generated_by: str = ""
    report_screen_tip: str = ""
    report_calendar_type: str = ""
    report_frequency_type: str = ""
    scheduled_timeframe: str = ""
    other_explain: str = ""
    report_data_accumulation_type: str = ""
    triggered_by: str = ""

class SelectionCriteria(ProvenanceMixin):
    report_selection_criteria: str = ""
    report_field: str = ""

class Parameter(ProvenanceMixin):
    parameter_description: str = ""
    prompt: bool = False

class Sort(ProvenanceMixin):
    sort_by: str = ""
    direction: str = ""

class ControlBreak(ProvenanceMixin):
    control_break: str = ""
    level: str = ""

class Total(ProvenanceMixin):
    total: str = ""
    level: str = ""

class Count(ProvenanceMixin):
    count: str = ""
    level: str = ""

class Output(ProvenanceMixin):
    report_output_format: str = ""
    reporting_portal: str = ""
    report_output_distribution_groups: str = ""

class Retention(ProvenanceMixin):
    report_retention_type: str = ""
    report_output_versions: str = ""
    report_run_history_log: str = ""

class Layout(ProvenanceMixin):
    report_id: str = ""
    file_name: str = ""
    report_title_line: str = ""
    report_section_label_names: str = ""

class ReportSpecificationRow(ProvenanceMixin):
    business_label: str = ""
    field_description: str = ""
    source_table: str = ""
    source_column: str = ""
    processing_rules: str = ""

class NhMmisDsd(BaseModel):
    """Root model for the NH MMIS DSD Semantic Contract."""
    report_definition: Optional[ReportDefinition] = None
    report_generation: Optional[ReportGeneration] = None
    selection_criteria: List[SelectionCriteria] = Field(default_factory=list)
    parameters: List[Parameter] = Field(default_factory=list)
    sorts: List[Sort] = Field(default_factory=list)
    control_breaks: List[ControlBreak] = Field(default_factory=list)
    totals: List[Total] = Field(default_factory=list)
    counts: List[Count] = Field(default_factory=list)
    output: Optional[Output] = None
    retention: Optional[Retention] = None
    layout: Optional[Layout] = None
    report_specification: List[ReportSpecificationRow] = Field(default_factory=list)
