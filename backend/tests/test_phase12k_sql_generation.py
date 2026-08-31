import pytest
from app.domain.cognos_models import ReportDefinition, ReportMetadata, ReportField
from app.domain.cognos_requirement import RequirementSet, RequirementCategory, CognosRequirement
from app.domain.cognos_test_case import CognosTestCase
from app.cognos.rules.sql_generator import DeterministicSqlGenerator
from app.cognos.pipeline import run_cognos_pipeline


def test_db_count_sql_generation_without_criteria():
    tc = CognosTestCase(
        report_id="OTHER-RPT-001",
        report_name="Other Report",
        category="DB Count Validation",
        methodology_pattern="DB_COUNT_VALIDATION",
        test_case_title="Verify DB counts match report totals",
        test_case_description="Count validation",
        objective="Validate DB count",
        test_steps="1. Step",
        expected_result="Match",
        source_table="OTHER_TABLE",
        source_column="Total Errors",
    )
    DeterministicSqlGenerator.enrich_test_case(tc)

    assert tc.sql_status == "AVAILABLE"
    assert tc.validation_sql.strip() == "SELECT COUNT(*)\nFROM OTHER_TABLE;"
    assert "Database COUNT(*) must equal the report's 'Total Errors' count" in tc.expected_validation


def test_db_count_sql_generation_with_single_criterion():
    tc = CognosTestCase(
        report_id="OTHER-RPT-001",
        report_name="Term Date Report",
        category="DB Count Validation",
        methodology_pattern="DB_COUNT_VALIDATION",
        test_case_title="Verify DB counts with single criterion",
        test_case_description="Count validation",
        objective="Validate DB count",
        test_steps="1. Step",
        expected_result="Match",
        source_table="P_RPT_CLDI_TERM_TB",
        source_column="Total Errors",
        selection_criteria="OPLC Term Date >= current date",
    )
    DeterministicSqlGenerator.enrich_test_case(tc)

    assert tc.sql_status == "AVAILABLE"
    assert tc.validation_sql.strip() == "SELECT COUNT(*)\nFROM P_RPT_CLDI_TERM_TB\nWHERE P_CMN_LIC_CERT_END_DT >= CURRENT_DATE;"


def test_db_count_sql_generation_with_multiple_criteria_and_operator_preservation():
    tc = CognosTestCase(
        report_id="OTHER-RPT-001",
        report_name="Term Date Report",
        category="DB Count Validation",
        methodology_pattern="DB_COUNT_VALIDATION",
        test_case_title="Verify DB counts with multiple criteria",
        test_case_description="Count validation",
        objective="Validate DB count",
        test_steps="1. Step",
        expected_result="Match",
        source_table="P_RPT_CLDI_TERM_TB",
        source_column="Total Errors",
        selection_criteria="OPLC Term Date >= current date\nMMIS Lic Cert End Date <= 31/12/9999",
    )
    DeterministicSqlGenerator.enrich_test_case(tc)

    assert tc.sql_status == "AVAILABLE"
    expected_sql = (
        "SELECT COUNT(*)\n"
        "FROM P_RPT_CLDI_TERM_TB\n"
        "WHERE P_CMN_LIC_CERT_END_DT >= CURRENT_DATE\n"
        "  AND P_LIC_CERT_END_DT <= DATE('9999-12-31');"
    )
    assert tc.validation_sql.strip() == expected_sql
    assert len(tc.source_mappings) == 2
    assert tc.source_mappings[0]["field"] == "OPLC Term Date"
    assert tc.source_mappings[0]["column"] == "P_CMN_LIC_CERT_END_DT"
    assert tc.source_mappings[1]["field"] == "MMIS Lic Cert End Date"
    assert tc.source_mappings[1]["column"] == "P_LIC_CERT_END_DT"


def test_date_normalization_formats():
    val_cur, is_d1 = DeterministicSqlGenerator._normalize_date_value("current date")
    assert val_cur == "CURRENT_DATE"
    assert is_d1 is True

    val_dmy, is_d2 = DeterministicSqlGenerator._normalize_date_value("31/12/9999")
    assert val_dmy == "DATE('9999-12-31')"
    assert is_d2 is True

    val_iso, is_d3 = DeterministicSqlGenerator._normalize_date_value("2025-06-30")
    assert val_iso == "DATE('2025-06-30')"
    assert is_d3 is True


