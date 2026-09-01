import pytest
from pathlib import Path
from app.cognos.pipeline import run_cognos_pipeline
from app.services.cognos_excel_compiler import build_cognos_workbook

def test_excel_test_scenarios_columns():
    docx_path = Path("runs/94/source/source.docx")
    if not docx_path.exists():
        docx_path = Path("tests/fixtures/golden_sources/PRV-INT-027_DSD.docx")

    res = run_cognos_pipeline(docx_path)
    ctx = res.final_report_context
    assert ctx is not None

    wb = build_cognos_workbook(ctx)
    ws = wb["Test Scenarios"]

    # 1. Verify exact headers
    expected_headers = [
        "Test Case ID",
        "Category",
        "Test Objective",
        "DSD / Technical Reference",
        "Preconditions / Test Data",
        "Test Steps",
        "Expected Result",
        "Generated SQL",
    ]

    actual_headers = [ws.cell(row=1, column=c).value for c in range(1, len(expected_headers) + 1)]
    assert actual_headers == expected_headers, f"Header mismatch: {actual_headers}"

    # Verify no extra headers beyond column 8
    assert ws.cell(row=1, column=9).value is None

    # 2. Verify excluded columns are NOT present
    removed_cols = [
        "Evidence Required",
        "Evidence Type",
        "Open Item / Notes",
        "Requirement ID(s)",
        "Source Page",
        "Source Section",
        "LLM Refinement Status",
        "Status",
        "Confidence",
    ]
    for col_name in removed_cols:
        assert col_name not in actual_headers

    # 3. Verify Generated SQL is populated in column 8 for SQL scenarios
    found_sql = False
    for row in range(2, ws.max_row + 1):
        tc_id = ws.cell(row=row, column=1).value
        sql_val = ws.cell(row=row, column=8).value
        if tc_id == "PRV027-DBRV-01":
            assert sql_val is not None and "SELECT" in sql_val and "P_RPT_CLDI_TERM_TB" in sql_val
            found_sql = True
        elif tc_id == "PRV027-LABE-01":
            assert sql_val is not None and "SELECT" in sql_val

    assert found_sql, "PRV027-DBRV-01 SQL not found in Generated SQL column"

    # 4. Verify Evidence Snapshots sheet is excluded
    assert "Evidence Snapshots" not in wb.sheetnames, f"Unexpected 'Evidence Snapshots' sheet found: {wb.sheetnames}"
