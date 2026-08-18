"""
Layout extractor — extracts presentation type, header, body, footer,
and crosstab/list structural elements from the "Report Layout" section of a
Cognos report definition.

Supports:
- LIST_OBJECT, CROSSTAB_OBJECT, REPEATER_OBJECT, CHART_OBJECT presentation types
- Visual Header & Footer layout elements
- Crosstab measures, row dimensions, and column dimensions
- Strict separation ensuring body field specifications are NEVER misclassified as visual headers
"""

from __future__ import annotations

import re

from app.domain.cognos_models import (
    LayoutDefinition, LayoutElement, PresentationType, SourceReference,
)
from app.services.cognos_docx_parser import CognosParsedDocument


_VISUAL_HEADER_KEYWORDS = [
    "report id:", "client report id", "report title:", "line of business:",
    "department of health and human services", "dhhs", "new hampshire",
    "enterprise operational reports",
]

_VISUAL_FOOTER_KEYWORDS = [
    "run date", "run time", "page: x of y", "page: x", "page number",
]

# Field names from body field specifications that MUST NOT be placed into visual headers
_SPECIFICATION_BODY_FIELDS = {
    "policy dates", "mbr cvrg dates", "coverage codes", "err cd", "mbr alt id",
    "records read", "exact matches", "partial matches", "new coverage",
    "new members", "policies added", "active policies", "pended policies",
    "existing policies modified", "total records exchanged",
}

_PLACEHOLDER_LABELS = {
    "report label name", "reorit lable name", "label name", "report title",
    "report id", "line of business", "client report id", "file name", "process date"
}


def extract_layout(
    doc: CognosParsedDocument,
    source_document_name: str = "",
) -> tuple[LayoutDefinition, list[str]]:
    """
    Extract presentation profile and layout elements from parsed DOCX.
    Returns (LayoutDefinition, warnings).
    """
    layout = LayoutDefinition(
        source=SourceReference(
            document_name=source_document_name,
            section="Report Layout",
        ),
    )
    warnings: list[str] = []

    layout_sections = doc.get_sections("Report Layout")
    if not layout_sections:
        layout_sections = doc.get_sections("Layout")

    if not layout_sections:
        warnings.append("No 'Report Layout' section detected.")
        # Detect presentation type from full document text if section not found
        layout.presentation_type = _detect_presentation_type(doc)
        layout.presentation_type_str = layout.presentation_type.value
        return layout, warnings

    for section in layout_sections:
        layout.source.page = section.estimated_page

        # 1. Presentation Type Detection
        ptype = _detect_presentation_type_from_section(section, doc)
        layout.presentation_type = ptype
        layout.presentation_type_str = ptype.value

        # 2. Extract Elements from Layout Tables
        for parsed_table in section.tables:
            _extract_layout_table_elements(
                parsed_table, layout, section.estimated_page,
                source_document_name, section.name,
            )

        # 3. Extract Elements from Paragraphs
        for para in section.paragraphs:
            _extract_layout_paragraph_elements(
                para, layout, section.estimated_page,
                source_document_name, section.name,
            )

    return layout, warnings


def _detect_presentation_type_from_section(section, doc: CognosParsedDocument) -> PresentationType:
    """Detect presentation type (LIST_OBJECT vs CROSSTAB_OBJECT)."""
    # Check table 0 header row text first
    if section.tables and section.tables[0].rows:
        row0_text = " ".join(c.text for c in section.tables[0].rows[0].cells).lower()
        if "crosstab object" in row0_text or "crosstab" in row0_text:
            return PresentationType.CROSSTAB_OBJECT
        if "list object" in row0_text or "list" in row0_text:
            return PresentationType.LIST_OBJECT
        if "repeater object" in row0_text:
            return PresentationType.REPEATER_OBJECT
        if "chart object" in row0_text:
            return PresentationType.CHART_OBJECT

    # Check paragraph text
    for para in section.paragraphs:
        p_lower = para.lower()
        if "crosstab object" in p_lower or "crosstab" in p_lower:
            return PresentationType.CROSSTAB_OBJECT
        if "list object" in p_lower:
            return PresentationType.LIST_OBJECT

    return _detect_presentation_type(doc)


