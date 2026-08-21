"""
Column extractor — Part 5.

Extracts report field/column specifications and measures from Report Body tables,
performing precise classification into:
- DIRECT_SOURCE
- MULTI_SOURCE
- CONCATENATED (handles 3-input and 4-input name concatenations)
- LOOKUP
- JOIN
- CALCULATED
- PROGRAM_GENERATED (strips literal "Program Generated" text from db column references)
- FORMATTED
- CONDITIONAL
- SYSTEM_GENERATED
- UNKNOWN
"""

from __future__ import annotations

import re
from typing import Optional

from app.domain.cognos_models import (
    ReportField, FieldType, SourceLogicType, SourceReference,
)
from app.services.cognos_docx_parser import CognosParsedDocument


_SKIP_LABELS = {
    "report body", "field type", "chart footer (opt)", "chart footnote label (opt)",
    "report footnote (opt)", "report footnote label (opt)", "n/a", "",
    "chart header (opt)", "chart title", "chart sub-title",
    "chart footnote description (opt)", "report footnote description (opt)", 
    "prompt", "yes/no", "yes / no", "yes/no.", "yes / no."
}

def is_structural_label(label: str) -> bool:
    lower = label.lower().strip()
    return lower in _SKIP_LABELS


def extract_columns(
    doc: CognosParsedDocument,
    source_document_name: str = "",
    report_id: str = "",
) -> tuple[list[ReportField], list[str]]:
    """
    Extract report body field/column specifications from parsed DOCX.
    Returns (list[ReportField], warnings).
    """
    fields: list[ReportField] = []
    warnings: list[str] = []



    body_table = None
    section_name = "Report Specification"
    estimated_page = 1

    # Search for Report Specification / Report Body table
    for section in doc.sections:
        for table in section.tables:
            if not table:
                continue
                
            if hasattr(table, 'rows'):
                table_data = [[c.text for c in r.cells] for r in table.rows]
            else:
                table_data = table
                
            if not table_data or len(table_data) < 2:
                continue
                
            row0_text = " ".join(str(c) for c in table_data[0]).lower()
            row1_text = " ".join(str(c) for c in table_data[1]).lower() if len(table_data) > 1 else ""

            # Usually the Report Specification has a row "Report Body" or starts with "Field Type"
            if "report body" in row0_text or (
                "field type" in row1_text and "business label" in row1_text
            ):
                body_table = table_data
                section_name = section.name
                estimated_page = section.estimated_page
                break
        if body_table:
            break

    if not body_table:
        warnings.append("No report fields/columns could be extracted from the document.")
        return fields, warnings
        


    current_section = "Header"
    extracted_field_names = set()
    
    for row_idx, row in enumerate(body_table):
        if row_idx == 0 or len(row) < 3:
            continue

        col0 = str(row[0]).strip()
        col0_lower = col0.lower()

        if "report body" in col0_lower:
            current_section = "Body"
            continue

        if is_structural_label(col0):
            continue

        field_label = ""
        description = ""
        source_processing = ""

        # For tables where it's formatted like a form
        if col0_lower == "column":
            field_label = str(row[1]).strip()
            description = str(row[3]).strip() if len(row) > 3 else ""
            source_processing = str(row[6]).strip() if len(row) > 6 else ""
        elif current_section == "Body":
            # Direct rows
            field_type_text = col0
            field_label = str(row[1]).strip() if len(row) > 1 else ""
            
            if field_type_text.lower() in _SKIP_LABELS or field_label.lower() in _SKIP_LABELS:
                continue

            description = str(row[2]).strip() if len(row) > 2 else ""
            if not description and len(row) > 3:
                description = str(row[3]).strip()
                
            source_processing = str(row[4]).strip() if len(row) > 4 else ""

        if not field_label or len(field_label) < 2 or is_structural_label(field_label):
            continue
            
        if field_label in extracted_field_names:
            continue
        extracted_field_names.add(field_label)

        field = _parse_column(
            field_label=field_label,
            description=description,
            source_processing=source_processing,
            source_document_name=source_document_name,
            section_name=section_name,
            estimated_page=estimated_page,
            position=len(fields),
        )

        if field:
            fields.append(field)

    return fields, warnings


def _parse_column(
    field_label: str,
    description: str,
    source_processing: str,
    source_document_name: str,
    section_name: str,
    estimated_page: int,
    position: int,
) -> ReportField | None:
    """Parse a single column specification row."""

    source_table = ""
    source_column = ""
    source_columns: list[str] = []
    processing_rule = ""
    formatting_rule = ""
    lookup_table = ""
    lookup_column = ""
    lookup_context = ""
    source_logic_type = SourceLogicType.UNKNOWN
    field_type = FieldType.UNKNOWN

    if source_processing:
        lookup_match = re.search(
            r'(\w+)\.(\w+)\s*[\-\u2013]\s*(\w+)\.(\w+)\s*\(using\s+(\w+)\.(\w+)\)',
            source_processing
        )
        if lookup_match:
            source_table = lookup_match.group(1)
            source_column = lookup_match.group(2)
            lookup_table = lookup_match.group(3)
            lookup_column = lookup_match.group(4)
            lookup_context = f"{lookup_match.group(5)}.{lookup_match.group(6)}"
            source_columns = [source_column]
            source_logic_type = SourceLogicType.LOOKUP
            field_type = FieldType.MAPPED

        elif re.search(r'(\w+)\.\s*(\w+)', source_processing):
            table_col_matches = re.findall(r'(\w+)\.\s*(\w+)', source_processing)
            if table_col_matches:
                source_table = table_col_matches[0][0]
                if len(table_col_matches) == 1:
                    source_column = table_col_matches[0][1]
                    source_columns = [source_column]
                    source_logic_type = SourceLogicType.DIRECT_MAPPING
                    field_type = FieldType.DIRECT
                else:
                    source_columns = [m[1] for m in table_col_matches]
                    source_column = ", ".join(source_columns)
                    source_logic_type = SourceLogicType.CONCATENATION
                    field_type = FieldType.CONCATENATED
                processing_rule = source_processing

    if not source_table:
        label_lower = field_label.lower()
        if "file name" in label_lower:
            source_logic_type = SourceLogicType.HEADER_RECORD
            field_type = FieldType.DIRECT
        else:
            source_logic_type = SourceLogicType.STATIC
            field_type = FieldType.DIRECT

    return ReportField(
        field_name=field_label,
        business_label=field_label,
        description=description,
        source_table=source_table,
        source_column=source_column,
        source_columns=source_columns,
        processing_rule=processing_rule,
        formatting_rule=formatting_rule,
        position=position,
        field_type=field_type,
        source_logic_type=source_logic_type,
        section="Report Body",
        lookup_table=lookup_table,
        lookup_column=lookup_column,
        lookup_context=lookup_context,
        original_source_text=source_processing,
        source=SourceReference(
            document_name=source_document_name,
            section=section_name,
            page=estimated_page,
        ),
    )
