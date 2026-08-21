"""
Cognos Test Case domain model.

Every generated manual UT test case must be specific enough that a Cognos
tester can execute it without needing the AI to explain what it meant.

The test case model enforces the 20+ required fields from the master
specification and provides completeness validation.

This module also defines TestSuite (collection with coverage), CoverageReport,
and SpecificationQualityReport for the full generation output.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
from app.domain.cognos_requirement import TestOrigin

class TestType(str, Enum):
    POSITIVE = "Positive"
    NEGATIVE = "Negative"
    BOUNDARY = "Boundary"
    VALIDATION = "Validation"
    ERROR_HANDLING = "Error Handling"
    INTEGRATION = "Integration"
    SECURITY = "Security"
    PERFORMANCE = "Performance"
    UNKNOWN = "Unknown"


class TestCaseStatus(str, Enum):
    DRAFT = "Draft"
    GENERATED = "Generated"
    REVIEWED = "Reviewed"
    APPROVED = "Approved"
    DEPRECATED = "Deprecated"


class EvidenceRequirement(BaseModel):
    """Structured evidence requirement for manual testing."""
    evidence_type: str = ""
    description: str = ""
    placeholder: str = ""
    mandatory: bool = True


class EvidenceReference(BaseModel):
    """Specific rendered DSD evidence for a test case."""
    evidence_id: str = ""
    evidence_type: str = ""       # e.g., DSD_REPORT_LAYOUT, DSD_REPORT_SPECIFICATION
    document_name: str = ""
    source_document_id: str = ""
    source_document_url: str = ""
    page_number: Optional[int] = None
    section: str = ""
    source_text: str = ""
    snapshot_path: str = ""       # Absolute physical path
    snapshot_url: str = ""        # API endpoint URL
    crop_path: str = ""
    bounding_box: dict = Field(default_factory=dict)
    description: str = ""



class TestCasePriority(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class CognosTestCase(BaseModel):
    """
    A single manual Cognos Unit Test case.

    Every field is designed so that a tester can answer:
    - What am I testing?
    - Where did this requirement come from?
    - What data do I need?
    - What do I do?
    - What should I verify?
    - What should the expected result be?
    """
    # --- Required fields (every test MUST have these) ---
    test_case_id: str = ""          # e.g., OPR016-HDR-01
    report_id: str = ""             # e.g., OPR-TPL-016
    report_name: str = ""           # e.g., TPL Interface (HMS) Exception Report
    test_case_title: str = ""       # Concise, descriptive title
    test_case_description: str = "" # Detailed description of what is being tested
    category: str = ""              # Header, Column Logic, Sorting, etc.
    requirement_ids: list[str] = Field(default_factory=list)  # Links to source requirements (many-to-many)
    objective: str = ""             # What is being verified
    source_document: str = ""       # Source file name
    source_section: str = ""        # Where in the spec this came from
    source_page: Optional[int] = None
    preconditions: str = ""         # What must be true before testing
    test_data: str = ""             # Test Data / Field Reference — structured source info
    test_steps: str = ""            # Step-by-step instructions
    expected_result: str = ""       # What a passing result looks like
    validation_logic: str = ""      # How to verify the result
    evidence_required: str = ""     # Legacy evidence required text
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list) # Structured evidence
    evidence_type: str = ""         # General category of evidence
    priority: TestCasePriority = TestCasePriority.MEDIUM

    # --- Source traceability fields ---
    source_field: str = ""          # Which report field this tests
    source_table: str = ""          # Source table from spec
    source_column: str = ""         # Primary source column from spec
    source_columns: str = ""        # All source columns (newline-separated for multi)
    processing_rule: str = ""       # Processing rule from spec
    formatting_rule: str = ""       # Formatting rule from spec
    formatting_logic: str = ""      # Formatting logic details
    business_rule: str = ""         # Business rule if applicable
    notes: str = ""                 # Additional notes
    assumptions: str = ""           # Assumptions made
    open_questions: str = ""        # Unresolved questions / specification gaps

    # --- Internal tracking ---
    status: TestCaseStatus = TestCaseStatus.GENERATED
    origin: TestOrigin = TestOrigin.DIRECT_SPECIFICATION
    test_type: TestType = TestType.UNKNOWN
    version: int = 1
    
    # --- Added for Phase 10.2 ---
    applicability_reason: str = ""
    evidence_references: list[EvidenceReference] = Field(default_factory=list)

    # --- Added for Phase 10.6 (Developer UT Scenario Engine) ---
    dsd_reference: str = ""          # e.g., "DSD p.4-5 § Report Body" — authoritative source text
    open_item: str = ""              # Documented conflict or REVIEW_REQUIRED item (never silently dropped)
    llm_refinement_status: str = "NOT_ATTEMPTED"  # NOT_ATTEMPTED | REFINED | FALLBACK
    confidence: str = "High"         # High | Medium | Low — extraction confidence level
    methodology_pattern: str = ""    # The methodology family this test belongs to

    @property
    def requirement_id(self) -> str:
        """Legacy accessor: returns comma-separated requirement IDs."""
        return ", ".join(self.requirement_ids) if self.requirement_ids else ""

    @property
    def is_complete(self) -> bool:
        """A test case is complete if all required fields are populated."""
        return all([
            self.test_case_id,
            self.report_id,
            self.test_case_title,
            self.category,
            self.objective,
            self.test_steps,
            self.expected_result,
            self.evidence_required,
            self.source_section,
        ])

    @property
    def missing_fields(self) -> list[str]:
        """List of required fields that are empty."""
        required = {
            "test_case_id": self.test_case_id,
            "report_id": self.report_id,
            "test_case_title": self.test_case_title,
            "category": self.category,
            "objective": self.objective,
            "test_steps": self.test_steps,
            "expected_result": self.expected_result,
            "evidence_required": self.evidence_required,
            "source_section": self.source_section,
        }
        return [k for k, v in required.items() if not v]


class CategoryCoverage(BaseModel):
    """Coverage statistics for a single category."""
    category: str = ""
    requirements_found: int = 0
    requirements_covered: int = 0
    requirements_unmapped: int = 0
    requirements_ambiguous: int = 0
    test_cases_generated: int = 0
    coverage_percentage: float = 0.0


class CoverageReport(BaseModel):
    """Full requirement-to-test-case coverage analysis."""
    report_id: str = ""
    total_requirements: int = 0
    requirements_covered: int = 0
    requirements_unmapped: int = 0
    requirements_ambiguous: int = 0
    requirements_duplicate: int = 0
    overall_coverage_percentage: float = 0.0
    methodology_patterns_generated: int = 0
    methodology_coverage_percentage: float = 0.0
    category_coverage: list[CategoryCoverage] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class TraceabilityEntry(BaseModel):
    """One row of the traceability matrix."""
    requirement_id: str = ""
    requirement_text: str = ""
    category: str = ""
    source_page: Optional[int] = None
    test_case_ids: list[str] = Field(default_factory=list)
    coverage_status: str = ""  # Covered, Uncovered, Partial, Ambiguous


class SpecificationQualityReport(BaseModel):
    """Analysis of the source specification's completeness."""
    report_id: str = ""
    report_title: str = ""
    requirements_found: int = 0
    testable_requirements: int = 0
    ambiguous_requirements: int = 0
    missing_information: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class TestSuiteSummary(BaseModel):
    """Per-category test count summary."""
    report_id: str = ""
    applicability_reason: str = ""

    # QA Meta Attributes
    metadata_tests: int = 0
    header_tests: int = 0
    selection_tests: int = 0
    column_tests: int = 0
    logic_tests: int = 0
    format_tests: int = 0
    sort_tests: int = 0
    control_break_tests: int = 0
    total_tests: int = 0
    count_tests: int = 0
    layout_tests: int = 0
    output_tests: int = 0
    special_processing_tests: int = 0
    report_layout_tests: int = 0
    report_label_tests: int = 0
    date_format_tests: int = 0
    null_handling_tests: int = 0
    trim_handling_tests: int = 0
    database_validation_tests: int = 0
    parameter_tests: int = 0
    parameter_sql_tests: int = 0
    duplicate_data_tests: int = 0
    no_data_tests: int = 0
    total_generated_ut_cases: int = 0