def _detect_presentation_type(doc: CognosParsedDocument) -> PresentationType:
    """Fallback presentation type detection from whole document."""
    for para in doc.all_paragraphs:
        p_lower = para.lower()
        if "crosstab object" in p_lower or "crosstab" in p_lower:
            return PresentationType.CROSSTAB_OBJECT
        if "list object" in p_lower or "nh mmis report layout – list" in p_lower:
            return PresentationType.LIST_OBJECT
    return PresentationType.LIST_OBJECT


def _extract_layout_table_elements(
    parsed_table,
    layout: LayoutDefinition,
    estimated_page: int,
    source_document_name: str,
    section_name: str,
) -> None:
    """Extract visual layout elements and crosstab measures/dimensions."""
    seen_elements: set[str] = set()

    for r_idx, row in enumerate(parsed_table.rows):
        row_text_set = set(cell.text.strip() for cell in row.cells if cell.text.strip())

        for cell in row.cells:
            text = cell.text.strip()
            if not text:
                continue

            text_clean = re.sub(r"\s+", " ", text)
            text_lower = text_clean.lower()
            source = SourceReference(
                document_name=source_document_name,
                section=section_name,
                page=estimated_page,
            )

            # Check Crosstab Measures (for CROSSTAB_OBJECT like OPR-005)
            if layout.presentation_type == PresentationType.CROSSTAB_OBJECT:
                cleaned_label = text_clean.rstrip(":")
                if any(m in cleaned_label.lower() for m in (
                    "records read", "exact matches", "partial matches", "new coverage",
                    "new members", "policies added", "active policies", "pended policies",
                    "existing policies modified", "total records exchanged"
                )):
                    if cleaned_label not in layout.measures:
                        layout.measures.append(cleaned_label)
                        continue

            # Skip header title row
            if "nh mmis report layout" in text_lower:
                continue
                
            # Skip placeholders
            if text_lower.strip("[]") in _PLACEHOLDER_LABELS:
                continue

            # Classify Visual Footer
            if any(kw in text_lower for kw in _VISUAL_FOOTER_KEYWORDS):
                if text_clean not in seen_elements:
                    seen_elements.add(text_clean)
                    layout.footer_elements.append(LayoutElement(
                        element_name=text_clean, position="footer", source=source
                    ))

            # Classify Visual Header (ensuring no body field mappings enter)
            elif any(kw in text_lower for kw in _VISUAL_HEADER_KEYWORDS):
                if text_lower not in _SPECIFICATION_BODY_FIELDS and text_clean not in seen_elements:
                    seen_elements.add(text_clean)
                    layout.header_elements.append(LayoutElement(
                        element_name=text_clean, position="header", source=source
                    ))

            # Body Elements
            else:
                if text_clean not in seen_elements:
                    seen_elements.add(text_clean)
                    layout.body_elements.append(LayoutElement(
                        element_name=text_clean, position="body", source=source
                    ))

    # Populate dimensions for crosstab
    if layout.presentation_type == PresentationType.CROSSTAB_OBJECT:
        # We rely on the generic body_elements to serve as measures or dimensions
        # rather than inventing hardcoded report-specific structure.
        pass
    else:
        layout.columns = [e.element_name for e in layout.body_elements if e.element_name not in _SPECIFICATION_BODY_FIELDS]


def _extract_layout_paragraph_elements(
    text: str,
    layout: LayoutDefinition,
    estimated_page: int,
    source_document_name: str,
    section_name: str,
) -> None:
    """Extract paragraph layout elements."""
    text_clean = text.strip()
    if not text_clean:
        return
    text_lower = text_clean.lower()
    source = SourceReference(
        document_name=source_document_name,
        section=section_name,
        page=estimated_page,
    )

    if any(kw in text_lower for kw in _VISUAL_FOOTER_KEYWORDS):
        layout.footer_elements.append(LayoutElement(
            element_name=text_clean, position="footer", source=source
        ))
    elif any(kw in text_lower for kw in _VISUAL_HEADER_KEYWORDS):
        layout.header_elements.append(LayoutElement(
            element_name=text_clean, position="header", source=source
        ))
    elif text_lower.strip("[]") not in _PLACEHOLDER_LABELS:
        layout.body_elements.append(LayoutElement(
            element_name=text_clean, position="body", source=source
        ))
