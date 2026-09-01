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
    # Phase 10.6, 12, 12R, and 15.4 Developer UT Methodologies (Authoritative)
    "Report Execution and Scheduling Validation": "EXEC",
    "Report Execution & Scheduling Validation": "EXEC",
    "Scheduled Execution Validation": "EXEC",
    "Report Execution Validation": "EXEC",
    "EXEC": "EXEC",
    "SCHE": "EXEC",
    "Report Name Description Validation": "REPO",
    "Report Definition Validation": "REPO",
    "Report Header Validation": "RHDR",
    "Report Section Heading Validation": "SECT",
    "Selection Criteria Validation": "SELC",
    "Label Validation": "LABE",
    "Layout Validation": "LAYO",
    "Lookup Validation": "LOOK",
    "Output Delivery Validation": "OUTP",
    "Script Output Validation": "SCRI",
    "Sort Validation": "SORT",
    "Special Processing Validation": "SPEC",
    "Date Format Validation": "DATE",
    "DB Report Data Validation": "DBRV",
    "DB Count Validation": "DBCO",
    "Duplicate Validation": "DUPL",
    "Control Break Validation": "CB",
    "No Data Validation": "NODATA",

    # Aliases and Legacy Categories
    "Metadata": "REPO",
    "Report Header": "RHDR",
    "Section Heading": "SECT",
    "Section Header": "SECT",
    "Report Selection Criteria": "SELC",
    "Selection Criteria": "SELC",
    "Header": "RHDR",
    "Footer": "RHDR",
    "Report Label": "LABE",
    "Report Layout": "LAYO",
    "Sorting": "SORT",
    "Special Processing": "SPEC",
    "Date Format": "DATE",
    "Column Logic": "DBRE",
    "Totals/Counts": "DBCO",
    "Duplicate Data": "DUPL",
    "Control Break": "CB",
    "No Data": "NODATA",
    "Output": "SCRI",
    "Database Validation": "DBRE",
    "Null Handling": "NULL",
    "Trim Handling": "TRIM",
    "Parameter": "PARAM",
    "Parameter SQL": "PSQL",
    "Negative": "NEG",
    "Configuration": "CONF",
    "COLUMN": "DBRE",
    "SELECTION_CRITERIA_VALIDATION": "SELC",
    "SELECTION_CRITERIA": "SELC",
    "COUNT": "DBCO",
    "TOTAL": "DBCO",
    "OUTPUT_FORMAT": "SCRI",
    "DISTRIBUTION": "OUTP",
    "RETENTION": "SCRI",
    "SCHEDULED_EXECUTION_VALIDATION": "EXEC",
}

_CATEGORY_BASE_ORDER = {
    "EXEC": 10,
    "REPO": 20,
    "RHDR": 30,
    "SECT": 40,
    "SELC": 50,
    "LABE": 60,
    "LAYO": 70,
    "CB": 80,
    "LOOK": 90,
    "OUTP": 100,
    "SCRI": 110,
    "SORT": 120,
    "SPEC": 130,
    "DATE": 140,
    "DBRV": 150,
    "DBRE": 150,
    "DBCO": 160,
    "DUPL": 170,
    "NODATA": 180,
    "NEG": 190,
}

