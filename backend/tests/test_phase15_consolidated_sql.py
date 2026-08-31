import pytest
from pathlib import Path
from app.cognos.pipeline import run_cognos_pipeline

def test_phase15_consolidated_sql():
    source_path = Path("runs/210/source/source.docx")
    if not source_path.exists():
        source_path = Path("tests/fixtures/golden_sources/PRV-INT-027_DSD.docx")
    
    res = run_cognos_pipeline(source_path)
    test_cases = res.test_suite.test_cases

    dbrv_cases = [tc for tc in test_cases if "DBRV" in tc.test_case_id or tc.category == "DB Report Data Validation"]
    assert len(dbrv_cases) == 1, f"Expected 1 DBRV case, found {len(dbrv_cases)}"

    tc = dbrv_cases[0]
    # Check shared group
    shared_group = tc.shared_sql_group
    assert shared_group == "PRVINT027_FULL_REPORT_SQL" or "FULL_REPORT_SQL" in shared_group

    full_sql = tc.validation_sql
    assert full_sql, "validation_sql should not be empty"
    assert "SELECT" in full_sql
    assert "FROM P_RPT_CLDI_TERM_TB" in full_sql
    assert "R_VV_TB" in full_sql
    assert 'AS "Reval Stat Cd"' in full_sql
    assert 'AS "Prov ID"' in full_sql
    assert 'AS "Prov Sort Name"' in full_sql
    assert 'AS "Prov Lic Cert Num"' in full_sql
    assert 'AS "OPLC Term Date"' in full_sql
    assert 'AS "MMIS Lic Cert End Date"' in full_sql

    assert tc.report_validation_sql == full_sql
    assert tc.sql_status == "AVAILABLE"
    assert tc.source_column, f"Missing source_column in {tc.test_case_id}"
    assert tc.source_field, f"Missing source_field in {tc.test_case_id}"
    assert tc.sql_purpose, f"Missing sql_purpose in {tc.test_case_id}"
    assert tc.expected_validation, f"Missing expected_validation in {tc.test_case_id}"

    # Verify target mappings include all 6 fields
    mappings = {m['field']: m['column'] for m in tc.source_mappings}
    assert "Prov ID" in mappings
    assert "Prov Sort Name" in mappings
    assert "Prov Lic Cert Num" in mappings
    assert "OPLC Term Date" in mappings
    assert "MMIS Lic Cert End Date" in mappings
    assert "Reval Stat Cd" in mappings
