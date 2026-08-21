"""
Golden Methodology Scenario Pattern Engine — PHASE 11.

Defines the 14 Golden Methodology patterns from the developer UT methodology
reference and provides the applicability rules to determine which patterns are
required based on the DSD evidence for the CURRENT report.

Phase 11 additions:
  - ApplicablePattern now carries evidence_source, supporting_sections,
    and supporting_requirement_ids for full provenance tracing.
  - discover_applicable_patterns() returns a MethodologyApplicabilityReport
    containing both GENERATED and NOT_GENERATED entries.
  - Evidence sources are: 'DSD', 'Technical UT', 'Derived Developer Methodology'.

Zero report-specific hardcoding. Works for any NH MMIS Cognos DSD.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, Any

from app.domain.cognos_requirement import CognosRequirement, RequirementCategory, ReportFeatures, RequirementConfidence
from app.domain.cognos_models import SourceLogicType


class MethodologyPattern(str, Enum):
    LAYOUT_VALIDATION = "LAYOUT_VALIDATION"
    LABEL_VALIDATION = "LABEL_VALIDATION"
    SORT_VALIDATION = "SORT_VALIDATION"
    SCRIPT_OUTPUT_VALIDATION = "SCRIPT_OUTPUT_VALIDATION"
    REPORT_NAME_DESCRIPTION_VALIDATION = "REPORT_NAME_DESCRIPTION_VALIDATION"
    NO_DATA_VALIDATION = "NO_DATA_VALIDATION"
    DATE_FORMAT_VALIDATION = "DATE_FORMAT_VALIDATION"
    CONTROL_BREAK_VALIDATION = "CONTROL_BREAK_VALIDATION"
    DB_COUNT_VALIDATION = "DB_COUNT_VALIDATION"
    DUPLICATE_VALIDATION = "DUPLICATE_VALIDATION"
    LOOKUP_VALIDATION = "LOOKUP_VALIDATION"
    BOX_EXECUTION_VALIDATION = "BOX_EXECUTION_VALIDATION"  # Deprecated
    SDR_DELIVERY_VALIDATION = "SDR_DELIVERY_VALIDATION"  # Deprecated
    SCHEDULED_EXECUTION_VALIDATION = "SCHEDULED_EXECUTION_VALIDATION"
    OUTPUT_DELIVERY_VALIDATION = "OUTPUT_DELIVERY_VALIDATION"
    DB_REPORT_DATA_VALIDATION = "DB_REPORT_DATA_VALIDATION"


@dataclass
class ApplicablePattern:
    """A pattern that applies to the current DSD with the linked requirements."""
    pattern: MethodologyPattern
    requirements: list[CognosRequirement] = field(default_factory=list)
    applicable_reason: str = ""
    confidence: RequirementConfidence = RequirementConfidence.HIGH
    # Phase 11: Evidence provenance fields
    evidence_source: str = "DSD"          # 'DSD' | 'Technical UT' | 'Derived Developer Methodology'
    supporting_sections: list[str] = field(default_factory=list)
    supporting_requirement_ids: list[str] = field(default_factory=list)


@dataclass
class NotApplicablePattern:
    """A pattern that does NOT apply, with the reason why."""
    pattern: MethodologyPattern
    reason: str
    confidence: RequirementConfidence = RequirementConfidence.HIGH


@dataclass
class MethodologyApplicabilityReport:
    """Full applicability report: GENERATED + NOT GENERATED entries."""
    generated: list[ApplicablePattern] = field(default_factory=list)
    not_generated: list[NotApplicablePattern] = field(default_factory=list)

    def applicable_patterns(self) -> list[ApplicablePattern]:
        return self.generated


@dataclass
class MethodologyRule:
    """A generic methodology applicability rule."""
    pattern: MethodologyPattern
    predicate: Callable[[ReportFeatures], bool]
    reason_template: str
    confidence: RequirementConfidence
    requirement_filter: Callable[[CognosRequirement], bool]
    not_applicable_reason: str = ""   # Phase 11: why it's NOT generated when predicate fails


# ---------------------------------------------------------------------------
# Generic Rule Catalog
# ---------------------------------------------------------------------------
METHODOLOGY_RULES = [
    MethodologyRule(
        pattern=MethodologyPattern.LAYOUT_VALIDATION,
        predicate=lambda f: bool(f.has_layout),
        reason_template="Report semantics dictate explicit layout, header, footer, or pagination formatting.",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: r.category in (RequirementCategory.LAYOUT, RequirementCategory.HEADER, RequirementCategory.FOOTER, RequirementCategory.PAGINATION, RequirementCategory.COLUMN),
        not_applicable_reason="No layout, header, footer, or pagination formatting detected in DSD."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.LABEL_VALIDATION,
        predicate=lambda f: bool(f.has_labels),
        reason_template="Report contains explicit column or field labels.",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: r.category in (RequirementCategory.COLUMN_LABEL, RequirementCategory.COLUMN),
        not_applicable_reason="No explicit field or column labels detected in DSD."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.SORT_VALIDATION,
        predicate=lambda f: bool(f.has_sorting),
        reason_template="Report defines specific sort orders.",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: r.category == RequirementCategory.SORT,
        not_applicable_reason="No Sort By definitions detected in DSD."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.SCRIPT_OUTPUT_VALIDATION,
        predicate=lambda f: bool(f.has_script_output),
        reason_template="Report output formats, scripts, or retention rules were discovered.",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: r.category in (RequirementCategory.OUTPUT_FORMAT, RequirementCategory.RETENTION) or "script" in (r.requirement_text or "").lower(),
        not_applicable_reason="No output format, retention, or script/output rules detected in DSD."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.REPORT_NAME_DESCRIPTION_VALIDATION,
        predicate=lambda f: bool(f.has_metadata),
        reason_template="Report explicitly defines title, description, and core metadata.",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: r.category in (RequirementCategory.REPORT_METADATA, RequirementCategory.REPORT_ID, RequirementCategory.REPORT_TITLE, RequirementCategory.REPORT_DESCRIPTION),
        not_applicable_reason="No report metadata (ID, title, description) detected in DSD."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.NO_DATA_VALIDATION,
        predicate=lambda f: bool(f.has_selection_criteria or f.has_parameters or f.has_no_data_evidence),
        reason_template="Report features selection criteria or parameters, necessitating empty-set boundary testing.",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: r.category in (RequirementCategory.SELECTION_CRITERIA, RequirementCategory.PARAMETER) or (r.category in (RequirementCategory.SPECIAL_PROCESSING, RequirementCategory.COLUMN) and "no data" in (r.requirement_text or "").lower()),
        not_applicable_reason="No selection criteria, parameters, or no-data special processing detected."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.DATE_FORMAT_VALIDATION,
        predicate=lambda f: bool(f.has_date_formatting),
        reason_template="Report semantic extraction found specific Date formatting requirements.",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: bool((r.category == RequirementCategory.COLUMN_FORMAT and ("date" in (r.formatting_rule or "").lower() or "date" in (r.requirement_text or "").lower())) or (r.category == RequirementCategory.COLUMN and (r.formatting_rule or "date" in (r.processing_rule or "").lower() or "format" in (r.processing_rule or "").lower()))),
        not_applicable_reason="No date-formatted columns detected in DSD."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.CONTROL_BREAK_VALIDATION,
        predicate=lambda f: bool(f.has_control_breaks),
        reason_template="Report explicitly outlines page or section control breaks.",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: r.category == RequirementCategory.CONTROL_BREAK,
        not_applicable_reason="No control break definitions detected in DSD (control break rows may be empty template rows)."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.DB_COUNT_VALIDATION,
        predicate=lambda f: bool(f.has_counts_or_totals),
        reason_template="Totals, subtotals, or count checks exist in the DSD.",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: r.category in (RequirementCategory.COUNT, RequirementCategory.TOTAL) or ("count" in (r.requirement_text or "").lower() and r.category == RequirementCategory.BUSINESS_RULE),
        not_applicable_reason="No Count or Total definitions detected in DSD."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.DUPLICATE_VALIDATION,
        predicate=lambda f: bool(f.has_source_columns),
        reason_template="Report pulls tabular data from a database; duplicate records must be verified.",
        confidence=RequirementConfidence.MEDIUM,
        requirement_filter=lambda r: False,  # Duplicates don't map individual column requirements
        not_applicable_reason="No source column mappings detected; cannot verify deduplication."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.LOOKUP_VALIDATION,
        predicate=lambda f: bool(f.has_lookup_semantics),
        reason_template="Discovered lookup tables or code/indicator translation logic.",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: getattr(r, "source_logic_type", SourceLogicType.UNKNOWN) == SourceLogicType.LOOKUP or "lookup" in (r.requirement_text or "").lower() or ("description" in (r.requirement_text or "").lower() and r.category in (RequirementCategory.COLUMN_LOGIC, RequirementCategory.BUSINESS_RULE)),
        not_applicable_reason="No lookup semantics, code/description mappings, or indicator fields detected in DSD."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.SCHEDULED_EXECUTION_VALIDATION,
        predicate=lambda f: bool(f.has_distribution),
        reason_template="Report requires scheduled execution or frequency distribution.",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: "box" in (r.requirement_text or "").lower() or "scheduler" in (r.requirement_text or "").lower() or r.category in (RequirementCategory.DISTRIBUTION, RequirementCategory.REPORT_FREQUENCY),
        not_applicable_reason="No scheduling, frequency, or distribution configuration detected in DSD."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.OUTPUT_DELIVERY_VALIDATION,
        predicate=lambda f: bool(f.has_delivery_destination),
        reason_template="Delivery destination semantics found (e.g. SDR, EDMS, web portal).",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: "sdr" in (r.requirement_text or "").lower() or "edms" in (r.requirement_text or "").lower() or "delivery" in (r.requirement_text or "").lower() or "deliver" in (r.requirement_text or "").lower() or r.category in (RequirementCategory.DISTRIBUTION, RequirementCategory.RETENTION),
        not_applicable_reason="No delivery destination (SDR, EDMS, portal) detected in DSD."
    ),
    MethodologyRule(
        pattern=MethodologyPattern.DB_REPORT_DATA_VALIDATION,
        predicate=lambda f: bool(f.has_source_columns),
        reason_template="Primary source column mappings exist; end-to-end data fidelity must be verified.",
        confidence=RequirementConfidence.HIGH,
        requirement_filter=lambda r: r.category in (RequirementCategory.COLUMN_SOURCE, RequirementCategory.COLUMN, RequirementCategory.COLUMN_LOGIC),
        not_applicable_reason="No source column mappings detected in DSD; DB data validation cannot be performed."
    )
]


def discover_applicable_patterns(
    requirements: list[CognosRequirement],
    report_def: Any = None
) -> MethodologyApplicabilityReport:
    """
    Phase 11: Evaluate the requirement set against all 14 Golden Methodology Patterns.

    Returns a MethodologyApplicabilityReport containing:
      - generated: ApplicablePattern list (each carrying evidence_source, supporting_sections,
        supporting_requirement_ids) for patterns whose predicate is True.
      - not_generated: NotApplicablePattern list with reason why each pattern did not apply.

    This enables the pipeline to print a complete methodology applicability report.
    Uses generic ReportFeatures — zero report-specific hardcoding.
    """
    if report_def:
        features = ReportFeatures.extract(requirements, report_def)
    else:
        from app.domain.cognos_models import ReportDefinition, ReportMetadata, LayoutDefinition, OutputDefinition
        features = ReportFeatures.extract(requirements, ReportDefinition(metadata=ReportMetadata(), layout=LayoutDefinition(), output=OutputDefinition()))

    # Map pattern → FeatureEvidence accessor
    feature_map = {
        MethodologyPattern.LAYOUT_VALIDATION:                  lambda f: f.has_layout,
        MethodologyPattern.LABEL_VALIDATION:                   lambda f: f.has_labels,
        MethodologyPattern.SORT_VALIDATION:                    lambda f: f.has_sorting,
        MethodologyPattern.SCRIPT_OUTPUT_VALIDATION:           lambda f: f.has_script_output,
        MethodologyPattern.REPORT_NAME_DESCRIPTION_VALIDATION: lambda f: f.has_metadata,
        MethodologyPattern.NO_DATA_VALIDATION:                 lambda f: f.has_selection_criteria or f.has_parameters or f.has_no_data_evidence,
        MethodologyPattern.DATE_FORMAT_VALIDATION:             lambda f: f.has_date_formatting,
        MethodologyPattern.CONTROL_BREAK_VALIDATION:           lambda f: f.has_control_breaks,
        MethodologyPattern.DB_COUNT_VALIDATION:                lambda f: f.has_counts_or_totals,
        MethodologyPattern.DUPLICATE_VALIDATION:               lambda f: f.has_source_columns,
        MethodologyPattern.LOOKUP_VALIDATION:                  lambda f: f.has_lookup_semantics,
        MethodologyPattern.SCHEDULED_EXECUTION_VALIDATION:     lambda f: f.has_distribution,
        MethodologyPattern.OUTPUT_DELIVERY_VALIDATION:         lambda f: f.has_delivery_destination,
        MethodologyPattern.DB_REPORT_DATA_VALIDATION:          lambda f: f.has_source_columns,
    }

    generated: list[ApplicablePattern] = []
    not_generated: list[NotApplicablePattern] = []

    for rule in METHODOLOGY_RULES:
        evidence = feature_map.get(rule.pattern, lambda f: None)(features) if rule.pattern in feature_map else None
        applies = bool(evidence) if evidence is not None else rule.predicate(features)

        if applies:
            linked_reqs = [r for r in requirements if rule.requirement_filter(r)]

            # Build reason from FeatureEvidence if rich; else use template
            if evidence and hasattr(evidence, 'reason'):
                reason = evidence.reason
                conf = evidence.confidence
                ev_source = "DSD"
                sections = [evidence.source_section] if evidence.source_section else []
                sem_ev = evidence.semantic_evidence or []
                if sem_ev:
                    reason += f" (Evidence: {', '.join(str(e) for e in sem_ev[:3])})"
            else:
                reason = rule.reason_template
                conf = rule.confidence
                ev_source = "Derived Developer Methodology"
                sections = [r.source_section for r in linked_reqs if r.source_section][:3]

            generated.append(ApplicablePattern(
                pattern=rule.pattern,
                requirements=linked_reqs,
                applicable_reason=reason,
                confidence=conf,
                evidence_source=ev_source,
                supporting_sections=list(dict.fromkeys(sections)),
                supporting_requirement_ids=[r.requirement_id for r in linked_reqs if r.requirement_id][:10],
            ))
        else:
            not_generated.append(NotApplicablePattern(
                pattern=rule.pattern,
                reason=rule.not_applicable_reason or f"Predicate for {rule.pattern.value} evaluated to False.",
                confidence=rule.confidence,
            ))

    return MethodologyApplicabilityReport(generated=generated, not_generated=not_generated)
