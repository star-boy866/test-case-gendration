"""
Phase 13 Unit Tests: Code-to-Description / Valid Values SQL Generation.

Verifies:
1. MMIS agency code (P_MMIS_LIC_CERT_AGCY_CD) generates joined SQL with R_VV_TB.
2. OPLC agency code (P_LIC_CERT_AGCY_CD) generates joined SQL with R_VV_TB.
3. LOOKUP_VALIDATION test cases have sql_status == "AVAILABLE" and populated validation_sql.
4. DB Report Data fields with valid-value processing rules generate joined SQL with R_VV_TB.
5. Selection criteria WHERE clauses are preserved with proper alias prefixing.
"""

import pytest
from app.domain.cognos_models import (
    ReportDefinition,
    ReportMetadata,
    ReportField,
    SelectionCriterion,
)
from app.domain.cognos_requirement import (
    CognosRequirement,
    RequirementCategory,
    RequirementConfidence,
    RequirementSet,
)
from app.domain.cognos_test_case import CognosTestCase
from app.cognos.rules.sql_generator import DeterministicSqlGenerator
from app.cognos.rules.scenario_expander import ScenarioExpander
from app.cognos.rules.scenario_patterns import discover_applicable_patterns, MethodologyPattern


def test_mmis_agency_code_lookup_sql():
    """Verify MMIS agency code produces exact expected SQL with R_VV_TB join."""
    tc = CognosTestCase(
        report_id="PRV-INT-028",
        test_case_title="Verify lookup for 'Prov Agency' in PRV-INT-028",
        category="Lookup Validation",
        methodology_pattern="LOOKUP_VALIDATION",
        source_table="P_RPT_CLDI_ERR_TB",
        source_column="P_MMIS_LIC_CERT_AGCY_CD",
        source_field="Prov Agency",
        processing_rule="Display code, hyphen, short description from valid values",
        lookup_table="R_VV_TB",
        lookup_code_column="R_VV_CD",
        lookup_description_column="R_VV_SHORT_DESC",
        lookup_domain="P_MMIS_LIC_CERT_AGCY_CD",
    )

    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="PRV-INT-028", report_title="Provider Error Report"),
        report_fields=[
            ReportField(
                field_name="Prov Agency",
                business_label="Prov Agency",
                source_table="P_RPT_CLDI_ERR_TB",
                source_column="P_MMIS_LIC_CERT_AGCY_CD",
                processing_rule="Display code, hyphen, short description from valid values",
            )
        ],
    )

    DeterministicSqlGenerator.enrich_test_case(tc, rd=rd)

    assert tc.sql_status == "AVAILABLE"
    assert "FROM P_RPT_CLDI_ERR_TB p" in tc.validation_sql
    assert "LEFT JOIN R_VV_TB r" in tc.validation_sql
    assert "ON p.P_MMIS_LIC_CERT_AGCY_CD = r.R_VV_CD" in tc.validation_sql
    assert "r.R_VV_DOMAIN_NAME = 'P_MMIS_LIC_CERT_AGCY_CD'" in tc.validation_sql
    assert "p.P_MMIS_LIC_CERT_AGCY_CD || ' - ' || r.R_VV_SHORT_DESC AS PROV_AGENCY" in tc.validation_sql


def test_oplc_agency_code_lookup_sql():
    """Verify OPLC agency code produces exact expected SQL with R_VV_TB join."""
    tc = CognosTestCase(
        report_id="PRV-INT-028",
        test_case_title="Verify lookup for 'Prov Agency' in PRV-INT-028",
        category="Lookup Validation",
        methodology_pattern="LOOKUP_VALIDATION",
        source_table="P_RPT_CLDI_ERR_TB",
        source_column="P_LIC_CERT_AGCY_CD",
        source_field="Prov Agency",
        processing_rule="Display code, hyphen, short description from valid values",
        lookup_table="R_VV_TB",
        lookup_code_column="R_VV_CD",
        lookup_description_column="R_VV_SHORT_DESC",
        lookup_domain="P_LIC_CERT_AGCY_CD",
    )

    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="PRV-INT-028", report_title="Provider Error Report"),
        report_fields=[
            ReportField(
                field_name="Prov Agency",
                business_label="Prov Agency",
                source_table="P_RPT_CLDI_ERR_TB",
                source_column="P_LIC_CERT_AGCY_CD",
                processing_rule="Display code, hyphen, short description from valid values",
            )
        ],
    )

    DeterministicSqlGenerator.enrich_test_case(tc, rd=rd)

    assert tc.sql_status == "AVAILABLE"
    assert "FROM P_RPT_CLDI_ERR_TB p" in tc.validation_sql
    assert "LEFT JOIN R_VV_TB r" in tc.validation_sql
    assert "ON p.P_LIC_CERT_AGCY_CD = r.R_VV_CD" in tc.validation_sql
    assert "r.R_VV_DOMAIN_NAME = 'P_LIC_CERT_AGCY_CD'" in tc.validation_sql
    assert "p.P_LIC_CERT_AGCY_CD || ' - ' || r.R_VV_SHORT_DESC AS PROV_AGENCY" in tc.validation_sql


