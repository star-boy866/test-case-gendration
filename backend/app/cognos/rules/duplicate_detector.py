"""
Duplicate detector — prevents generating identical test cases for the
same requirement appearing across multiple document sections.

When the same field/requirement appears in Report Definition, Report
Layout, and Report Specification, this module consolidates them into
one logical test with multiple source references.
"""

from __future__ import annotations

from app.domain.cognos_requirement import CognosRequirement, RequirementSet


def detect_and_mark_duplicates(req_set: RequirementSet) -> list[str]:
    """
    Detect duplicate requirements and mark them.

    A requirement is considered a duplicate if it has the same category,
    field, and semantically equivalent text as another requirement.

    The first occurrence is kept as the primary; duplicates get their
    is_duplicate_of set to the primary's ID, and the primary gains
    additional source_references.

    Returns list of deduplication messages.
    """
    messages: list[str] = []
    seen: dict[str, CognosRequirement] = {}  # key -> primary requirement

    for req in req_set.requirements:
        key = _dedup_key(req)

        if key in seen:
            primary = seen[key]
            req.is_duplicate_of = primary.requirement_id

            # Add this source reference to the primary
            source_ref = f"{req.source_section}"
            if req.source_page:
                source_ref += f" (page {req.source_page})"
            if source_ref not in primary.source_references:
                primary.source_references.append(source_ref)

            messages.append(
                f"Requirement '{req.requirement_id}' is a duplicate of "
                f"'{primary.requirement_id}' ({req.field} in {req.source_section})"
            )
        else:
            seen[key] = req
            source_ref = f"{req.source_section}"
            if req.source_page:
                source_ref += f" (page {req.source_page})"
            req.source_references.append(source_ref)

    # Recompute summary
    req_set.compute_summary()

    return messages


def _dedup_key(req: CognosRequirement) -> str:
    """
    Generate a deduplication key for a requirement.

    Uses category + field name (normalized) to detect logical duplicates
    across sections.
    """
    field_normalized = req.field.strip().lower().replace(" ", "_")
    return f"{req.category.value}::{field_normalized}"
