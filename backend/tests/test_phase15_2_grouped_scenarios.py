import pytest
from pathlib import Path
from app.cognos.pipeline import run_cognos_pipeline

def test_phase15_2_grouped_scenarios():
    source_path = Path("runs/210/source/source.docx")
    if not source_path.exists():
        source_path = Path("tests/fixtures/golden_sources/PRV-INT-027_DSD.docx")
    
    res = run_cognos_pipeline(source_path)
    test_cases = res.test_suite.test_cases

    # 1. DB Report Data Validation — Exactly 1 Consolidated Scenario
    dbrv_cases = [tc for tc in test_cases if "DBRV" in tc.test_case_id or tc.category == "DB Report Data Validation"]
    assert len(dbrv_cases) == 1, f"Expected exactly 1 DBRV case, found {len(dbrv_cases)}"
    
    dbrv = dbrv_cases[0]
    assert dbrv.test_case_id == "PRV027-DBRV-01"
    assert dbrv.test_case_title == "Verify all report data mappings for PRV-INT-027 against the source database"
    assert len(dbrv.requirement_ids) == 6, f"Expected 6 requirement IDs in DBRV-01, found {len(dbrv.requirement_ids)}"
    assert dbrv.sql_status == "AVAILABLE"
    
    # Check full report SQL
    assert "SELECT" in dbrv.validation_sql
    assert "P_CURR_ALT_ID" in dbrv.validation_sql
    assert "P_SORT_NAM" in dbrv.validation_sql
    assert "P_LIC_CERT_NUM" in dbrv.validation_sql
    assert "P_CMN_LIC_CERT_END_DT" in dbrv.validation_sql
    assert "P_LIC_CERT_END_DT" in dbrv.validation_sql
    assert "P_REVLDTN_STAT_CD" in dbrv.validation_sql
    assert "R_VV_TB" in dbrv.validation_sql
    assert "FROM P_RPT_CLDI_TERM_TB" in dbrv.validation_sql
    
    # Check source mappings
    mapped_fields = [m["field"] for m in dbrv.source_mappings]
    assert any("Prov ID" in f for f in mapped_fields)
    assert any("Prov Sort Name" in f for f in mapped_fields)
    assert any("Prov Lic Cert Num" in f for f in mapped_fields)
    assert any("OPLC Term Date" in f for f in mapped_fields)
    assert any("MMIS Lic Cert End Date" in f for f in mapped_fields)
    assert any("Reval Stat Cd" in f for f in mapped_fields)

    # 2. Sort Validation — Exactly 1 Consolidated Scenario
    sort_cases = [tc for tc in test_cases if "SORT" in tc.test_case_id or tc.category == "Sort Validation"]
    assert len(sort_cases) == 1, f"Expected exactly 1 SORT case, found {len(sort_cases)}"
    
    sort_tc = sort_cases[0]
    assert sort_tc.test_case_id == "PRV027-SORT-01"
    assert sort_tc.test_case_title == "Verify report sort order for PRV-INT-027"
    assert len(sort_tc.requirement_ids) == 2, f"Expected 2 requirement IDs in SORT-01, found {len(sort_tc.requirement_ids)}"
    
    # Check sort keys in mappings
    sort_fields = [m["field"] for m in sort_tc.source_mappings]
    assert any("Prov Lic Cert Num" in f for f in sort_fields)
    assert any("Error Field" in f for f in sort_fields)
    
    # 3. Overall Count
    assert len(test_cases) == 18, f"Expected 18 total scenarios, found {len(test_cases)}"