class TestSuite(BaseModel):
    """
    Complete test suite output for a Cognos report definition.

    This is the final product of the generation pipeline, containing
    everything needed for QA export and review.
    """
    report_id: str = ""
    report_title: str = ""
    test_cases: list[CognosTestCase] = Field(default_factory=list)
    coverage: CoverageReport = Field(default_factory=CoverageReport)
    quality_report: SpecificationQualityReport = Field(default_factory=SpecificationQualityReport)
    traceability_matrix: list[TraceabilityEntry] = Field(default_factory=list)
    summary: TestSuiteSummary = Field(default_factory=TestSuiteSummary)
    generation_warnings: list[str] = Field(default_factory=list)
    generation_version: str = "1.0"

    def get_tests_by_category(self, category: str) -> list[CognosTestCase]:
        return [tc for tc in self.test_cases if tc.category == category]

    def compute_summary(self) -> None:
        """Populate the summary from current test cases."""
        cat_map = {
            "REPORT_METADATA": "metadata_tests",
            "REPORT_ID": "metadata_tests",
            "REPORT_TITLE": "metadata_tests",
            "REPORT_DESCRIPTION": "metadata_tests",
            "REPORT_SOURCE": "metadata_tests",
            "REPORT_GENERATED_BY": "metadata_tests",
            "REPORT_FREQUENCY": "metadata_tests",
            "HEADER": "header_tests",
            "SELECTION_CRITERIA": "selection_tests",
            "PROMPT": "selection_tests",
            "PARAMETER": "parameter_tests",
            "PARAMETER_SQL": "parameter_sql_tests",
            "COLUMN": "column_tests",
            "COLUMN_LABEL": "report_label_tests",
            "COLUMN_SOURCE": "column_tests",
            "COLUMN_LOGIC": "logic_tests",
            "COLUMN_FORMAT": "format_tests",
            "SORT": "sort_tests",
            "CONTROL_BREAK": "control_break_tests",
            "TOTAL": "total_tests",
            "COUNT": "count_tests",
            "LAYOUT": "layout_tests",
            "REPORT_LAYOUT": "report_layout_tests",
            "PAGINATION": "layout_tests",
            "FOOTER": "layout_tests",
            "OUTPUT_FORMAT": "output_tests",
            "DISTRIBUTION": "output_tests",
            "RETENTION": "output_tests",
            "SPECIAL_PROCESSING": "special_processing_tests",
            "BUSINESS_RULE": "logic_tests",
            "DATA_MAPPING": "column_tests",
            "DATABASE_MAPPING": "database_validation_tests",
            "DATE_FORMAT": "date_format_tests",
            "NULL_HANDLING": "null_handling_tests",
            "TRIM_HANDLING": "trim_handling_tests",
            "DUPLICATE_DATA": "duplicate_data_tests",
            "NO_DATA": "no_data_tests",
            "REPORT_LABEL": "report_label_tests",
            "REPORT_NAME": "metadata_tests",
            "CONFIGURATION": "metadata_tests",
            "METADATA": "metadata_tests",
        }
        self.summary = TestSuiteSummary(
            report_id=self.report_id,
            report_title=self.report_title,
        )
        for tc in self.test_cases:
            attr = cat_map.get(tc.category, "column_tests")
            current = getattr(self.summary, attr, 0)
            setattr(self.summary, attr, current + 1)
        self.summary.total_generated_ut_cases = len(self.test_cases)
