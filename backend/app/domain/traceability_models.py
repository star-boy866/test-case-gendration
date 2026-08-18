"""
Cognos Traceability Domain Models.

These models represent the mapping and traceability state between the authoritative 
DSD (ReportDefinition) and the actual implementation (CognosXMLModel).
"""

from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field

class MappingStatus(str, Enum):
    MATCH = "MATCH"
    MISSING_IN_XML = "MISSING_IN_XML"
    MISSING_IN_DSD = "MISSING_IN_DSD"
    AMBIGUOUS = "AMBIGUOUS"

class ReviewStatus(str, Enum):
    OK = "OK"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"

class MatchStrategy(str, Enum):
    EXACT_BUSINESS_LABEL = "EXACT_BUSINESS_LABEL"
    EXACT_TECHNICAL_NAME = "EXACT_TECHNICAL_NAME"
    SOURCE_COLUMN = "SOURCE_COLUMN"
    NORMALIZED_ALIAS = "NORMALIZED_ALIAS"
    FALLBACK = "FALLBACK"
    NOT_MATCHED = "NOT_MATCHED"

class FieldTrace(BaseModel):
    dsd_field_name: str
    xml_data_item_name: str = ""
    mapping_status: MappingStatus
    review_status: ReviewStatus
    implementation_type: str = ""
    transformation_present: bool = False
    confidence: float = 0.0
    match_strategy: MatchStrategy = MatchStrategy.NOT_MATCHED
    discrepancy_notes: list[str] = Field(default_factory=list)
    xml_provenance: str = ""

class SortTrace(BaseModel):
    dsd_field_name: str
    dsd_direction: str
    xml_field_name: str = ""
    xml_direction: str = ""
    mapping_status: MappingStatus
    review_status: ReviewStatus
    notes: list[str] = Field(default_factory=list)
    provenance: str = ""

class SelectionCriteriaTrace(BaseModel):
    dsd_criterion: str
    xml_filter: str = ""
    mapping_status: MappingStatus
    review_status: ReviewStatus
    notes: list[str] = Field(default_factory=list)
    provenance: str = ""

class LayoutTrace(BaseModel):
    dsd_element: str
    xml_object: str = ""
    mapping_status: MappingStatus
    review_status: ReviewStatus
    notes: list[str] = Field(default_factory=list)
    provenance: str = ""

class XMLOnlyItem(BaseModel):
    item_name: str
    item_type: str  # technical, hidden, variable
    provenance: str = ""

class TraceabilityResult(BaseModel):
    field_traces: list[FieldTrace] = Field(default_factory=list)
    sort_traces: list[SortTrace] = Field(default_factory=list)
    selection_traces: list[SelectionCriteriaTrace] = Field(default_factory=list)
    layout_traces: list[LayoutTrace] = Field(default_factory=list)
    implementation_only_items: list[XMLOnlyItem] = Field(default_factory=list)
