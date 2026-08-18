"""
Special processing extractor.

Extracts use cases, version variants, and naming conventions from the
"Report Special Processing" section of a Cognos report definition.

For example, OPR-TPL-016 has HMS Daily and HMS Weekly versions with
distinct naming conventions — each becomes a separate special processing
item for targeted test case generation.
"""

from __future__ import annotations

import re

from app.domain.cognos_models import SpecialProcessingItem, SourceReference
from app.services.cognos_docx_parser import CognosParsedDocument


def extract_special_processing(
    doc: CognosParsedDocument,
    source_document_name: str = "",
) -> tuple[list[SpecialProcessingItem], list[str]]:
    """
    Extract special processing items from the parsed DOCX.

    Returns (items, warnings).
    """
    items: list[SpecialProcessingItem] = []
    warnings: list[str] = []

    # Find special processing section
    sp_sections = doc.get_sections("Special Processing")
    if not sp_sections:
        return items, warnings

    for section in sp_sections:
        # Extract from tables
        for table_data in section.tables:
            items.extend(_extract_from_table(
                table_data, section.estimated_page,
                source_document_name, section.name,
            ))

        # Extract from paragraph text
        items.extend(_extract_from_paragraphs(
            section.paragraphs, section.estimated_page,
            source_document_name, section.name,
        ))

    if not items:
        # Try to create a general item from the section text
        for section in sp_sections:
            if section.raw_text.strip():
                items.append(SpecialProcessingItem(
                    use_case="General",
                    description=section.raw_text.strip()[:500],
                    source=SourceReference(
                        document_name=source_document_name,
                        section=section.name,
                        page=section.estimated_page,
                    ),
                ))

    return items, warnings


def _extract_from_table(
    table_data: list[list[str]],
    estimated_page: int,
    source_document_name: str,
    section_name: str,
) -> list[SpecialProcessingItem]:
    """Extract special processing items from a table."""
    items = []

    if not table_data:
        return items

    for row in table_data:
        text = " | ".join(cell.strip() for cell in row if cell.strip())
        if not text:
            continue

        item = _parse_special_processing_text(
            text, estimated_page, source_document_name, section_name
        )
        if item:
            items.append(item)

    return items


def _extract_from_paragraphs(
    paragraphs: list[str],
    estimated_page: int,
    source_document_name: str,
    section_name: str,
) -> list[SpecialProcessingItem]:
    """Extract special processing items from paragraph text."""
    items = []

    full_text = "\n".join(paragraphs)

    # Look for use case patterns
    use_case_pattern = re.compile(
        r"(?:use\s+case|scenario|version)\s*(?:\d+)?[:\s]+(.+?)(?=use\s+case|scenario|version|\Z)",
        re.IGNORECASE | re.DOTALL,
    )

    for match in use_case_pattern.finditer(full_text):
        desc = match.group(1).strip()
        if desc and len(desc) > 5:
            item = _parse_special_processing_text(
                desc, estimated_page, source_document_name, section_name
            )
            if item:
                items.append(item)

    # Look for naming convention patterns
    naming_pattern = re.compile(
        r"([A-Z]{2,4}-[A-Z]{2,4}-\d{3,}[A-Za-z0-9_-]*)",
    )
    for match in naming_pattern.finditer(full_text):
        convention = match.group(1)
        # Check if this is a version naming convention (longer than a basic report ID)
        if len(convention) > 12:  # Longer than typical report IDs
            # Find context around the match
            start = max(0, match.start() - 100)
            end = min(len(full_text), match.end() + 100)
            context = full_text[start:end].strip()

            items.append(SpecialProcessingItem(
                naming_convention=convention,
                description=context[:300],
                source=SourceReference(
                    document_name=source_document_name,
                    section=section_name,
                    page=estimated_page,
                ),
            ))

    # Look for daily/weekly/monthly variant patterns
    variant_pattern = re.compile(
        r"(daily|weekly|monthly|quarterly|annual)\s+(?:version|report|processing|run)",
        re.IGNORECASE,
    )
    for match in variant_pattern.finditer(full_text):
        variant = match.group(1).strip().title()
        start = max(0, match.start() - 100)
        end = min(len(full_text), match.end() + 200)
        context = full_text[start:end].strip()

        # Avoid duplicating if already captured
        already_exists = any(
            variant.lower() in (item.version.lower() or item.use_case.lower())
            for item in items
        )
        if not already_exists:
            items.append(SpecialProcessingItem(
                use_case=f"{variant} Processing",
                version=variant,
                description=context[:300],
                source=SourceReference(
                    document_name=source_document_name,
                    section=section_name,
                    page=estimated_page,
                ),
            ))

    return items


def _parse_special_processing_text(
    text: str,
    estimated_page: int,
    source_document_name: str,
    section_name: str,
) -> SpecialProcessingItem | None:
    """Parse a text block into a SpecialProcessingItem."""
    if not text or len(text.strip()) < 5:
        return None

    text = text.strip()

    # Try to identify components
    use_case = ""
    version = ""
    naming_convention = ""

    # Check for naming conventions
    naming_match = re.search(
        r"([A-Z]{2,4}-[A-Z]{2,4}-\d{3,}[A-Za-z0-9_-]*)", text
    )
    if naming_match:
        naming_convention = naming_match.group(1)

    # Check for version identifiers
    version_match = re.search(
        r"(daily|weekly|monthly|quarterly|HMS\s+\w+)",
        text, re.IGNORECASE
    )
    if version_match:
        version = version_match.group(1).strip()

    # Use case is the full description
    use_case = text[:200]

    return SpecialProcessingItem(
        use_case=use_case,
        version=version,
        naming_convention=naming_convention,
        description=text[:500],
        source=SourceReference(
            document_name=source_document_name,
            section=section_name,
            page=estimated_page,
        ),
    )
