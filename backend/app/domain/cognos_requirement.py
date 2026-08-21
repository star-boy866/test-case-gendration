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
from typing import Optional, Any, TYPE_CHECKING
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.domain.cognos_models import ReportDefinition

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
    traceability_details: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    is_ambiguous: bool = False
    open_questions: list[str] = Field(default_factory=list)

    # Added for Phase 10.2
    evidence_references: list[Any] = Field(default_factory=list) # Using Any here to avoid circular imports, but it's a list[SourceReference]

    # --- Duplication & Coverage Engine State ---
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


class FeatureEvidence(BaseModel):
    """Detailed evidence tracing why a feature is deemed applicable."""
    feature_name: str
    reason: str
    source_section: str
    semantic_evidence: list[str]
    confidence: RequirementConfidence


class ReportFeatures(BaseModel):
    """
    High-level semantic traits of a report, derived from its requirements and raw definitions.
    Used by the rules engine to deterministically apply methodology patterns.

    Phase 11: has_no_data_evidence added for No Data Validation trigger.
    """
    has_layout: Optional[FeatureEvidence] = None
    has_labels: Optional[FeatureEvidence] = None
    has_sorting: Optional[FeatureEvidence] = None
    has_script_output: Optional[FeatureEvidence] = None
    has_metadata: Optional[FeatureEvidence] = None
    has_selection_criteria: Optional[FeatureEvidence] = None
    has_parameters: Optional[FeatureEvidence] = None
    has_no_data_evidence: Optional[FeatureEvidence] = None   # Phase 11
    has_date_formatting: Optional[FeatureEvidence] = None
    has_control_breaks: Optional[FeatureEvidence] = None
    has_counts_or_totals: Optional[FeatureEvidence] = None
    has_source_columns: Optional[FeatureEvidence] = None
    has_lookup_semantics: Optional[FeatureEvidence] = None
    has_distribution: Optional[FeatureEvidence] = None
    has_delivery_destination: Optional[FeatureEvidence] = None

    @classmethod
    def extract(cls, requirements: list[CognosRequirement], report_def: 'ReportDefinition') -> 'ReportFeatures':
        """Extract features directly from both the structural definition and the requirement list.
        
        Phase 11: Widened triggering for Layout, Control Break, Lookup, No Data, 
        Scheduled Execution, and Output Delivery to handle NH MMIS DSD structures
        where some structural fields may be empty but requirements carry the evidence.
        """
        f = cls()

        # ── 1. LAYOUT ────────────────────────────────────────────────────────
        # Trigger from presentation_type_str, header_elements, OR simply from
        # the existence of report_fields (every column report has a layout).
        layout_evidence: list[str] = []
        if report_def.layout.presentation_type_str:
            layout_evidence.append(f"Presentation: {report_def.layout.presentation_type_str}")
        if getattr(report_def.layout, 'header_elements', None):
            layout_evidence.extend([e.element_name for e in report_def.layout.header_elements[:2]])
        if report_def.report_fields:
            layout_evidence.append(f"{len(report_def.report_fields)} report body fields define layout structure")
        # Also check LAYOUT, HEADER, FOOTER requirements directly
        layout_req_evidence = [
            r.requirement_text for r in requirements
            if r.category in (RequirementCategory.LAYOUT, RequirementCategory.HEADER, RequirementCategory.FOOTER)
        ]
        layout_evidence.extend(layout_req_evidence[:2])
        
        if layout_evidence:
            f.has_layout = FeatureEvidence(
                feature_name="has_layout",
                reason="Explicit Layout formatting, Presentation Type, or report body fields detected in DSD.",
                source_section="Report Layout / Report Body",
                semantic_evidence=layout_evidence[:4],
                confidence=RequirementConfidence.HIGH
            )

        # ── 2. LABELS ─────────────────────────────────────────────────────────
        if report_def.report_fields:
            labels = [field.business_label for field in report_def.report_fields if field.business_label]
            if labels:
                f.has_labels = FeatureEvidence(
                    feature_name="has_labels",
                    reason="Explicit report fields/columns with business labels found.",
                    source_section="Report Specification",
                    semantic_evidence=labels[:5],
                    confidence=RequirementConfidence.HIGH
                )

        # ── 3. SORTING ────────────────────────────────────────────────────────
        if report_def.sort_definitions:
            sorts = [f"{s.field} {s.direction.value}" for s in report_def.sort_definitions]
            f.has_sorting = FeatureEvidence(
                feature_name="has_sorting",
                reason="Explicit Sort By definitions detected.",
                source_section="Sorts",
                semantic_evidence=sorts,
                confidence=RequirementConfidence.HIGH
            )
        else:
            # Fallback: SORT requirements
            sort_reqs = [r for r in requirements if r.category == RequirementCategory.SORT]
            if sort_reqs:
                f.has_sorting = FeatureEvidence(
                    feature_name="has_sorting",
                    reason="Sort requirements detected in RequirementSet.",
                    source_section="Report Sorts",
                    semantic_evidence=[r.requirement_text for r in sort_reqs[:3]],
                    confidence=RequirementConfidence.HIGH
                )

        # ── 4. CONTROL BREAKS ─────────────────────────────────────────────────
        # Phase 11: Also check CONTROL_BREAK requirements directly, not just struct.
        if report_def.control_break_definitions:
            breaks = [f"{b.break_type}: {b.field}" for b in report_def.control_break_definitions]
            f.has_control_breaks = FeatureEvidence(
                feature_name="has_control_breaks",
                reason="Explicit Control Break definitions detected in ReportDefinition.",
                source_section="Control Breaks",
                semantic_evidence=breaks,
                confidence=RequirementConfidence.HIGH
            )
        else:
            # Fallback: CONTROL_BREAK requirements
            cb_reqs = [r for r in requirements if r.category == RequirementCategory.CONTROL_BREAK]
            if cb_reqs:
                f.has_control_breaks = FeatureEvidence(
                    feature_name="has_control_breaks",
                    reason="Control break requirements detected in RequirementSet.",
                    source_section="Report Control Breaks",
                    semantic_evidence=[r.requirement_text for r in cb_reqs[:3]],
                    confidence=RequirementConfidence.HIGH
                )

        # ── 5. COUNTS & TOTALS ────────────────────────────────────────────────
        if report_def.count_definitions or report_def.total_definitions:
            counts = [c.description for c in report_def.count_definitions] + [t.description for t in report_def.total_definitions]
            f.has_counts_or_totals = FeatureEvidence(
                feature_name="has_counts_or_totals",
                reason="Explicit Count or Total definitions detected.",
                source_section="Totals & Counts",
                semantic_evidence=counts,
                confidence=RequirementConfidence.HIGH
            )
        else:
            # Fallback: COUNT / TOTAL requirements
            ct_reqs = [r for r in requirements if r.category in (RequirementCategory.COUNT, RequirementCategory.TOTAL)]
            if ct_reqs:
                f.has_counts_or_totals = FeatureEvidence(
                    feature_name="has_counts_or_totals",
                    reason="Count/Total requirements detected in RequirementSet.",
                    source_section="Report Totals",
                    semantic_evidence=[r.requirement_text for r in ct_reqs[:3]],
                    confidence=RequirementConfidence.HIGH
                )

        # ── 6. SCRIPT OUTPUT ──────────────────────────────────────────────────
        if report_def.output.formats or report_def.output.retention:
            f.has_script_output = FeatureEvidence(
                feature_name="has_script_output",
                reason="Report output formats or retention rules were discovered.",
                source_section="Output",
                semantic_evidence=report_def.output.formats + ([report_def.output.retention] if report_def.output.retention else []),
                confidence=RequirementConfidence.HIGH
            )
        else:
            # Fallback: OUTPUT_FORMAT / RETENTION requirements
            out_reqs = [r for r in requirements if r.category in (RequirementCategory.OUTPUT_FORMAT, RequirementCategory.RETENTION)]
            if out_reqs:
                f.has_script_output = FeatureEvidence(
                    feature_name="has_script_output",
                    reason="Output/Retention requirements detected in RequirementSet.",
                    source_section="Report Output",
                    semantic_evidence=[r.requirement_text for r in out_reqs[:3]],
                    confidence=RequirementConfidence.HIGH
                )

        # ── 7. METADATA ───────────────────────────────────────────────────────
        if report_def.metadata.report_id or report_def.metadata.report_title:
            f.has_metadata = FeatureEvidence(
                feature_name="has_metadata",
                reason="Report explicitly defines title, description, and core metadata.",
                source_section="Report Metadata",
                semantic_evidence=[report_def.metadata.report_id, report_def.metadata.report_title],
                confidence=RequirementConfidence.HIGH
            )

        # ── 8. SELECTION CRITERIA ─────────────────────────────────────────────
        if report_def.selection_criteria:
            crit = [c.field for c in report_def.selection_criteria]
            f.has_selection_criteria = FeatureEvidence(
                feature_name="has_selection_criteria",
                reason="Report features selection criteria.",
                source_section="Selection Criteria",
                semantic_evidence=crit,
                confidence=RequirementConfidence.HIGH
            )
        else:
            sel_reqs = [r for r in requirements if r.category == RequirementCategory.SELECTION_CRITERIA]
            if sel_reqs:
                f.has_selection_criteria = FeatureEvidence(
                    feature_name="has_selection_criteria",
                    reason="Selection criteria requirements detected.",
                    source_section="Report Selection Criteria",
                    semantic_evidence=[r.requirement_text for r in sel_reqs[:3]],
                    confidence=RequirementConfidence.HIGH
                )

        # ── 9. PARAMETERS ─────────────────────────────────────────────────────
        if report_def.parameters:
            params = [p.parameter_name for p in report_def.parameters]
            f.has_parameters = FeatureEvidence(
                feature_name="has_parameters",
                reason="Report features parameters.",
                source_section="Parameters",
                semantic_evidence=params,
                confidence=RequirementConfidence.HIGH
            )

        # ── 10. DISTRIBUTION / SCHEDULING ────────────────────────────────────
        # Phase 11: Widen to also trigger from REPORT_FREQUENCY requirements.
        dist_evidence: list[str] = []
        if report_def.metadata.frequency_type and report_def.metadata.frequency_type.lower() not in ("unknown", "", "not specified"):
            dist_evidence.append(f"Frequency: {report_def.metadata.frequency_type}")
        if report_def.output.distribution_enabled or report_def.output.distribution:
            dist_evidence.append(f"Distribution: {report_def.output.distribution}")
        
        # Fallback: REPORT_FREQUENCY or DISTRIBUTION requirements
        freq_reqs = [r for r in requirements if r.category in (RequirementCategory.REPORT_FREQUENCY, RequirementCategory.DISTRIBUTION)]
        for r in freq_reqs:
            dist_evidence.append(r.requirement_text)

        if dist_evidence:
            f.has_distribution = FeatureEvidence(
                feature_name="has_distribution",
                reason="Report defines distribution, frequency, or scheduling logic.",
                source_section="Output / Metadata",
                semantic_evidence=dist_evidence[:3],
                confidence=RequirementConfidence.HIGH
            )

        # ── 11. DELIVERY DESTINATION ──────────────────────────────────────────
        # Phase 11: Widen to trigger from OUTPUT_FORMAT (EDMS/SDR/portal) and RETENTION.
        delivery_evidence: list[str] = []
        if report_def.output.reporting_portal:
            delivery_evidence.append(f"Reporting Portal: {report_def.output.reporting_portal}")
        
        portal_keywords = ("sdr", "edms", "portal", "delivery", "deliver")
        delivery_reqs = [
            r for r in requirements
            if r.category in (RequirementCategory.OUTPUT_FORMAT, RequirementCategory.RETENTION, RequirementCategory.DISTRIBUTION)
            and any(kw in (r.requirement_text or "").lower() for kw in portal_keywords)
        ]
        for r in delivery_reqs:
            delivery_evidence.append(r.requirement_text)

        if delivery_evidence:
            f.has_delivery_destination = FeatureEvidence(
                feature_name="has_delivery_destination",
                reason="Delivery destination semantics found.",
                source_section="Output / Retention",
                semantic_evidence=delivery_evidence[:3],
                confidence=RequirementConfidence.HIGH
            )

        # ── 12. Deep requirements scan (Date Formatting, Source Cols, Lookups, No Data) ───
        date_ev: list[str] = []
        source_cols: list[str] = []
        lookup_ev: list[str] = []
        no_data_ev: list[str] = []
        
        # Lookup code-field suffixes requiring corroboration
        _LOOKUP_SUFFIXES = (" cd", "_cd", " stat", "_stat", " ind", "_ind", " typ", "_typ")

        for r in requirements:
            cat = r.category
            text = (r.requirement_text or "").lower()
            proc = (r.processing_rule or "").lower()
            fmt = (r.formatting_rule or "").lower()
            logic = getattr(r, "source_logic_type", SourceLogicType.UNKNOWN)
            field_name_lower = (r.field or r.business_label or "").lower()

            # Date formatting
            if not f.has_date_formatting:
                if (cat == RequirementCategory.COLUMN_FORMAT and ("date" in fmt or "date" in text)) or \
                   (cat == RequirementCategory.COLUMN and (fmt or "date" in proc or "format" in proc)):
                    date_ev.append(r.requirement_text)

            # Source columns
            if cat in (RequirementCategory.COLUMN_SOURCE, RequirementCategory.COLUMN) or \
               "duplicate" in text or "distinct" in text:
                source_cols.append(r.field)

            # ── LOOKUP (Phase 11 strict rules) ────────────────────────────────
            # Only trigger if there is corroborating evidence beyond the suffix alone.
            is_lookup = False
            if logic == SourceLogicType.LOOKUP:
                is_lookup = True
            elif "lookup" in text:
                is_lookup = True
            elif "description" in text and cat in (RequirementCategory.COLUMN_LOGIC, RequirementCategory.BUSINESS_RULE):
                is_lookup = True
            elif any(field_name_lower.endswith(sfx) for sfx in _LOOKUP_SUFFIXES):
                # Suffix-based: only accept if processing_rule or requirement_text provides corroboration
                corroborating_keywords = ("description", "lookup", "code", "indicator", "resolve", "translate", "valid value")
                if any(kw in text or kw in proc for kw in corroborating_keywords):
                    is_lookup = True
            
            if is_lookup:
                lookup_ev.append(r.requirement_text)

            # ── NO DATA (Phase 11) ────────────────────────────────────────────
            # Detect no-data evidence from SPECIAL_PROCESSING requirements, even
            # when selection_criteria is absent from the structural model.
            if not f.has_no_data_evidence:
                if cat == RequirementCategory.SPECIAL_PROCESSING and ("no data" in text or "no record" in text or "empty" in text):
                    no_data_ev.append(r.requirement_text)
                elif "no data" in text and cat in (RequirementCategory.COLUMN, RequirementCategory.BUSINESS_RULE):
                    no_data_ev.append(r.requirement_text)

            # ── DISTRIBUTION FALLBACK ─────────────────────────────────────────
            if not f.has_distribution:
                if "box" in text or "scheduler" in text or cat in (RequirementCategory.DISTRIBUTION, RequirementCategory.REPORT_FREQUENCY):
                    f.has_distribution = FeatureEvidence(
                        feature_name="has_distribution",
                        reason="Scheduling/distribution semantics detected in requirements text.",
                        source_section=r.source_section,
                        semantic_evidence=[r.requirement_text],
                        confidence=RequirementConfidence.MEDIUM
                    )

            # ── DELIVERY FALLBACK ─────────────────────────────────────────────
            if not f.has_delivery_destination:
                if "sdr" in text or "edms" in text or "delivery" in text or "deliver" in text:
                    f.has_delivery_destination = FeatureEvidence(
                        feature_name="has_delivery_destination",
                        reason="Delivery destination detected in requirements text.",
                        source_section=r.source_section,
                        semantic_evidence=[r.requirement_text],
                        confidence=RequirementConfidence.MEDIUM
                    )

        if date_ev:
            f.has_date_formatting = FeatureEvidence(
                feature_name="has_date_formatting",
                reason="Date formatting logic found in fields.",
                source_section="Report Specification",
                semantic_evidence=date_ev[:3],
                confidence=RequirementConfidence.HIGH
            )

        if source_cols:
            f.has_source_columns = FeatureEvidence(
                feature_name="has_source_columns",
                reason="Report relies on specific source columns mapped from a database.",
                source_section="Report Specification",
                semantic_evidence=source_cols[:3],
                confidence=RequirementConfidence.HIGH
            )

        if lookup_ev:
            f.has_lookup_semantics = FeatureEvidence(
                feature_name="has_lookup_semantics",
                reason="Explicit lookup tables, code/description resolution, or indicator translation detected.",
                source_section="Report Specification",
                semantic_evidence=lookup_ev[:3],
                confidence=RequirementConfidence.HIGH
            )

        if no_data_ev:
            f.has_no_data_evidence = FeatureEvidence(
                feature_name="has_no_data_evidence",
                reason="Special processing or business rules define no-data behavior.",
                source_section="Report Special Processing",
                semantic_evidence=no_data_ev[:3],
                confidence=RequirementConfidence.MEDIUM
            )

        return f
