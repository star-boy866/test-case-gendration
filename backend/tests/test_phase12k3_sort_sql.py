"""
Phase 12K.3 — Unit Tests for Sort Validation SQL Generation (Deterministic).

Covers:
1. Explicit mapped sort field -> ORDER BY source_column ASC
2. Explicit descending sort -> ORDER BY source_column DESC
3. Multiple sort fields -> preserve DSD order (ORDER BY col1 ASC, col2 DESC)
4. Selection criteria present -> WHERE included
5. Selection criteria absent -> no WHERE
6. Unresolved sort field -> SQL Requires Completion with explicit reason
"""

import pytest
from app.domain.cognos_models import (
    ReportDefinition,
    ReportMetadata,
    ReportField,
    SelectionCriterion,
)
from app.domain.cognos_requirement import RequirementSet, CognosRequirement, RequirementCategory
from app.domain.cognos_test_case import CognosTestCase
from app.cognos.rules.sql_generator import DeterministicSqlGenerator


@pytest.fixture
def base_report_def():
    return ReportDefinition(
        metadata=ReportMetadata(
            report_id="PRV-INT-027",
            report_title="Provider License Interface – Term Date Report",
            author="State of New Hampshire",
            creation_date="03/24/2026",
        ),
        report_fields=[
            ReportField(field_name="Prov ID", source_column="P_CURR_ALT_ID", source_table="P_RPT_CLDI_TERM_TB"),
            ReportField(field_name="Prov Sort Name", source_column="P_SORT_NAM", source_table="P_RPT_CLDI_TERM_TB"),
            ReportField(field_name="Prov Lic Cert Num", source_column="P_LIC_CERT_NUM", source_table="P_RPT_CLDI_TERM_TB"),
            ReportField(field_name="OPLC Term Date", source_column="P_CMN_LIC_CERT_END_DT", source_table="P_RPT_CLDI_TERM_TB"),
            ReportField(field_name="MMIS Lic Cert End Date", source_column="P_LIC_CERT_END_DT", source_table="P_RPT_CLDI_TERM_TB"),
            ReportField(field_name="Reval Status CD", source_column="P_REVLDTN_STAT_CD", source_table="P_RPT_CLDI_TERM_TB"),
        ],
        selection_criteria=[
            SelectionCriterion(field="OPLC Term Date", filter_logic="OPLC Term Date >= current date"),
            SelectionCriterion(field="MMIS Lic Cert End Date", filter_logic="MMIS Lic Cert End Date <= 31/12/9999"),
        ],
    )


def test_sort_sql_explicit_mapped_asc(base_report_def):
    """Scenario 1: Explicit mapped sort field -> ORDER BY P_LIC_CERT_NUM ASC with criteria."""
    tc = CognosTestCase(
        test_case_id="PRV027-SORT-02",
        report_id="PRV-INT-027",
        category="Sort Validation",
        methodology_pattern="SORT_VALIDATION",
        source_field="Prov Lic Cert Num",
        source_column="Prov Lic Cert Num",
        processing_rule="Ascending",
        source_table="P_RPT_CLDI_TERM_TB",
        test_case_title="Verify sort order by 'Prov Lic Cert Num' (Ascending) for PRV-INT-027",
        dsd_reference="DSD § Sort By: Prov Lic Cert Num (Ascending)",
    )

    DeterministicSqlGenerator.enrich_test_case(tc, rd=base_report_def)

    assert tc.sql_status == "AVAILABLE"
    assert tc.source_column == "P_LIC_CERT_NUM"
    assert "ORDER BY P_LIC_CERT_NUM ASC;" in tc.validation_sql
    assert "WHERE P_CMN_LIC_CERT_END_DT >= CURRENT_DATE" in tc.validation_sql
    assert "AND P_LIC_CERT_END_DT <= DATE('9999-12-31')" in tc.validation_sql
    assert "P_CURR_ALT_ID" in tc.validation_sql
    assert "P_SORT_NAM" in tc.validation_sql
    assert "P_LIC_CERT_NUM" in tc.validation_sql
    assert "Records returned by the source query must be ordered by: P_LIC_CERT_NUM ASC." in tc.expected_validation


