"""
Cognos XML Domain Models.

These models represent the "As-Built" state of the Cognos report,
extracted directly from the report specification XML.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class LayoutObjectType(str, Enum):
    LIST = "List"
    CROSSTAB = "Crosstab"
    REPEATER = "Repeater"
    CHART = "Chart"
    UNKNOWN = "Unknown"


class ImplementationType(str, Enum):
    DIRECT = "DIRECT"
    CALCULATED = "CALCULATED"
    LOOKUP = "LOOKUP"
    CONCATENATED = "CONCATENATED"
    CONDITIONAL = "CONDITIONAL"
    FORMATTED = "FORMATTED"
    AGGREGATED = "AGGREGATED"
    PROGRAM_GENERATED = "PROGRAM_GENERATED"
    TECHNICAL = "TECHNICAL"
    UNKNOWN = "UNKNOWN"


class UsageContext(str, Enum):
    DISPLAYED_BUSINESS_FIELD = "DISPLAYED_BUSINESS_FIELD"
    DISPLAYED_TECHNICAL_FIELD = "DISPLAYED_TECHNICAL_FIELD"
    HIDDEN_TECHNICAL_FIELD = "HIDDEN_TECHNICAL_FIELD"
    CALCULATION_SUPPORT_FIELD = "CALCULATION_SUPPORT_FIELD"
    LAYOUT_SUPPORT_FIELD = "LAYOUT_SUPPORT_FIELD"
    VARIABLE_SUPPORT_FIELD = "VARIABLE_SUPPORT_FIELD"
    QUERY_ONLY_FIELD = "QUERY_ONLY_FIELD"


class XMLDataFormat(BaseModel):
    format_type: str  # date, number, string, etc.
    pattern: str = "" # e.g., 'yyyy-mm-dd'


class FilterContext(str, Enum):
    QUERY_FILTER = "QUERY_FILTER"
    REPORT_SELECTION_CRITERIA = "REPORT_SELECTION_CRITERIA"
    PAGE_DISPLAY_CONDITION = "PAGE_DISPLAY_CONDITION"
    CONDITIONAL_STYLE = "CONDITIONAL_STYLE"
    VARIABLE_CONDITION = "VARIABLE_CONDITION"
    JOIN_CONDITION = "JOIN_CONDITION"
    BUSINESS_RULE = "BUSINESS_RULE"


class XMLFilter(BaseModel):
    expression: str
    context: FilterContext
    provenance: str


class XMLDataItem(BaseModel):
    name: str                   
    label: str                  
    expression: str             
    implementation_type: ImplementationType
    aggregate_function: str = ""
    source_tables: list[str] = Field(default_factory=list)
    source_columns: list[str] = Field(default_factory=list)
    data_format: XMLDataFormat | None = None
    is_displayed: bool = False
    usage_context: list[UsageContext] = Field(default_factory=list)
    provenance: str


class XMLQuery(BaseModel):
    query_name: str
    sql: str = ""
    joins: list[str] = Field(default_factory=list)
    filters: list[XMLFilter] = Field(default_factory=list)
    data_items: list[XMLDataItem] = Field(default_factory=list)


class XMLLayout(BaseModel):
    object_type: LayoutObjectType = LayoutObjectType.UNKNOWN
    displayed_items: list[str] = Field(default_factory=list) 
    sorts: list[str] = Field(default_factory=list)
    groupings: list[str] = Field(default_factory=list)
    no_data_handlers: list[str] = Field(default_factory=list)
    conditions: list[XMLFilter] = Field(default_factory=list)


class CognosXMLModel(BaseModel):
    report_metadata: dict[str, str] = Field(default_factory=dict)
    package_model: str = ""
    queries: list[XMLQuery] = Field(default_factory=list)
    layouts: list[XMLLayout] = Field(default_factory=list)
    variables: list[str] = Field(default_factory=list)
