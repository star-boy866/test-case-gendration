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
    # Phase 10.6, 12, and 12R Developer UT Methodologies (Authoritative)
    "Report Name Description Validation": "REPO",
    "Report Header Validation": "RHDR",
    "Report Section Heading Validation": "SECT",
    "Selection Criteria Validation": "SELC",
    "Label Validation": "LABE",
    "Layout Validation": "LAYO",
    "Lookup Validation": "LOOK",
    "Output Delivery Validation": "OUTP",
    "Script Output Validation": "SCRI",
    "Scheduled Execution Validation": "SCHE",
    "Sort Validation": "SORT",
    "Special Processing Validation": "SPEC",
    "Date Format Validation": "DATE",
    "DB Report Data Validation": "DBRE",
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
}

_CATEGORY_BASE_ORDER = {
    "REPO": 10,
    "RHDR": 20,
    "SECT": 30,
    "SELC": 40,
    "LABE": 50,
    "LAYO": 60,
    "LOOK": 70,
    "OUTP": 80,
    "SCRI": 100,
    "SCHE": 120,
    "SORT": 130,
    "SPEC": 150,
    "DATE": 160,
    "DBRE": 180,
    "DBCO": 240,
    "DUPL": 250,
    "CB": 260,
    "NODATA": 270,
    "NEG": 280,
}

_CATEGORY_ORDER = [
    # 01  PRV027-REPO-01: Report Name Description Validation
    "Report Name Description Validation",
    "Metadata",
    "REPORT_NAME_DESCRIPTION_VALIDATION",

    # 02  PRV027-RHDR-01: Report Header Validation
    "Report Header Validation",
    "Report Header",
    "Header",
    "Footer",
    "REPORT_HEADER_VALIDATION",

    # 03  PRV027-SECT-01: Report Section Heading Validation
    "Report Section Heading Validation",
    "Section Heading",
    "Section Header",
    "REPORT_SECTION_HEADING_VALIDATION",

    # 04  PRV027-SELC-01: Selection Criteria Validation
    "Selection Criteria Validation",
    "Report Selection Criteria",
    "Selection Criteria",
    "SELECTION_CRITERIA_VALIDATION",
    "SELECTION_CRITERIA",

    # 05  PRV027-LABE-01: Label Validation
    "Label Validation",
    "Report Label",
    "LABEL_VALIDATION",

    # 06  PRV027-LAYO-01: Layout Validation
    "Layout Validation",
    "Report Layout",
    "LAYOUT_VALIDATION",

    # 07  PRV027-LOOK-01: Lookup Validation
    "Lookup Validation",
    "LOOKUP_VALIDATION",

    # 08-09  PRV027-OUTP-01/02: Output Delivery Validation
    "Output Delivery Validation",
    "OUTPUT_DELIVERY_VALIDATION",
    "DISTRIBUTION",

    # 10-11  PRV027-SCRI-01/02: Script Output Validation
    "Script Output Validation",
    "SCRIPT_OUTPUT_VALIDATION",
    "Output",
    "OUTPUT_FORMAT",
    "RETENTION",

    # 12  PRV027-SCHE-01: Scheduled Execution Validation
    "Scheduled Execution Validation",
    "SCHEDULED_EXECUTION_VALIDATION",

    # 13-14  PRV027-SORT-01/02: Sort Validation
    "Sort Validation",
    "Sorting",
    "SORT_VALIDATION",
    "SORT",

    # 15  PRV027-SPEC-01: Special Processing Validation
    "Special Processing Validation",
    "Special Processing",
    "SPECIAL_PROCESSING_VALIDATION",

    # 16-17  PRV027-DATE-01/02: Date Format Validation
    "Date Format Validation",
    "Date Format",
    "DATE_FORMAT_VALIDATION",

    # 18-23  PRV027-DBRE-01..06: DB Report Data Validation
    "DB Report Data Validation",
    "Column Logic",
    "DB_REPORT_DATA_VALIDATION",
    "COLUMN",

    # 24  PRV027-DBCO-01: DB Count Validation
    "DB Count Validation",
    "Totals/Counts",
    "DB_COUNT_VALIDATION",
    "Count",
    "COUNT",
    "TOTAL",

    # 25  PRV027-DUPL-01: Duplicate Validation
    "Duplicate Validation",
    "Duplicate Data",
    "DUPLICATE_VALIDATION",

    # Additional / Fallbacks
    "Control Break Validation",
    "Control Break",
    "CONTROL_BREAK_VALIDATION",
    "CB",
    "No Data Validation",
    "No Data",
    "NO_DATA_VALIDATION",
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
    
    Orders test cases by their business-defined scenario_order.
    All consumers (persistence, API, UI, Excel export, previous/next navigation)
    must rely on this ordering function as the single source of truth.
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

    # Sort test cases in category / business order first to group and sequence each category
    def sort_key(tc: CognosTestCase) -> tuple:
        cat = tc.category
        order = _CATEGORY_ORDER.index(cat) if cat in _CATEGORY_ORDER else 999
        return (order, tc.source_field or "", tc.test_case_title or "")

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

        # Assign authoritative scenario_order
        base_order = _CATEGORY_BASE_ORDER.get(abbrev, 900)
        tc.scenario_order = base_order + (seq - 1) * 10

    # Return ordered test cases via the single authoritative ordering function
    return order_cognos_test_cases(sorted_cases)


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