_CATEGORY_ORDER = [
    # 00  EXEC: Scheduled Execution Validation
    "Report Execution and Scheduling Validation",
    "Report Execution & Scheduling Validation",
    "Scheduled Execution Validation",
    "SCHEDULED_EXECUTION_VALIDATION",
    "REPORT_EXECUTION_VALIDATION",

    # 01  REPO: Report Name Description Validation
    "Report Name Description Validation",
    "Report Definition Validation",
    "Metadata",
    "REPORT_NAME_DESCRIPTION_VALIDATION",

    # 02  RHDR: Report Header Validation
    "Report Header Validation",
    "Report Header",
    "Header",
    "Footer",
    "REPORT_HEADER_VALIDATION",

    # 03  SECT: Report Section Heading Validation
    "Report Section Heading Validation",
    "Section Heading",
    "Section Header",
    "REPORT_SECTION_HEADING_VALIDATION",

    # 04  SELC: Selection Criteria Validation
    "Selection Criteria Validation",
    "Report Selection Criteria",
    "Selection Criteria",
    "SELECTION_CRITERIA_VALIDATION",
    "SELECTION_CRITERIA",

    # 05  LABE: Label Validation
    "Label Validation",
    "Report Label",
    "LABEL_VALIDATION",

    # 06  LAYO: Layout Validation
    "Layout Validation",
    "Report Layout",
    "LAYOUT_VALIDATION",

    # 07  CB: Control Break Validation
    "Control Break Validation",
    "Control Break",
    "CONTROL_BREAK_VALIDATION",
    "CB",

    # 08  LOOK: Lookup Validation
    "Lookup Validation",
    "LOOKUP_VALIDATION",

    # 09  OUTP: Output Delivery Validation
    "Output Delivery Validation",
    "OUTPUT_DELIVERY_VALIDATION",
    "DISTRIBUTION",

    # 10  SCRI: Script Output Validation
    "Script Output Validation",
    "SCRIPT_OUTPUT_VALIDATION",
    "Output",
    "OUTPUT_FORMAT",
    "RETENTION",

    # 11  SORT: Sort Validation
    "Sort Validation",
    "Sorting",
    "SORT_VALIDATION",
    "SORT",

    # 12  SPEC: Special Processing Validation
    "Special Processing Validation",
    "Special Processing",
    "SPECIAL_PROCESSING_VALIDATION",

    # 13  DATE: Date Format Validation
    "Date Format Validation",
    "Date Format",
    "DATE_FORMAT_VALIDATION",

    # 14  DBRV/DBRE: DB Report Data Validation
    "DB Report Data Validation",
    "Column Logic",
    "DB_REPORT_DATA_VALIDATION",
    "COLUMN",

    # 15  DBCO: DB Count Validation
    "DB Count Validation",
    "Totals/Counts",
    "DB_COUNT_VALIDATION",
    "Count",
    "COUNT",
    "TOTAL",

    # 16  DUPL: Duplicate Validation
    "Duplicate Validation",
    "Duplicate Data",
    "DUPLICATE_VALIDATION",

    # 17  NODATA: No Data Validation
    "No Data Validation",
    "No Data",
    "NO_DATA_VALIDATION",

    # Fallbacks
    "Null Handling",
    "Trim Handling",
    "Database Validation",
    "Parameter",
    "Parameter SQL",
    "Negative",
    "Configuration",
]


def _derive_prefix(report_id: str) -> str:
    """
    Derive a short prefix from the report ID for test case IDs.

    Examples:
        RPT-XYZ-016 -> RPT016
        RPT-MBR-001 -> RPT001
        PRV-INT-027 -> PRV027
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


def order_cognos_test_cases(test_cases: list[CognosTestCase]) -> list[CognosTestCase]:
    """
    Single Authoritative Ordering function for Cognos Test Cases (Phase 12Q).
    
    Orders test cases strictly by their business-defined scenario_order,
    or falls back to category rank so categories are always contiguous and never interleaved.
    """
    def order_key(tc: CognosTestCase) -> tuple:
        if tc.scenario_order and tc.scenario_order > 0:
            return (tc.scenario_order, tc.test_case_id or "", tc.test_case_title or "")
        
        # Fallback if scenario_order is not yet populated
        cat = tc.category or ""
        abbrev = _CATEGORY_ID_MAP.get(cat, "")
        if not abbrev:
            clean_cat = re.sub(r"[^A-Z]", "", cat.upper())
            abbrev = clean_cat[:4] if clean_cat else "TC"
        
        base_order = _CATEGORY_BASE_ORDER.get(abbrev, 999)
        return (base_order, tc.source_field or "", tc.test_case_title or "")

    return sorted(test_cases, key=order_key)


def assign_test_case_ids(
    test_cases: list[CognosTestCase],
    report_id: str,
) -> list[CognosTestCase]:
    """
    Assign deterministic test case IDs and scenario_order in the authoritative business order.

    ID format: {PREFIX}-{CATEGORY_ABBREV}-{SEQUENCE}
    Example: PRV027-REPO-01, PRV027-RHDR-01, PRV027-DBRE-01
    """
    prefix = _derive_prefix(report_id)

    # Sort test cases strictly by category rank to guarantee contiguous grouping while preserving internal order
    def sort_key(tc: CognosTestCase) -> int:
        cat = tc.category or ""
        abbrev = _CATEGORY_ID_MAP.get(cat, "")
        if not abbrev:
            clean_cat = re.sub(r"[^A-Z]", "", cat.upper())
            abbrev = clean_cat[:4] if clean_cat else "TC"
        return _CATEGORY_BASE_ORDER.get(abbrev, 999)

    sorted_cases = sorted(test_cases, key=sort_key)

    category_counters: dict[str, int] = {}

    for tc in sorted_cases:
        abbrev = _CATEGORY_ID_MAP.get(tc.category)
        if not abbrev:
            clean_cat = re.sub(r"[^A-Z]", "", (tc.category or "").upper())
            abbrev = clean_cat[:4] if clean_cat else "TC"

        category_counters[abbrev] = category_counters.get(abbrev, 0) + 1
        seq = category_counters[abbrev]

        tc.test_case_id = f"{prefix}-{abbrev}-{seq:02d}"
        if not tc.report_id:
            tc.report_id = report_id

    # Assign contiguous sequential scenario_order: 10, 20, 30, ...
    for idx, tc in enumerate(sorted_cases, start=1):
        tc.scenario_order = idx * 10

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
