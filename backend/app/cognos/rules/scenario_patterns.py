"""
Golden Methodology Scenario Pattern Engine.

Defines the 14 Golden Methodology patterns from the PRV-INT-027 UT Document
and provides the applicability rules to determine which patterns are required
based on the DSD evidence.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

from app.domain.cognos_requirement import CognosRequirement, RequirementCategory
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
    LOOKUP_DESCRIPTION_VALIDATION = "LOOKUP_DESCRIPTION_VALIDATION"
    BOX_EXECUTION_VALIDATION = "BOX_EXECUTION_VALIDATION"
    SDR_DELIVERY_VALIDATION = "SDR_DELIVERY_VALIDATION"
    DB_REPORT_DATA_VALIDATION = "DB_REPORT_DATA_VALIDATION"


@dataclass
class ApplicablePattern:
    """A pattern that applies to the current DSD with the linked requirements."""
    pattern: MethodologyPattern
    requirements: list[CognosRequirement] = field(default_factory=list)


def discover_applicable_patterns(requirements: list[CognosRequirement]) -> list[ApplicablePattern]:
    """
    Evaluate the requirement set to determine which of the 14 Golden Patterns apply.
    Returns a list of ApplicablePattern with the linked requirements.
    """
    applicable_patterns: dict[MethodologyPattern, list[CognosRequirement]] = {}
    
    def _add_req(pattern: MethodologyPattern, req: CognosRequirement):
        if pattern not in applicable_patterns:
            applicable_patterns[pattern] = []
        applicable_patterns[pattern].append(req)

    for req in requirements:
        cat = req.category
        logic_type = getattr(req, "source_logic_type", SourceLogicType.UNKNOWN)

        # Pattern 1: LAYOUT_VALIDATION
        if cat in (RequirementCategory.LAYOUT, RequirementCategory.HEADER, RequirementCategory.FOOTER, RequirementCategory.PAGINATION):
            _add_req(MethodologyPattern.LAYOUT_VALIDATION, req)

        # Pattern 2: LABEL_VALIDATION
        if cat == RequirementCategory.COLUMN_LABEL or cat == RequirementCategory.COLUMN:
            _add_req(MethodologyPattern.LABEL_VALIDATION, req)

        # Pattern 3: SORT_VALIDATION
        if cat == RequirementCategory.SORT:
            _add_req(MethodologyPattern.SORT_VALIDATION, req)

        # Pattern 4: SCRIPT_OUTPUT_VALIDATION
        if cat == RequirementCategory.OUTPUT_FORMAT or cat == RequirementCategory.RETENTION:
            _add_req(MethodologyPattern.SCRIPT_OUTPUT_VALIDATION, req)
        elif "script" in (req.requirement_text or "").lower():
            _add_req(MethodologyPattern.SCRIPT_OUTPUT_VALIDATION, req)

        # Pattern 5: REPORT_NAME_DESCRIPTION_VALIDATION
        if cat in (RequirementCategory.REPORT_METADATA, RequirementCategory.REPORT_ID, RequirementCategory.REPORT_TITLE, RequirementCategory.REPORT_DESCRIPTION):
            _add_req(MethodologyPattern.REPORT_NAME_DESCRIPTION_VALIDATION, req)

        # Pattern 6: NO_DATA_VALIDATION
        if cat in (RequirementCategory.SPECIAL_PROCESSING, RequirementCategory.COLUMN):
            if "no data" in (req.requirement_text or "").lower():
                _add_req(MethodologyPattern.NO_DATA_VALIDATION, req)

        # Pattern 7: DATE_FORMAT_VALIDATION
        if cat == RequirementCategory.COLUMN_FORMAT and ("date" in (req.formatting_rule or "").lower() or "date" in (req.requirement_text or "").lower()):
            _add_req(MethodologyPattern.DATE_FORMAT_VALIDATION, req)

        # Pattern 8: CONTROL_BREAK_VALIDATION
        if cat == RequirementCategory.CONTROL_BREAK:
            _add_req(MethodologyPattern.CONTROL_BREAK_VALIDATION, req)

        # Pattern 9: DB_COUNT_VALIDATION
        if cat == RequirementCategory.COUNT or cat == RequirementCategory.TOTAL:
            _add_req(MethodologyPattern.DB_COUNT_VALIDATION, req)
        elif "count" in (req.requirement_text or "").lower() and cat == RequirementCategory.BUSINESS_RULE:
            _add_req(MethodologyPattern.DB_COUNT_VALIDATION, req)

        # Pattern 10: DUPLICATE_VALIDATION
        if "duplicate" in (req.requirement_text or "").lower() or "distinct" in (req.requirement_text or "").lower():
            _add_req(MethodologyPattern.DUPLICATE_VALIDATION, req)

        # Pattern 11: LOOKUP_DESCRIPTION_VALIDATION
        if logic_type == SourceLogicType.LOOKUP or "lookup" in (req.requirement_text or "").lower() or ("description" in (req.requirement_text or "").lower() and cat in (RequirementCategory.COLUMN_LOGIC, RequirementCategory.BUSINESS_RULE)):
            _add_req(MethodologyPattern.LOOKUP_DESCRIPTION_VALIDATION, req)

        # Pattern 12: BOX_EXECUTION_VALIDATION
        if "box" in (req.requirement_text or "").lower() or "scheduler" in (req.requirement_text or "").lower() or cat == RequirementCategory.DISTRIBUTION:
            _add_req(MethodologyPattern.BOX_EXECUTION_VALIDATION, req)

        # Pattern 13: SDR_DELIVERY_VALIDATION
        if "sdr" in (req.requirement_text or "").lower() or "edms" in (req.requirement_text or "").lower() or "delivery" in (req.requirement_text or "").lower() or "deliver" in (req.requirement_text or "").lower():
            _add_req(MethodologyPattern.SDR_DELIVERY_VALIDATION, req)

        # Pattern 14: DB_REPORT_DATA_VALIDATION
        if cat in (RequirementCategory.COLUMN_SOURCE, RequirementCategory.COLUMN_LOGIC, RequirementCategory.COLUMN):
            _add_req(MethodologyPattern.DB_REPORT_DATA_VALIDATION, req)

    results = []
    for pattern, reqs in applicable_patterns.items():
        results.append(ApplicablePattern(pattern=pattern, requirements=reqs))
    
    return results