def test_unmapped_field_requires_completion():
    tc = CognosTestCase(
        report_id="OTHER-RPT-001",
        report_name="Other Report",
        category="DB Count Validation",
        methodology_pattern="DB_COUNT_VALIDATION",
        test_case_title="Verify unmapped field handling",
        test_case_description="Count validation",
        objective="Validate DB count",
        test_steps="1. Step",
        expected_result="Match",
        source_table="P_RPT_CLDI_TERM_TB",
        source_column="Total Errors",
        selection_criteria="Unmapped Custom Field >= current date",
    )
    DeterministicSqlGenerator.enrich_test_case(tc)

    assert tc.sql_status == "REQUIRES_COMPLETION"
    assert "could not be mapped to an authoritative source column" in tc.sql_reason


def test_parameterized_criterion():
    field_to_col = {"oplctermdate": "P_CMN_LIC_CERT_END_DT"}
    cond, mapping, err = DeterministicSqlGenerator._parse_and_bind_criterion(
        "OPLC Term Date = ?Prompt?", field_to_col, "P_RPT_CLDI_TERM_TB"
    )
    assert err is None
    assert cond == "P_CMN_LIC_CERT_END_DT = :oplc_term_date"
    assert mapping is not None
    assert mapping["column"] == "P_CMN_LIC_CERT_END_DT"


def test_db_report_data_sql_generation():
    tc = CognosTestCase(
        report_id="PRV-INT-027",
        report_name="Term Date Report",
        category="DB Report Data Validation",
        methodology_pattern="DB_REPORT_DATA_VALIDATION",
        test_case_title="Verify DB mapping for MMIS Lic Cert End Date",
        test_case_description="Field mapping",
        objective="Validate column mapping",
        test_steps="1. Step",
        expected_result="Match",
        source_table="P_RPT_CLDI_TERM_TB",
        source_column="P_LIC_CERT_END_DT",
        source_field="MMIS Lic Cert End Date",
    )
    DeterministicSqlGenerator.enrich_test_case(tc)

    assert tc.sql_status == "AVAILABLE"
    expected_sql = (
        "SELECT P_LIC_CERT_END_DT\n"
        "FROM P_RPT_CLDI_TERM_TB;"
    )
    assert tc.validation_sql.strip() == expected_sql
    assert "P_RPT_CLDI_TERM_TB.P_LIC_CERT_END_DT" in tc.expected_validation


def test_incomplete_metadata_sql_status():
    tc = CognosTestCase(
        report_id="PRV-INT-027",
        report_name="Term Date Report",
        category="DB Report Data Validation",
        methodology_pattern="DB_REPORT_DATA_VALIDATION",
        test_case_title="Incomplete test",
        test_case_description="Incomplete",
        objective="Incomplete",
        test_steps="1. Step",
        expected_result="Match",
        source_table="NOT_DEFINED",
        source_column="NOT_DEFINED",
    )
    DeterministicSqlGenerator.enrich_test_case(tc)

    assert tc.sql_status == "UNAVAILABLE"
    assert "incomplete" in tc.sql_reason.lower()


def test_pipeline_integration_prv027_dbco_01():
    result = run_cognos_pipeline("runs/94/source/source.docx")
    
    db_count_cases = [tc for tc in result.test_suite.test_cases if tc.test_case_id == "PRV027-DBCO-01"]
    assert len(db_count_cases) == 1
    tc_count = db_count_cases[0]
    assert tc_count.source_table == "P_RPT_CLDI_TERM_TB"
    assert tc_count.sql_status == "AVAILABLE"
    
    expected_sql = (
        "SELECT COUNT(*)\n"
        "FROM P_RPT_CLDI_TERM_TB\n"
        "WHERE P_CMN_LIC_CERT_END_DT >= CURRENT_DATE\n"
        "  AND P_LIC_CERT_END_DT <= DATE('9999-12-31');"
    )
    assert tc_count.validation_sql.strip() == expected_sql
    assert "Total Errors" in tc_count.expected_validation
    assert len(tc_count.source_mappings) == 2
    assert tc_count.traceability_source == "Selection Criteria • Report Specification / Report Body"


