"""
Cognos Requirement domain model.

Every requirement extracted from a Cognos Report Definition / Design
Specification is represented as a CognosRequirement with full traceability
back to the source document section and page.

RequirementCategory provides Cognos-specific classification aligned with
how QA testers naturally organize report validation.

HALLUCINATION PREVENTION: Requirements are ONLY created from content
explicitly present in the source document. When information is missing or
ambiguous, the requirement is flagged accordingly — never invented.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from app.domain.cognos_models import SourceLogicType


class TestOrigin(str, Enum):
    DSD_DERIVED = "DSD_DERIVED"
    RISK_DERIVED = "RISK_DERIVED"
    COMMENT_DERIVED = "COMMENT_DERIVED"
    ASSUMPTION_DERIVED = "ASSUMPTION_DERIVED"
    DIRECT_SPECIFICATION = "DIRECT_SPECIFICATION"
    DEV_UT_METHODOLOGY = "DEV_UT_METHODOLOGY"


class RequirementCategory(str, Enum):
    """Cognos-specific requirement categories."""
    # Report-level
    REPORT_METADATA = "REPORT_METADATA"
    REPORT_ID = "REPORT_ID"
    REPORT_TITLE = "REPORT_TITLE"
    REPORT_DESCRIPTION = "REPORT_DESCRIPTION"
    REPORT_SOURCE = "REPORT_SOURCE"
    REPORT_GENERATED_BY = "REPORT_GENERATED_BY"
    REPORT_FREQUENCY = "REPORT_FREQUENCY"

    # Selection / Parameters
    SELECTION_CRITERIA = "SELECTION_CRITERIA"
    PROMPT = "PROMPT"
    PARAMETER = "PARAMETER"

    # Column-level
    HEADER = "HEADER"
    COLUMN = "COLUMN"
    COLUMN_LABEL = "COLUMN_LABEL"
    COLUMN_SOURCE = "COLUMN_SOURCE"
    COLUMN_LOGIC = "COLUMN_LOGIC"
    COLUMN_FORMAT = "COLUMN_FORMAT"

    # Sort / Grouping
    SORT = "SORT"
    CONTROL_BREAK = "CONTROL_BREAK"
    TOTAL = "TOTAL"
    COUNT = "COUNT"

    # Layout / Presentation
    LAYOUT = "LAYOUT"
    PAGINATION = "PAGINATION"
    FOOTER = "FOOTER"

    # Output
    OUTPUT_FORMAT = "OUTPUT_FORMAT"
    DISTRIBUTION = "DISTRIBUTION"
    RETENTION = "RETENTION"

    # Processing
    SPECIAL_PROCESSING = "SPECIAL_PROCESSING"
    BUSINESS_RULE = "BUSINESS_RULE"
    DATA_MAPPING = "DATA_MAPPING"
    DATABASE_MAPPING = "DATABASE_MAPPING"


class RequirementConfidence(str, Enum):
    """How confident the extraction is."""
    HIGH = "High"           # Directly and unambiguously stated
    MEDIUM = "Medium"       # Implied or requires interpretation
    LOW = "Low"             # Ambiguous, partial, or requires confirmation
    UNKNOWN = "Unknown"     # Cannot determine


class CognosRequirement(BaseModel):
    """
    A single extracted requirement from a Cognos Report Definition.

    Every requirement must answer: "Where did this come from?" via the
    source traceability fields.
    """
    requirement_id: str = ""
    report_id: str = ""
    category: RequirementCategory = RequirementCategory.REPORT_METADATA

    # The requirement itself
    field: str = ""                   # Field/element this requirement relates to
    business_label: str = ""          # Display/business label
    requirement_text: str = ""        # Human-readable requirement description
    description: str = ""             # Additional context

    # Source traceability (NON-NEGOTIABLE per spec)
    source_document: str = ""
    source_section: str = ""
    source_page: Optional[int] = None

    # Data mapping
    source_table: str = ""
    source_columns: list[str] = Field(default_factory=list)
    processing_rule: str = ""
    formatting_rule: str = ""
    source_logic_type: SourceLogicType = SourceLogicType.UNKNOWN

    # Status & Origin
    status: str = "EXTRACTED"         # EXTRACTED, VALIDATED, AMBIGUOUS, CONFLICT, REVIEW_REQUIRED
    origin: TestOrigin = TestOrigin.DIRECT_SPECIFICATION

    # Quality indicators
    confidence: RequirementConfidence = RequirementConfidence.HIGH
    is_ambiguous: bool = False
    open_questions: list[str] = Field(default_factory=list)

    # Deduplication & Traceability
    source_references: list[str] = Field(default_factory=list)  # All sections where this was found
    is_duplicate_of: Optional[str] = None  # requirement_id of primary if this is a dup
    mapped_test_case_ids: list[str] = Field(default_factory=list)  # Many-to-many link to test cases

    @property
    def is_complete(self) -> bool:
        """A requirement is complete if it has an ID, text, and source."""
        return bool(self.requirement_id and self.requirement_text and self.source_section)

    @property
    def has_data_mapping(self) -> bool:
        """Whether this requirement has a source table/column mapping."""
        return bool(self.source_table or self.source_columns)


class RequirementSet(BaseModel):
    """Collection of requirements extracted from a single report definition."""
    report_id: str = ""
    source_document: str = ""
    requirements: list[CognosRequirement] = Field(default_factory=list)

    # Extraction summary
    total_extracted: int = 0
    ambiguous_count: int = 0
    open_question_count: int = 0
    duplicate_count: int = 0
    warnings: list[str] = Field(default_factory=list)

    def by_category(self, category: RequirementCategory) -> list[CognosRequirement]:
        """Get all requirements of a specific category."""
        return [r for r in self.requirements if r.category == category]

    def category_counts(self) -> dict[str, int]:
        """Count requirements per category."""
        counts: dict[str, int] = {}
        for req in self.requirements:
            cat = req.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def compute_summary(self) -> None:
        """Recompute summary statistics from current requirements."""
        self.total_extracted = len(self.requirements)
        self.ambiguous_count = sum(1 for r in self.requirements if r.is_ambiguous)
        self.open_question_count = sum(
            len(r.open_questions) for r in self.requirements
        )
        self.duplicate_count = sum(
            1 for r in self.requirements if r.is_duplicate_of is not None
        )