def test_sort_sql_explicit_descending(base_report_def):
    """Scenario 2: Explicit descending sort -> ORDER BY P_SORT_NAM DESC."""
    tc = CognosTestCase(
        test_case_id="PRV027-SORT-03",
        report_id="PRV-INT-027",
        category="Sort Validation",
        methodology_pattern="SORT_VALIDATION",
        source_field="Prov Sort Name",
        source_column="Prov Sort Name",
        processing_rule="Descending",
        source_table="P_RPT_CLDI_TERM_TB",
        test_case_title="Verify sort order by 'Prov Sort Name' (Descending) for PRV-INT-027",
        dsd_reference="DSD § Sort By: Prov Sort Name (Descending)",
    )

    DeterministicSqlGenerator.enrich_test_case(tc, rd=base_report_def)

    assert tc.sql_status == "AVAILABLE"
    assert tc.source_column == "P_SORT_NAM"
    assert tc.sort_direction == "Descending"
    assert "ORDER BY P_SORT_NAM DESC;" in tc.validation_sql
    assert "Records returned by the source query must be ordered by: P_SORT_NAM DESC." in tc.expected_validation


def test_sort_sql_multiple_fields_preserves_order(base_report_def):
    """Scenario 3: Multiple sort fields -> preserves DSD order in ORDER BY."""
    tc = CognosTestCase(
        test_case_id="PRV027-SORT-MULTI",
        report_id="PRV-INT-027",
        category="Sort Validation",
        methodology_pattern="SORT_VALIDATION",
        source_field="Prov ID (Ascending), Prov Sort Name (Descending)",
        source_table="P_RPT_CLDI_TERM_TB",
        test_case_title="Verify compound sort by Prov ID and Prov Sort Name",
        dsd_reference="DSD § Sort By: Prov ID (Ascending), Prov Sort Name (Descending)",
    )

    DeterministicSqlGenerator.enrich_test_case(tc, rd=base_report_def)

    assert tc.sql_status == "AVAILABLE"
    assert "P_CURR_ALT_ID ASC" in tc.validation_sql
    assert "P_SORT_NAM DESC" in tc.validation_sql
    assert "ORDER BY\n    P_CURR_ALT_ID ASC,\n    P_SORT_NAM DESC;" in tc.validation_sql


def test_sort_sql_without_selection_criteria():
    """Scenario 5: Selection criteria absent -> query generated without WHERE clause."""
    rd_no_crit = ReportDefinition(
        metadata=ReportMetadata(report_id="TST-001", report_title="Test Report"),
        report_fields=[
            ReportField(field_name="Provider Alt ID", source_column="P_ALT_ID", source_table="P_TEST_TB"),
        ],
        selection_criteria=[],
    )

    tc = CognosTestCase(
        test_case_id="TST001-SORT-01",
        report_id="TST-001",
        category="Sort Validation",
        methodology_pattern="SORT_VALIDATION",
        source_field="Provider Alt ID",
        processing_rule="Ascending",
        source_table="P_TEST_TB",
        test_case_title="Verify sort by Provider Alt ID",
    )

    DeterministicSqlGenerator.enrich_test_case(tc, rd=rd_no_crit)

    assert tc.sql_status == "AVAILABLE"
    assert "WHERE" not in tc.validation_sql
    assert "FROM P_TEST_TB\nORDER BY P_ALT_ID ASC;" in tc.validation_sql


def test_sort_sql_unresolved_field():
    """Scenario 6: Unresolved sort field (Error Field) -> SQL Requires Completion."""
    tc = CognosTestCase(
        test_case_id="PRV027-SORT-01",
        report_id="PRV-INT-027",
        category="Sort Validation",
        methodology_pattern="SORT_VALIDATION",
        source_field="Error Field",
        source_column="Error Field",
        processing_rule="Ascending",
        source_table="P_RPT_CLDI_TERM_TB",
        test_case_title="Verify sort order by 'Error Field' (Ascending) for PRV-INT-027",
        dsd_reference="DSD § Sort By: Error Field (Ascending)",
    )

    # Empty ReportDefinition with no mapping for "Error Field"
    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="PRV-INT-027", report_title="Test"),
        report_fields=[],
        selection_criteria=[],
    )

    DeterministicSqlGenerator.enrich_test_case(tc, rd=rd)

    assert tc.sql_status == "REQUIRES_COMPLETION"
    assert tc.source_column == "Not resolved from DSD"
    assert tc.validation_sql == ""
    assert 'Sort field "Error Field" has no authoritative source-column mapping in the DSD.' in tc.sql_reason
    assert 'Records returned by the source query must be ordered by the authoritative source column corresponding to "Error Field" in Ascending order.' in tc.expected_validation
    assert tc.source_mappings[0]["column"] == "Not resolved from DSD"
