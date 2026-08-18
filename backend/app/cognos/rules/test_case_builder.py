"""
Test case builder — assigns deterministic IDs and ensures completeness.

Generates test case IDs following the reference format:
    {PREFIX}-{CATEGORY}-{SEQUENCE}

Where PREFIX is derived from the Report ID (e.g., RPT-XYZ-016 -> RPT016).

Category ID mapping matches the reference workbook exactly:
    Header -> HDR, Section Header -> SEC, Column Logic -> COL,
    Sorting -> SORT, Control Break -> CB, Totals/Counts -> TOT,
    Selection Criteria -> SEL, Special Processing -> SPEC,
    Output -> OUT, Negative -> NEG, Footer -> HDR (grouped with header)
"""

from __future__ import annotations

import re

from app.domain.cognos_test_case import CognosTestCase


_CATEGORY_ID_MAP = {
    "Header": "HDR",
    "Footer": "HDR",        # Footer tests are numbered with header (HDR-06)
    "Section Header": "SEC",
    "Column Logic": "COL",
    "Sorting": "SORT",
    "Control Break": "CB",
    "Totals/Counts": "TOT",
    "Selection Criteria": "SEL",
    "Special Processing": "SPEC",
    "Output": "OUT",
    "Negative": "NEG",
    # New Dev UT categories
    "Report Layout": "LAY",
    "Report Label": "LBL",
    "Date Format": "DATE",
    "Null Handling": "NULL",
    "Trim Handling": "TRIM",
    "Database Validation": "DB",
    "Parameter": "PARAM",
    "Parameter SQL": "PSQL",
    "Duplicate Data": "DUP",
    "No Data": "NODATA",
    "Configuration": "CONF",
    "Metadata": "META",
    # Legacy category names (backward compatibility)
    "REPORT_ID": "HDR",
    "REPORT_TITLE": "HDR",
    "REPORT_DESCRIPTION": "HDR",
    "REPORT_SOURCE": "HDR",
    "REPORT_GENERATED_BY": "HDR",
    "REPORT_FREQUENCY": "HDR",
    "HEADER": "HDR",
    "SELECTION_CRITERIA": "SEL",
    "COLUMN": "COL",
    "COLUMN_LABEL": "COL",
    "COLUMN_SOURCE": "COL",
    "COLUMN_LOGIC": "COL",
    "COLUMN_FORMAT": "COL",
    "SORT": "SORT",
    "CONTROL_BREAK": "CB",
    "TOTAL": "TOT",
    "COUNT": "CNT",
    "LAYOUT": "LAY",
    "PAGINATION": "PAGE",
    "FOOTER": "HDR",
    "OUTPUT_FORMAT": "OUT",
    "SPECIAL_PROCESSING": "SPEC",
}

_CATEGORY_ORDER = [
    "Report Layout",
    "Metadata",
    "Configuration",
    "Report Label",
    "Header",
    "Footer",
    "Section Header",
    "Selection Criteria",
    "Parameter",
    "Parameter SQL",
    "Column Logic",
    "Date Format",
    "Null Handling",
    "Trim Handling",
    "Sorting",
    "Control Break",
    "Totals/Counts",
    "Duplicate Data",
    "No Data",
    "Special Processing",
    "Output",
    "Negative",
    "Database Validation",
    # Legacy
    "REPORT_ID", "REPORT_TITLE", "REPORT_DESCRIPTION",
    "REPORT_SOURCE", "REPORT_GENERATED_BY", "REPORT_FREQUENCY",
    "REPORT_METADATA", "HEADER",
    "SELECTION_CRITERIA",
    "COLUMN_LABEL", "COLUMN_SOURCE", "COLUMN_LOGIC", "COLUMN_FORMAT", "COLUMN",
    "SORT", "CONTROL_BREAK", "TOTAL", "COUNT",
    "LAYOUT", "PAGINATION",
    "OUTPUT_FORMAT", "DISTRIBUTION", "RETENTION",
    "SPECIAL_PROCESSING",
]


def _derive_prefix(report_id: str) -> str:
    """
    Derive a short prefix from the report ID for test case IDs.

    Examples:
        RPT-XYZ-016 -> RPT016
        RPT-MBR-001 -> RPT001
        RPT-PRV-002 -> RPT002
    """
    if not report_id:
        return "TC"

    parts = report_id.split("-")
    if len(parts) >= 3:
        prefix = parts[0]
        number = parts[-1]
        return f"{prefix}{number}"
    elif len(parts) == 2:
        return f"{parts[0]}{parts[1]}"
    else:
        clean = re.sub(r"[^A-Z0-9]", "", report_id.upper())
        return clean[:8] if clean else "TC"


def assign_test_case_ids(
    test_cases: list[CognosTestCase],
    report_id: str,
) -> list[CognosTestCase]:
    """
    Assign deterministic test case IDs and sort in logical testing order.

    ID format: {PREFIX}-{CATEGORY_ABBREV}-{SEQUENCE}
    Example: RPT016-HDR-01, RPT016-COL-03, RPT016-SORT-01
    """
    prefix = _derive_prefix(report_id)

    # Sort test cases in logical order
    def sort_key(tc: CognosTestCase) -> tuple:
        cat = tc.category
        order = _CATEGORY_ORDER.index(cat) if cat in _CATEGORY_ORDER else 999
        return (order, tc.source_field or "", tc.test_case_title)

    sorted_cases = sorted(test_cases, key=sort_key)

    category_counters: dict[str, int] = {}

    for tc in sorted_cases:
        abbrev = _CATEGORY_ID_MAP.get(tc.category)
        if not abbrev:
            clean_cat = re.sub(r"[^A-Z]", "", tc.category.upper())
            abbrev = clean_cat[:4] if clean_cat else "TC"

        category_counters[abbrev] = category_counters.get(abbrev, 0) + 1
        seq = category_counters[abbrev]

        tc.test_case_id = f"{prefix}-{abbrev}-{seq:02d}"
        if not tc.report_id:
            tc.report_id = report_id

    return sorted_cases


def validate_test_cases(
    test_cases: list[CognosTestCase],
) -> tuple[list[CognosTestCase], list[str]]:
    """
    Validate that all test cases are complete.

    Returns (valid_cases, warnings_for_incomplete).
    """
    valid = []
    warnings = []

    for tc in test_cases:
        missing = tc.missing_fields
        if missing:
            warnings.append(
                f"Test case '{tc.test_case_id or tc.test_case_title}' "
                f"is missing required fields: {', '.join(missing)}"
            )
            if tc.notes:
                tc.notes += f"\n[INCOMPLETE: missing {', '.join(missing)}]"
            else:
                tc.notes = f"[INCOMPLETE: missing {', '.join(missing)}]"

        valid.append(tc)

    return valid, warnings
