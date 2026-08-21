"""
Cognos Report Definition domain models.

Structured Pydantic models representing the full Cognos report definition
as extracted from a Report Definition / Design Specification DOCX.

These models are the intermediate representation between raw DOCX parsing
and test case generation. Every field traces back to a specific section
and page in the source document.

IMPORTANT: These models are NEVER populated by invention. Every value must
be extracted from the source document or explicitly marked as missing/ambiguous.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ReportType(str, Enum):
    STANDARD = "Standard"
    CUSTOMIZED = "Customized"
    UNKNOWN = "Unknown"


class SourceType(str, Enum):
    OLTP = "OLTP"
    OLAP = "OLAP"
    DATA_WAREHOUSE = "Data Warehouse"
    OTHER = "Other"
    UNKNOWN = "Unknown"


class FrequencyType(str, Enum):
    DAILY = "Daily"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    ANNUALLY = "Annually"
    AD_HOC = "Ad Hoc"
    EVENT_DRIVEN = "Event Driven"
    ON_DEMAND = "On Demand"
    UNKNOWN = "Unknown"


class SortDirection(str, Enum):
    ASCENDING = "Ascending"
    DESCENDING = "Descending"
    UNKNOWN = "Unknown"


class FieldType(str, Enum):
    """Classification of how a report field derives its value."""
    DIRECT = "Direct"                  # Straight from source column
    DERIVED = "Derived"                # Computed from other fields
    CALCULATED = "Calculated"          # Arithmetic calculation
    CONCATENATED = "Concatenated"      # Multiple fields joined together
    FORMATTED = "Formatted"            # Direct field with formatting applied
    MAPPED = "Mapped"                  # Code-to-description lookup
    CONDITIONAL = "Conditional"        # Value depends on conditions
    UNKNOWN = "Unknown"


class SourceLogicType(str, Enum):
    """How a report field's value is derived from the database / application logic."""
    DIRECT_SOURCE = "DIRECT_SOURCE"
    MULTI_SOURCE = "MULTI_SOURCE"
    CONCATENATED = "CONCATENATED"
    LOOKUP = "LOOKUP"
    JOIN = "JOIN"
    CALCULATED = "CALCULATED"
    PROGRAM_GENERATED = "PROGRAM_GENERATED"
    FORMATTED = "FORMATTED"
    CONDITIONAL = "CONDITIONAL"
    SYSTEM_GENERATED = "SYSTEM_GENERATED"
    UNKNOWN = "UNKNOWN"

    # Legacy string aliases for backwards compatibility
    DIRECT_MAPPING = "DIRECT_SOURCE"
    CONCATENATION = "CONCATENATED"
    TRANSFORMATION = "CALCULATED"
    FORMATTING = "FORMATTED"
    CALCULATION = "CALCULATED"
    HEADER_RECORD = "SYSTEM_GENERATED"
    STATIC = "SYSTEM_GENERATED"


class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class SourceReference(BaseModel):
    """Traceability back to the source document."""
    document_name: str = ""
    page: Optional[int] = None
    section: str = ""
    paragraph_index: Optional[int] = None
    table_index: Optional[int] = None
    source_text: str = ""
    snapshot_path: str = ""
    bounding_box: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Report Metadata
# ---------------------------------------------------------------------------

class ReportMetadata(BaseModel):
    """Core report identification and classification metadata."""
    report_id: str = ""
    report_title: str = ""
    report_description: str = ""
    report_type: ReportType = ReportType.UNKNOWN
    client: str = ""
    client_report_id: str = ""
    lob: str = ""
    division_department: str = ""
    source_state_code: str = ""
    source_type: str = ""
    source_component: str = ""
    generated_by: str = ""
    screen_tip: str = ""
    calendar_type: str = ""
    frequency_type: str = ""
    frequency: str = ""
    trigger: str = ""
    data_accumulation_type: str = ""
    source: SourceReference = Field(default_factory=SourceReference)


# ---------------------------------------------------------------------------
# Selection Criteria & Parameters
# ---------------------------------------------------------------------------

class SelectionCriterion(BaseModel):
    """A single selection criterion / report parameter."""
    field: str = ""
    parameter_name: str = ""
    prompt: bool = False
    required: Optional[bool] = None
    allowed_values: list[str] = Field(default_factory=list)
    source_table_column: str = ""
    filter_logic: str = ""
    default_value: str = ""
    description: str = ""
    source: SourceReference = Field(default_factory=SourceReference)


# ---------------------------------------------------------------------------
# Sort, Control Break, Total, Count
# ---------------------------------------------------------------------------

class SortDefinition(BaseModel):
    """A single sort field with priority and direction."""
    priority: int = 0
    field: str = ""
    direction: SortDirection = SortDirection.UNKNOWN
    source: SourceReference = Field(default_factory=SourceReference)


class ControlBreakDefinition(BaseModel):
    """A control break grouping."""
    field: str = ""
    break_type: str = ""  # "Page" or "Section"
    level: int = 0
    subtotal_fields: list[str] = Field(default_factory=list)
    description: str = ""
    source: SourceReference = Field(default_factory=SourceReference)


class TotalDefinition(BaseModel):
    """A total/subtotal requirement."""
    total_type: str = ""  # Grand Total, Section Total, Subtotal
    field: str = ""
    description: str = ""
    scope: str = ""  # e.g., "Per control break", "Grand"
    source: SourceReference = Field(default_factory=SourceReference)


