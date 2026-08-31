"""
Tests for Phase 15.8: Use DSD Business Labels as SQL Output Column Aliases.

Ensures that all generated validation SQL uses the exact, authoritative DSD Business Label
as a double-quoted SQL alias (e.g., AS "Prov ID", AS "Prov Sort Name").
"""

import pytest
from pathlib import Path
from app.domain.cognos_models import ReportDefinition, ReportMetadata, ReportField
from app.domain.cognos_requirement import RequirementSet, RequirementCategory, CognosRequirement
from app.domain.cognos_test_case import CognosTestCase
from app.cognos.rules.sql_generator import DeterministicSqlGenerator
from app.cognos.pipeline import run_cognos_pipeline


def test_business_label_exact_quoted_aliases_prv027():
    """Verify PRV-INT-027 consolidated report-level SQL uses exact quoted DSD Business Labels."""
    source_path = Path("runs/210/source/source.docx")
    if not source_path.exists():
        source_path = Path("tests/fixtures/golden_sources/PRV-INT-027_DSD.docx")
    if not source_path.exists():
        source_path = Path("runs/94/source/source.docx")

    res = run_cognos_pipeline(source_path)
    test_cases = res.test_suite.test_cases

    # 1. Check Consolidated DB Report Data Validation (PRV027-DBRV-01)
    dbrv_cases = [tc for tc in test_cases if "DBRV" in tc.test_case_id or tc.category == "DB Report Data Validation"]
    assert len(dbrv_cases) == 1
    tc_dbrv = dbrv_cases[0]
    sql = tc_dbrv.validation_sql

    assert 'AS "Prov ID"' in sql
    assert 'AS "Prov Sort Name"' in sql
    assert 'AS "Prov Lic Cert Num"' in sql
    assert 'AS "OPLC Term Date"' in sql
    assert 'AS "MMIS Lic Cert End Date"' in sql
    assert 'AS "Reval Stat Cd"' in sql

    # Ensure no old unquoted or underscored aliases exist
    assert "Prov_ID" not in sql
    assert "Prov_Sort_Name" not in sql
    assert "Prov_Lic_Cert_Num" not in sql
    assert "OPLC_Term_Date" not in sql
    assert "MMIS_Lic_Cert_End_Date" not in sql
    assert "Reval_Stat_Cd" not in sql


def test_label_validation_sql_quoted_aliases():
    """Verify Label Validation SQL uses exact quoted DSD Business Labels."""
    source_path = Path("runs/94/source/source.docx")
    res = run_cognos_pipeline(source_path)
    
    labe_cases = [tc for tc in res.test_suite.test_cases if tc.test_case_id == "PRV027-LABE-01" or tc.category == "Label Validation"]
    assert len(labe_cases) >= 1
    tc_labe = labe_cases[0]
    sql = tc_labe.validation_sql

    assert 'AS "Prov ID"' in sql
    assert 'AS "Prov Sort Name"' in sql
    assert 'AS "Prov Lic Cert Num"' in sql
    assert 'AS "OPLC Term Date"' in sql
    assert 'AS "MMIS Lic Cert End Date"' in sql
    assert 'AS "Reval Stat Cd"' in sql


def test_generic_and_future_dsd_labels_nd_ak():
    """Verify generic rule handles arbitrary DSD business labels across states (e.g. ND, AK)."""
    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="RPT-OPR-TPL-016", report_title="TPL Recipient Daily"),
        report_fields=[
            ReportField(field_name="TPL RECIP ND NUM", business_label="TPL RECIP ND NUM", source_column="TPL_RECIP_NUM", source_table="TPL_DATA_TB"),
            ReportField(field_name="Provider Agency", business_label="Provider Agency", source_column="PRV_AGCY_CD", source_table="TPL_DATA_TB"),
            ReportField(field_name="Claim Line Item ($)", business_label="Claim Line Item ($)", source_column="CLM_AMT", source_table="TPL_DATA_TB"),
        ],
        selection_criteria=[],
    )

    tc = CognosTestCase(
        report_id="RPT-OPR-TPL-016",
        category="Label Validation",
        methodology_pattern="LABEL_VALIDATION",
        source_table="TPL_DATA_TB",
        test_case_title="Verify column labels",
    )

    DeterministicSqlGenerator.enrich_test_case(tc, rd=rd)

    assert tc.sql_status == "AVAILABLE"
    assert 'AS "TPL RECIP ND NUM"' in tc.validation_sql
    assert 'AS "Provider Agency"' in tc.validation_sql
    assert 'AS "Claim Line Item ($)"' in tc.validation_sql
    assert "TPL_DATA_TB" in tc.validation_sql


def test_duplicate_label_disambiguation():
    """Verify duplicate Business Labels are safely disambiguated in SQL without crashing."""
    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="DUP-001", report_title="Duplicate Label Test"),
        report_fields=[
            ReportField(field_name="Status", business_label="Status", source_column="STAT_CD_1", source_table="TEST_TB"),
            ReportField(field_name="Status", business_label="Status", source_column="STAT_CD_2", source_table="TEST_TB"),
        ],
        selection_criteria=[],
    )

    tc = CognosTestCase(
        report_id="DUP-001",
        category="Label Validation",
        methodology_pattern="LABEL_VALIDATION",
        source_table="TEST_TB",
        test_case_title="Verify column labels with duplicates",
    )

    DeterministicSqlGenerator.enrich_test_case(tc, rd=rd)

    assert tc.sql_status == "AVAILABLE"
    assert 'AS "Status"' in tc.validation_sql
    assert 'AS "Status (2)"' in tc.validation_sql


def test_missing_label_fallback():
    """Verify missing/empty Business Label falls back cleanly to the source column name."""
    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="NOLBL-001", report_title="No Label Test"),
        report_fields=[
            ReportField(field_name="", business_label="", source_column="RAW_UNLABELLED_COL", source_table="TEST_TB"),
        ],
        selection_criteria=[],
    )

    tc = CognosTestCase(
        report_id="NOLBL-001",
        category="Label Validation",
        methodology_pattern="LABEL_VALIDATION",
        source_table="TEST_TB",
        test_case_title="Verify column labels without business labels",
    )

    DeterministicSqlGenerator.enrich_test_case(tc, rd=rd)

    assert tc.sql_status == "AVAILABLE"
    assert 'AS "RAW_UNLABELLED_COL"' in tc.validation_sql
