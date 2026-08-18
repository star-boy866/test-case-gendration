"""
Sort, control break, total, count, selection criteria, and output extractor — Part 3.

Extracts structured Report Definition tables:
- Selection Criteria (field, parameter, prompt)
- Sort Definitions (sequence 1..N, field, direction) — ignores blank rows
- Control Breaks (Page vs Section groupings)
- Totals & Subtotals (only populated rows)
- Counts / Measures (e.g., Total Records Exchanged, Exact Matches for OPR-005)
- Output, Distribution Groups, and Retention

Strict isolation ensures distribution groups (e.g., "Insurance Carriers", "Operations")
NEVER contaminate sort definitions.
"""

from __future__ import annotations

import re
from typing import Optional

from app.domain.cognos_models import (
    SortDefinition, SortDirection,
    ControlBreakDefinition,
    TotalDefinition,
    CountDefinition,
    SelectionCriterion,
    OutputDefinition,
    SourceReference,
)
from app.services.cognos_docx_parser import (
    CognosParsedDocument, DocumentSection, ParsedTable, CheckboxState,
)


def _parse_direction(text: str) -> SortDirection:
    """Parse sort direction from text."""
    text_lower = text.lower().strip()
    if any(kw in text_lower for kw in ("asc", "ascending", "a-z", "0-9", "low to high")):
        return SortDirection.ASCENDING
    if any(kw in text_lower for kw in ("desc", "descending", "z-a", "9-0", "high to low")):
        return SortDirection.DESCENDING
    return SortDirection.ASCENDING  # Default to ASCENDING for Cognos sorts


def _is_invalid_sort_field(field_text: str) -> bool:
    """Check if field_text is blank, label noise, or invalid for a sort field."""
    if not field_text:
        return True
    cleaned = field_text.strip().lower()
    if cleaned in ("", "blank", "n/a", "sort by", "sort by:", "ascending\tdescending", "ascending", "descending", "page:", "section:"):
        return True
    if any(kw in cleaned for kw in ("report control breaks", "report output", "insurance carriers", "operations", "distribution")):
        return True
    return False


def extract_sorts_and_groups(
    doc: CognosParsedDocument,
    source_document_name: str = "",
) -> tuple[
    list[SortDefinition],
    list[ControlBreakDefinition],
    list[TotalDefinition],
    list[CountDefinition],
    list[str],
]:
    """
    Extract sort, control break, total, and count definitions strictly from physical tables.
    Returns (sorts, control_breaks, totals, counts, warnings).
    """
    sorts: list[SortDefinition] = []
    control_breaks: list[ControlBreakDefinition] = []
    totals: list[TotalDefinition] = []
    counts: list[CountDefinition] = []
    warnings: list[str] = []

    seen_sort_fields: set[str] = set()

    for parsed_table in doc.all_parsed_tables:
        for row in parsed_table.rows:
            if not row.cells:
                continue

            c0_text = row.cells[0].text.strip().lower()

            # 1. SORT BY
            if c0_text.startswith("sort by") or c0_text == "sort":
                if len(row.cells) > 2:
                    field_val = row.cells[2].text.strip()
                    if field_val and not _is_invalid_sort_field(field_val):
                        # Clean field name
                        field_clean = re.sub(r"\s+", " ", field_val).strip()
                        if field_clean.lower() not in seen_sort_fields:
                            seen_sort_fields.add(field_clean.lower())

                            # Check direction cell (cell 5 or cell 6)
                            dir_val = SortDirection.ASCENDING
                            for cell in row.cells[3:]:
                                has_checked_dir = False
                                for cb in cell.checkbox_labels:
                                    if cb.get("checked") or cb.get("state") == CheckboxState.CHECKED:
                                        has_checked_dir = True
                                        if "descending" in cb["label"].lower():
                                            dir_val = SortDirection.DESCENDING
                                        elif "ascending" in cb["label"].lower():
                                            dir_val = SortDirection.ASCENDING
                                if not has_checked_dir and "descending" in cell.text.lower() and "ascending" not in cell.text.lower():
                                    dir_val = SortDirection.DESCENDING

                            sorts.append(SortDefinition(
                                priority=len(sorts) + 1,
                                field=field_clean,
                                direction=dir_val,
                                source=SourceReference(
                                    document_name=source_document_name,
                                    section=parsed_table.section_name,
                                    page=parsed_table.source_page,
                                ),
                            ))

            # 2. CONTROL BREAK
            elif c0_text.startswith("control break"):
                break_type = "Page"
                if len(row.cells) > 1 and "section" in row.cells[1].text.lower():
                    break_type = "Section"

                for cell in row.cells[2:]:
                    c_text = cell.text.strip()
                    if c_text and not _is_invalid_sort_field(c_text):
                        for cb_field in [f.strip() for f in c_text.split("\n") if f.strip()]:
                            if cb_field.lower() not in ("control break", "page:", "section:", "report control breaks, totals, counts, and sorts"):
                                # Avoid duplicate control breaks in the same row
                                if not any(cb.field == cb_field and cb.break_type == break_type for cb in control_breaks):
                                    control_breaks.append(ControlBreakDefinition(
                                        field=cb_field,
                                        break_type=break_type,
                                        level=len(control_breaks) + 1,
                                        source=SourceReference(
                                            document_name=source_document_name,
                                            section=parsed_table.section_name,
                                            page=parsed_table.source_page,
                                        ),
                                    ))

            # 3. TOTALS
            elif c0_text.startswith("total") and not c0_text.startswith("total records"):
                scope = "Grand"
                if len(row.cells) > 1 and "section" in row.cells[1].text.lower():
                    scope = "Section"
                for cell in row.cells[2:]:
                    c_text = cell.text.strip()
                    if c_text and c_text.lower() not in ("total", "grand:", "section:", "blank", "n/a"):
                        totals.append(TotalDefinition(
                            field=c_text,
                            total_type="Total",
                            scope=scope,
                            source=SourceReference(
                                document_name=source_document_name,
                                section=parsed_table.section_name,
                                page=parsed_table.source_page,
                            ),
                        ))

            # 4. COUNTS
            elif c0_text.startswith("counts") or c0_text.startswith("count"):
                scope = "Section"
                if len(row.cells) > 1 and "grand" in row.cells[1].text.lower():
                    scope = "Grand"
                for cell in row.cells[2:]:
                    c_text = cell.text.strip()
                    if c_text and c_text.lower() not in ("counts", "count", "grand:", "section:", "report control breaks, totals, counts, and sorts"):
                        # Extract count measure strings (e.g., Total Records Exchanged (by LOB Cd))
                        raw_items = [item.strip() for item in c_text.split("\n") if item.strip()]
                        for raw_item in raw_items:
                            # Clean measure name: remove "(by LOB Cd)" suffix
                            clean_measure = re.sub(r"\s*\(by\s+[^)]+\)", "", raw_item, flags=re.IGNORECASE).strip()
                            if clean_measure and not any(cnt.field == clean_measure for cnt in counts):
                                counts.append(CountDefinition(
                                    field=clean_measure,
                                    count_type="Count",
                                    scope=scope,
                                    description=raw_item,
                                    source=SourceReference(
                                        document_name=source_document_name,
                                        section=parsed_table.section_name,
                                        page=parsed_table.source_page,
                                    ),
                                ))

    sorts.sort(key=lambda s: s.priority)

    if not sorts:
        warnings.append("No sort definitions found in the document.")

    return sorts, control_breaks, totals, counts, warnings


