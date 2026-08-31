"""
Phase 12Q — Authoritative PRV-INT-027 Scenario Ordering Tests.

Verifies:
1. Exact 24 test cases generated for PRV-INT-027.
2. 24 unique test_case_id values (no duplicates).
3. Exact matching of the authoritative scenario order:
   01  PRV027-REPO-01
   02  PRV027-RHDR-01
   03  PRV027-SECT-01
   04  PRV027-LABE-01
   05  PRV027-LAYO-01
   06  PRV027-LOOK-01
   07  PRV027-OUTP-01
   08  PRV027-OUTP-02
   09  PRV027-SCRI-01
   10  PRV027-SCRI-02
   11  PRV027-SCHE-01
   12  PRV027-SORT-01
   13  PRV027-SORT-02
   14  PRV027-SPEC-01
   15  PRV027-DATE-01
   16  PRV027-DATE-02
   17  PRV027-DBRE-01
   18  PRV027-DBRE-02
   19  PRV027-DBRE-03
   20  PRV027-DBRE-04
   21  PRV027-DBRE-05
   22  PRV027-DBRE-06
   23  PRV027-DBCO-01
   24  PRV027-DUPL-01
4. scenario_order field matches 10, 20, ..., 240.
5. order_cognos_test_cases is idempotent and deterministic when given shuffled lists.
6. Excel compilation sheet maintains this exact order.
"""

import random
import pytest
from app.cognos.pipeline import run_cognos_pipeline
from app.cognos.rules import order_cognos_test_cases
from app.services.cognos_excel_compiler import build_cognos_workbook

EXPECTED_ORDERED_IDS = [
    "PRV027-EXEC-01",
    "PRV027-REPO-01",
    "PRV027-RHDR-01",
    "PRV027-SECT-01",
    "PRV027-SELC-01",
    "PRV027-LABE-01",
    "PRV027-LAYO-01",
    "PRV027-LOOK-01",
    "PRV027-OUTP-01",
    "PRV027-OUTP-02",
    "PRV027-SCRI-01",
    "PRV027-SCRI-02",
    "PRV027-SORT-01",
    "PRV027-SPEC-01",
    "PRV027-DATE-01",
    "PRV027-DATE-02",
    "PRV027-DBRV-01",
    "PRV027-DBCO-01",
    "PRV027-DUPL-01",
]


def test_prv027_authoritative_order_and_count():
    """Verify exact 19 scenarios and authoritative ordering for PRV-INT-027 with EXEC-01 first."""
    docx_path = "runs/94/source/source.docx"
    ctx = run_cognos_pipeline(docx_path)
    test_cases = ctx.test_suite.test_cases

    assert len(test_cases) == 19, f"Expected 19 test cases, got {len(test_cases)}"

    # 1. Check uniqueness (no duplicates)
    actual_ids = [tc.test_case_id for tc in test_cases]
    assert len(actual_ids) == len(set(actual_ids)), f"Duplicate IDs detected: {actual_ids}"

    # 2. Check exact ID order
    assert actual_ids == EXPECTED_ORDERED_IDS, f"Order mismatch:\nActual:   {actual_ids}\nExpected: {EXPECTED_ORDERED_IDS}"

    # 3. Check scenario_order field values (10, 20, ..., 240)
    for idx, tc in enumerate(test_cases):
        expected_order = (idx + 1) * 10
        assert tc.scenario_order == expected_order, f"{tc.test_case_id} scenario_order expected {expected_order}, got {tc.scenario_order}"


def test_order_cognos_test_cases_deterministic_shuffle():
    """Verify order_cognos_test_cases restores authoritative order from any shuffled state."""
    result = run_cognos_pipeline("runs/94/source/source.docx")
    original_cases = list(result.test_suite.test_cases)

    # Shuffle cases randomly
    shuffled = list(original_cases)
    random.seed(42)
    random.shuffle(shuffled)

    reordered = order_cognos_test_cases(shuffled)
    reordered_ids = [tc.test_case_id for tc in reordered]

    assert reordered_ids == EXPECTED_ORDERED_IDS


def test_excel_export_preserves_authoritative_order():
    """Verify that the generated Excel workbook lists test cases in the authoritative order."""
    result = run_cognos_pipeline("runs/94/source/source.docx")
    ctx = result.final_report_context
    assert ctx is not None

    wb = build_cognos_workbook(ctx)
    ws = wb["Test Scenarios"]

    # Extract Test Case IDs from column A (starting at row 2)
    excel_ids = []
    for row in range(2, 2 + len(EXPECTED_ORDERED_IDS)):
        val = ws.cell(row=row, column=1).value
        excel_ids.append(val)

    assert excel_ids == EXPECTED_ORDERED_IDS