def test_pipeline_integration_prv027_labe_01():
    result = run_cognos_pipeline("runs/94/source/source.docx")
    
    label_cases = [tc for tc in result.test_suite.test_cases if tc.test_case_id == "PRV027-LABE-01"]
    assert len(label_cases) == 1
    tc_label = label_cases[0]
    assert tc_label.source_table == "P_RPT_CLDI_TERM_TB"
    assert tc_label.sql_status == "AVAILABLE"
    
    expected_sql = (
        "SELECT\n"
        "    P_CURR_ALT_ID         AS \"Prov ID\",\n"
        "    P_SORT_NAM            AS \"Prov Sort Name\",\n"
        "    P_LIC_CERT_NUM        AS \"Prov Lic Cert Num\",\n"
        "    P_CMN_LIC_CERT_END_DT AS \"OPLC Term Date\",\n"
        "    P_LIC_CERT_END_DT     AS \"MMIS Lic Cert End Date\",\n"
        "    P_REVLDTN_STAT_CD     AS \"Reval Stat Cd\"\n"
        "FROM P_RPT_CLDI_TERM_TB\n"
        "WHERE P_CMN_LIC_CERT_END_DT >= CURRENT_DATE\n"
        "  AND P_LIC_CERT_END_DT <= DATE('9999-12-31');"
    )
    assert tc_label.validation_sql.strip() == expected_sql
    assert "Retrieve the source records used to validate the report-body labels" in tc_label.expected_validation
    assert len(tc_label.source_mappings) == 6
    assert "P_CURR_ALT_ID" in tc_label.source_columns
    assert "P_REVLDTN_STAT_CD" in tc_label.source_columns
    assert "Selection Criteria" in tc_label.traceability_source


def test_label_validation_without_criteria():
    tc = CognosTestCase(
        report_id="OTHER-RPT-002",
        report_name="Simple Report",
        category="Label Validation",
        methodology_pattern="LABEL_VALIDATION",
        test_case_title="Verify column labels",
        test_case_description="Label validation",
        objective="Validate labels",
        test_steps="1. Step",
        expected_result="Match",
        source_table="OTHER_TABLE",
        source_mappings=[
            {"field": "Column 1", "column": "COL_ONE", "table": "OTHER_TABLE"},
            {"field": "Column 2", "column": "COL_TWO", "table": "OTHER_TABLE"},
        ]
    )
    DeterministicSqlGenerator.enrich_test_case(tc)

    assert tc.sql_status == "AVAILABLE"
    expected_sql = (
        "SELECT\n"
        "    COL_ONE AS \"Column 1\",\n"
        "    COL_TWO AS \"Column 2\"\n"
        "FROM OTHER_TABLE;"
    )
    assert tc.validation_sql.strip() == expected_sql
    assert tc.selection_criteria == ""


def test_label_validation_multiple_tables_requires_completion():
    tc = CognosTestCase(
        report_id="OTHER-RPT-003",
        report_name="Multi Table Report",
        category="Label Validation",
        methodology_pattern="LABEL_VALIDATION",
        test_case_title="Verify multi table labels",
        test_case_description="Label validation",
        objective="Validate labels",
        test_steps="1. Step",
        expected_result="Match",
        source_mappings=[
            {"field": "Column A", "column": "COL_A", "table": "TABLE_A"},
            {"field": "Column B", "column": "COL_B", "table": "TABLE_B"},
        ]
    )
    DeterministicSqlGenerator.enrich_test_case(tc)

    assert tc.sql_status == "REQUIRES_COMPLETION"
    assert "Multiple source tables detected" in tc.sql_reason


def test_label_validation_incomplete_metadata():
    tc = CognosTestCase(
        report_id="OTHER-RPT-004",
        report_name="Incomplete Report",
        category="Label Validation",
        methodology_pattern="LABEL_VALIDATION",
        test_case_title="Verify incomplete labels",
        test_case_description="Label validation",
        objective="Validate labels",
        test_steps="1. Step",
        expected_result="Match",
        source_table="NOT_DEFINED",
        source_column="NOT_DEFINED",
    )
    DeterministicSqlGenerator.enrich_test_case(tc)

    assert tc.sql_status == "UNAVAILABLE"
    assert "incomplete" in tc.sql_reason.lower()