def test_db_report_data_with_valid_values_rule():
    """Verify DB_REPORT_DATA_VALIDATION detects valid-values processing rule and generates joined SQL."""
    tc = CognosTestCase(
        report_id="PRV-INT-028",
        test_case_title="Verify DB mapping for 'Prov Agency' in PRV-INT-028",
        category="DB Report Data Validation",
        methodology_pattern="DB_REPORT_DATA_VALIDATION",
        source_table="P_RPT_CLDI_ERR_TB",
        source_column="P_MMIS_LIC_CERT_AGCY_CD",
        source_field="Prov Agency",
        processing_rule="Display code, hyphen, short description from valid values",
    )

    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="PRV-INT-028", report_title="Provider Error Report"),
        report_fields=[
            ReportField(
                field_name="Prov Agency",
                business_label="Prov Agency",
                source_table="P_RPT_CLDI_ERR_TB",
                source_column="P_MMIS_LIC_CERT_AGCY_CD",
                processing_rule="Display code, hyphen, short description from valid values",
            )
        ],
    )

    DeterministicSqlGenerator.enrich_test_case(tc, rd=rd)

    assert tc.sql_status == "AVAILABLE"
    assert "FROM P_RPT_CLDI_ERR_TB p" in tc.validation_sql
    assert "LEFT JOIN R_VV_TB r" in tc.validation_sql
    assert "ON p.P_MMIS_LIC_CERT_AGCY_CD = r.R_VV_CD" in tc.validation_sql
    assert "r.R_VV_DOMAIN_NAME = 'P_MMIS_LIC_CERT_AGCY_CD'" in tc.validation_sql
    assert "p.P_MMIS_LIC_CERT_AGCY_CD || ' - ' || r.R_VV_SHORT_DESC AS PROV_AGENCY" in tc.validation_sql


def test_lookup_validation_with_selection_criteria():
    """Verify criteria WHERE clauses are preserved and prefixed in lookup SQL."""
    tc = CognosTestCase(
        report_id="PRV-INT-028",
        test_case_title="Verify lookup for 'Prov Agency' in PRV-INT-028",
        category="Lookup Validation",
        methodology_pattern="LOOKUP_VALIDATION",
        source_table="P_RPT_CLDI_ERR_TB",
        source_column="P_MMIS_LIC_CERT_AGCY_CD",
        source_field="Prov Agency",
        processing_rule="Display code, hyphen, short description from valid values",
    )

    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="PRV-INT-028", report_title="Provider Error Report"),
        report_fields=[
            ReportField(
                field_name="Prov Agency",
                business_label="Prov Agency",
                source_table="P_RPT_CLDI_ERR_TB",
                source_column="P_MMIS_LIC_CERT_AGCY_CD",
                processing_rule="Display code, hyphen, short description from valid values",
            )
        ],
        selection_criteria=[
            SelectionCriterion(field="P_MMIS_LIC_CERT_AGCY_CD", filter_logic="P_MMIS_LIC_CERT_AGCY_CD >= '01'")
        ]
    )

    DeterministicSqlGenerator.enrich_test_case(tc, rd=rd)

    assert tc.sql_status == "AVAILABLE"
    assert "WHERE p.P_MMIS_LIC_CERT_AGCY_CD >= '01'" in tc.validation_sql


def test_scenario_expander_lookup_end_to_end():
    """Verify ScenarioExpander produces LOOKUP_VALIDATION test case with available SQL."""
    req = CognosRequirement(
        requirement_id="REQ-028-COL-001",
        category=RequirementCategory.COLUMN,
        field="Prov Agency",
        business_label="Prov Agency",
        source_table="P_RPT_CLDI_ERR_TB",
        source_columns=["P_MMIS_LIC_CERT_AGCY_CD"],
        processing_rule="Display code, hyphen, short description from valid values",
        requirement_text="Report field 'Prov Agency' must be formatted and mapped to P_RPT_CLDI_ERR_TB.P_MMIS_LIC_CERT_AGCY_CD. Processing Rule: Display code, hyphen, short description from valid values",
        confidence=RequirementConfidence.HIGH,
    )

    req_set = RequirementSet(requirements=[req])
    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="PRV-INT-028", report_title="Provider Error Report"),
        report_fields=[
            ReportField(
                field_name="Prov Agency",
                business_label="Prov Agency",
                source_table="P_RPT_CLDI_ERR_TB",
                source_column="P_MMIS_LIC_CERT_AGCY_CD",
                processing_rule="Display code, hyphen, short description from valid values",
            )
        ],
    )

    report = discover_applicable_patterns(req_set.requirements, rd)
    lookup_pattern = next((p for p in report.generated if p.pattern == MethodologyPattern.LOOKUP_VALIDATION), None)
    assert lookup_pattern is not None

    expander = ScenarioExpander(rd, req_set)
    cases = expander.expand([lookup_pattern])

    assert len(cases) >= 1
    tc = cases[0]
    assert tc.category == "Lookup Validation"
    assert tc.sql_status == "AVAILABLE"
    assert "P_MMIS_LIC_CERT_AGCY_CD || ' - ' || r.R_VV_SHORT_DESC AS PROV_AGENCY" in tc.validation_sql