def extract_selection_criteria(
    doc: CognosParsedDocument,
    source_document_name: str = "",
) -> list[SelectionCriterion]:
    """
    Extract SelectionCriteria rows from Report Selection Criteria tables.
    Only creates parameter when parameter cell contains explicit parameter expression.
    """
    criteria: list[SelectionCriterion] = []
    seen_fields: set[str] = set()

    for parsed_table in doc.all_parsed_tables:
        for row in parsed_table.rows:
            if not row.cells:
                continue

            c0_text = row.cells[0].text.strip().lower()
            if "selection criteria" in c0_text:
                if len(row.cells) > 2:
                    field_val = row.cells[2].text.strip()
                    if not field_val or field_val.lower() in ("report field", "report selection criteria:", "no   yes", "prompt"):
                        continue

                    if field_val.lower() not in seen_fields:
                        seen_fields.add(field_val.lower())

                        # Parameter cell (cells[4] or cells[5])
                        param_val = ""
                        for cell in row.cells[3:]:
                            t = cell.text.strip()
                            if t and t.lower() not in ("no   yes", "prompt", "no", "yes") and not t.lower().startswith("report parameters"):
                                if "<parameter" in t.lower() or "parameter" in t.lower() or t.startswith(":"):
                                    param_val = t
                                    break

                        criteria.append(SelectionCriterion(
                            field=field_val,
                            parameter_name=param_val,
                            prompt=False,
                            source=SourceReference(
                                document_name=source_document_name,
                                section=parsed_table.section_name,
                                page=parsed_table.source_page,
                            ),
                        ))

    return criteria


def extract_output_definition(
    doc: CognosParsedDocument,
    source_document_name: str = "",
) -> OutputDefinition:
    """
    Extract Output, Distribution Groups, and Retention definitions.
    """
    output = OutputDefinition(
        source=SourceReference(
            document_name=source_document_name,
            section="Report Output",
        )
    )
    dist_groups = []

    for parsed_table in doc.all_parsed_tables:
        for row in parsed_table.rows:
            if not row.cells:
                continue

            c0_text = row.cells[0].text.strip().lower()

            if "output format" in c0_text:
                for cell in row.cells[2:]:
                    if "pdf" in cell.text.lower():
                        if "PDF" not in output.formats:
                            output.formats.append("PDF")

            elif "reporting portal" in c0_text:
                for cell in row.cells[2:]:
                    if "edms" in cell.text.lower():
                        output.reporting_portal = "EDMS"
                    elif "web portal" in cell.text.lower() and not output.reporting_portal:
                        output.reporting_portal = "Web Portal"

            elif "distribution group" in c0_text:
                output.distribution_enabled = True
                for cell in row.cells[4:]:
                    c_text = cell.text.strip()
                    if c_text:
                        # Match "1. Insurance Carriers", "2. Operations"
                        m = re.search(r"\d+\.\s*(.+)", c_text)
                        if m:
                            group_name = m.group(1).strip()
                            if group_name and group_name not in dist_groups:
                                dist_groups.append(group_name)

            elif "retention type" in c0_text:
                for cell in row.cells[2:]:
                    if "edms" in cell.text.lower():
                        output.retention_type = "EDMS"
                        output.retention = "EDMS"

            elif "output versions" in c0_text:
                for cell in row.cells[2:]:
                    c_text = cell.text.strip()
                    if "occurrences:7" in c_text.lower() or "7 years" in c_text.lower():
                        output.output_versions = "7 Years"

    output.distribution_groups = dist_groups
    output.distribution = dist_groups
    return output
