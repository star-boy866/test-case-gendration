"""
North Dakota MMIS DSD Schema & Pydantic Models.

Models representing the structural AST extracted from North Dakota Medicaid
Systems Project MMIS Report Definition documents.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class NdMmisReportDefinitionSection(BaseModel):
    report_name: Optional[str] = None
    report_id: Optional[str] = None
    report_description: Optional[str] = None
    state_lob: Optional[str] = None
    mita_process: Optional[str] = None
    report_status: Optional[str] = None
    generated_from: Optional[str] = None
    calendar_type: Optional[str] = None
    frequency_type: Optional[str] = None
    frequency_explanation: Optional[str] = None
    accumulation_type: Optional[str] = None


class NdSelectionCriterionRow(BaseModel):
    field_name: Optional[str] = None
    parameters: Optional[str] = None
    prompt: Optional[str] = None
    default_value: Optional[str] = None


class NdSortRow(BaseModel):
    field_name: str
    direction: str = "Ascending"  # Ascending | Descending


class NdReportOutputSection(BaseModel):
    output_formats: List[str] = Field(default_factory=list)
    portal: Optional[str] = None
    retention_type: Optional[str] = None
    retention_duration: Optional[str] = None


class NdSectionHeadingRow(BaseModel):
    label: str
    description: Optional[str] = None
    processing_rules: Optional[str] = None


class NdReportBodyRow(BaseModel):
    field_type: Optional[str] = "Column"
    field_label: str
    field_description: Optional[str] = None
    source_table: Optional[str] = None
    source_column: Optional[str] = None
    source_tables: List[str] = Field(default_factory=list)
    source_columns: List[str] = Field(default_factory=list)
    source_column_processing_rules: Optional[str] = None


class NdFootnoteRow(BaseModel):
    label: str
    description: Optional[str] = None
    processing_rules: Optional[str] = None


class NdControlBreakRow(BaseModel):
    break_type: str = "Section"  # "Page" | "Section"
    field_names: List[str] = Field(default_factory=list)


class NdTotalCountRow(BaseModel):
    total_type: str = "Total"  # "Total" | "Count"
    scope: str = "Section"     # "Grand" | "Section" | "Running"
    field_names: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    processing_rules: Optional[str] = None


class NdSpecialProcessingRow(BaseModel):
    label: str
    description: Optional[str] = None
    source_table: Optional[str] = None
    source_column: Optional[str] = None
    processing_rules: Optional[str] = None
    sql_example: Optional[str] = None


class NdMmisDsd(BaseModel):
    definition: NdMmisReportDefinitionSection = Field(default_factory=NdMmisReportDefinitionSection)
    selection_criteria: List[NdSelectionCriterionRow] = Field(default_factory=list)
    sorts: List[NdSortRow] = Field(default_factory=list)
    control_breaks: List[NdControlBreakRow] = Field(default_factory=list)
    totals_and_counts: List[NdTotalCountRow] = Field(default_factory=list)
    special_processing: List[NdSpecialProcessingRow] = Field(default_factory=list)
    output: NdReportOutputSection = Field(default_factory=NdReportOutputSection)
    presentation_type: Optional[str] = "List Object"
    section_headings: List[NdSectionHeadingRow] = Field(default_factory=list)
    report_body: List[NdReportBodyRow] = Field(default_factory=list)
    footnotes: List[NdFootnoteRow] = Field(default_factory=list)