class CountDefinition(BaseModel):
    """A count requirement."""
    count_type: str = ""
    field: str = ""
    description: str = ""
    scope: str = ""
    source: SourceReference = Field(default_factory=SourceReference)


# ---------------------------------------------------------------------------
# Output & Distribution
# ---------------------------------------------------------------------------

class OutputDefinition(BaseModel):
    """Report output configuration."""
    formats: list[str] = Field(default_factory=list)  # PDF, Excel, HTML, CSV
    reporting_portal: str = ""
    distribution: list[str] = Field(default_factory=list)
    distribution_enabled: bool = False
    distribution_groups: list[str] = Field(default_factory=list)
    retention: str = ""
    retention_type: str = ""
    output_versions: str = ""
    run_history: str = ""
    source: SourceReference = Field(default_factory=SourceReference)


# ---------------------------------------------------------------------------
# Special Processing
# ---------------------------------------------------------------------------

class SpecialProcessingItem(BaseModel):
    """A single special processing use case or version variant."""
    use_case: str = ""
    version: str = ""
    naming_convention: str = ""
    description: str = ""
    source_code: str = ""
    source: SourceReference = Field(default_factory=SourceReference)


class PresentationType(str, Enum):
    LIST_OBJECT = "LIST_OBJECT"
    CROSSTAB_OBJECT = "CROSSTAB_OBJECT"
    REPEATER_OBJECT = "REPEATER_OBJECT"
    CHART_OBJECT = "CHART_OBJECT"
    LIST = "LIST_OBJECT"
    CROSSTAB = "CROSSTAB_OBJECT"
    REPEATER = "REPEATER_OBJECT"
    CHART = "CHART_OBJECT"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

class LayoutElement(BaseModel):
    """A single layout element (header, body, or footer)."""
    element_name: str = ""
    element_value: str = ""
    position: str = ""  # e.g., "header", "body", "footer"
    source: SourceReference = Field(default_factory=SourceReference)


class LayoutDefinition(BaseModel):
    """Report layout definition."""
    presentation_type: PresentationType = PresentationType.UNKNOWN
    presentation_type_str: str = ""
    header_elements: list[LayoutElement] = Field(default_factory=list)
    body_elements: list[LayoutElement] = Field(default_factory=list)
    footer_elements: list[LayoutElement] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    row_dimensions: list[str] = Field(default_factory=list)
    column_dimensions: list[str] = Field(default_factory=list)
    measures: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    aggregations: list[str] = Field(default_factory=list)
    source: SourceReference = Field(default_factory=SourceReference)


# ---------------------------------------------------------------------------
# Report Fields (Column Specification)
# ---------------------------------------------------------------------------

class ReportField(BaseModel):
    """A single field/column in the report specification."""
    field_name: str = ""
    business_label: str = ""
    description: str = ""
    source_table: str = ""
    source_column: str = ""                    # Primary source column (legacy compat)
    source_columns: list[str] = Field(default_factory=list)  # All individual source columns
    processing_rule: str = ""
    formatting_rule: str = ""
    position: int = 0
    field_type: FieldType = FieldType.UNKNOWN
    source_logic_type: SourceLogicType = SourceLogicType.UNKNOWN
    data_type: str = ""
    section: str = ""  # Header, Body, Footer, Section Header, Specification

    # Lookup chain (for LOOKUP / DERIVED fields)
    lookup_table: str = ""
    lookup_column: str = ""
    lookup_context: str = ""

    # Preservation of exact spec text (never normalize away)
    original_source_text: str = ""

    source: SourceReference = Field(default_factory=SourceReference)


# ---------------------------------------------------------------------------
# Top-Level Report Definition
# ---------------------------------------------------------------------------

class ReportDefinition(BaseModel):
    """
    Complete structured representation of a Cognos Report Definition.

    This is the canonical domain model produced by the DOCX parser and
    requirement extraction pipeline. Every downstream component (rule engine,
    test case builder, coverage analyzer) operates on this model, never on
    raw document text.
    """
    metadata: ReportMetadata = Field(default_factory=ReportMetadata)
    selection_criteria: list[SelectionCriterion] = Field(default_factory=list)
    parameters: list[SelectionCriterion] = Field(default_factory=list)
    sort_definitions: list[SortDefinition] = Field(default_factory=list)
    control_break_definitions: list[ControlBreakDefinition] = Field(default_factory=list)
    total_definitions: list[TotalDefinition] = Field(default_factory=list)
    count_definitions: list[CountDefinition] = Field(default_factory=list)
    output: OutputDefinition = Field(default_factory=OutputDefinition)
    special_processing: list[SpecialProcessingItem] = Field(default_factory=list)
    layout: LayoutDefinition = Field(default_factory=LayoutDefinition)
    report_fields: list[ReportField] = Field(default_factory=list)

    # Document-level metadata
    source_document: str = ""
    parse_warnings: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)

    @property
    def report_id(self) -> str:
        return self.metadata.report_id

    @property
    def report_title(self) -> str:
        return self.metadata.report_title

    def get_header_fields(self) -> list[ReportField]:
        return [f for f in self.report_fields if f.section.lower() == "header"]

    def get_body_fields(self) -> list[ReportField]:
        return [f for f in self.report_fields if f.section.lower() == "body"]

    def get_footer_fields(self) -> list[ReportField]:
        return [f for f in self.report_fields if f.section.lower() == "footer"]
