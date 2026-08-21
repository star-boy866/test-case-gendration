"""
Specification Table Extractor — extracts section header fields from the
Report Specification table (the large table containing Field Label,
Field Description, and Source/Processing Rules for header-level fields).
"""

from __future__ import annotations

import re

def is_structural_label(label: str) -> bool:
    lower = label.lower().strip()
    structural = [
        "report header", "report section", "chart header", "chart footer",
        "report footnote", "report footnote label", "report body",
        "field type", "chart object", "presentation type", "n/a", "column", "unknown", "review required"
    ]
    for s in structural:
        if s in lower:
            return True
    return False
from app.domain.cognos_models import (
    ReportField, FieldType, SourceLogicType, SourceReference,
)
from app.services.cognos_docx_parser import CognosParsedDocument


def extract_spec_table_fields(
    doc: CognosParsedDocument,
    source_document_name: str = "",
) -> list[ReportField]:
    """
    Extract body fields and section fields from the Report Specification table.
    Uses semantic template form parsing for NH MMIS Report Definition Template.
    """
    fields: list[ReportField] = []

    spec_table = None
    section_name = ""
    estimated_page = 1

    for section in doc.sections:
        for table in section.tables:
            if not table:
                continue
            
            if hasattr(table, 'rows'):
                table_data = [[c.text for c in r.cells] for r in table.rows]
            else:
                table_data = table
                
            if not table_data:
                continue
                
            header_text = " ".join(table_data[0]).lower()
            if "report specification" in header_text:
                spec_table = table_data
                section_name = section.name
                estimated_page = section.estimated_page
                break
        if spec_table:
            break

    if not spec_table:
        return fields

    # State tracking for semantic interpretation
    current_section = "Header"
    

    # Filter function to keep only true fields moved to module level
    extracted_field_names = set()

    for row_idx, row in enumerate(spec_table):
        if row_idx == 0 or len(row) < 3:
            continue

        col0 = row[0].strip()
        col0_lower = col0.lower()

        # Handle section transitions
        if "report body" in col0_lower:
            current_section = "Body"
            continue

        if is_structural_label(col0):
            continue

        field_label = ""
        description = ""
        source_processing = ""

        if current_section == "Header":
            field_label = col0
            description = row[3].strip() if len(row) > 3 else ""
            source_processing = row[6].strip() if len(row) > 6 else ""
        elif current_section == "Body":
            if col0_lower == "column":
                field_label = row[1].strip()
                description = row[3].strip() if len(row) > 3 else ""
                source_processing = row[6].strip() if len(row) > 6 else ""
            else:
                continue

        # Skip if not a valid label
        if not field_label or len(field_label) < 2 or is_structural_label(field_label):
            continue
        if field_label in extracted_field_names:
            continue
        extracted_field_names.add(field_label)

        # Parse logic
        field = _parse_spec_field(
            field_label=field_label,
            description=description,
            source_processing=source_processing,
            source_document_name=source_document_name,
            section_name=section_name,
            estimated_page=estimated_page,
            position=len(fields),
            current_section=current_section
        )

        if field:
            fields.append(field)
            


    return fields


def _parse_spec_field(
    field_label: str,
    description: str,
    source_processing: str,
    source_document_name: str,
    section_name: str,
    estimated_page: int | None,
    position: int,
    current_section: str = "Section Header"
) -> ReportField | None:
    """Parse a single specification table row into a ReportField."""

    source_table = "NOT_DEFINED"
    source_column = "NOT_DEFINED"
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

    if source_table == "NOT_DEFINED" or not source_table:
        label_lower = field_label.lower()
        if "file name" in label_lower:
            source_logic_type = SourceLogicType.HEADER_RECORD
            field_type = FieldType.DIRECT
        else:
            source_logic_type = SourceLogicType.STATIC
            field_type = FieldType.DIRECT
        source_table = "NOT_DEFINED"
        
    if source_table in ["REVIEW_REQUIRED", "Line", "UNKNOWN", ""]:
        source_table = "NOT_DEFINED"

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
        section=current_section,
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
