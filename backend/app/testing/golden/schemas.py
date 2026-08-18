from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field

class GoldenMetadata(BaseModel):
    report_id: str
    source_filename: str
    source_sha256: str
    xml_sha256: str | None = None
    golden_schema_version: int = 1
    fixture_version: int = 1
    created_at: str

class GoldenRequirement(BaseModel):
    requirement_id: str
    requirement_area: str
    statement: str
    type: str
    origin: str
    status: str
    source_document: str | None
    source_section: str | None
    source_page: str | None
    source_location: str | None
    source_table: str | None
    source_columns: list[str] = Field(default_factory=list)
    processing_rules: str | None
    formatting_rules: str | None
    comments: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)

class GoldenTestCase(BaseModel):
    test_case_id: str
    requirement_ids: list[str] = Field(default_factory=list)
    scenario: str
    test_type: str
    test_origin: str
    test_design_technique: str
    preconditions: str
    validation_steps: str
    test_data: str
    expected_result: str
    priority: str
    evidence_types: list[str] = Field(default_factory=list)

class GoldenCoverage(BaseModel):
    total_dsd_requirements: int
    covered_requirement_ids: list[str] = Field(default_factory=list)
    uncovered_requirement_ids: list[str] = Field(default_factory=list)
    supplemental_test_count: int
    coverage_percentage: float

class GoldenTraceabilityItem(BaseModel):
    requirement_id: str
    xml_path: str
    match_strategy: str
    confidence: str
    implementation_type: str
    status: str

class GoldenTraceability(BaseModel):
    report_id: str
    mappings: list[GoldenTraceabilityItem] = Field(default_factory=list)
    implementation_only_items: list[str] = Field(default_factory=list)
    missing_in_xml_items: list[str] = Field(default_factory=list)
    discrepancy_notes: list[str] = Field(default_factory=list)
