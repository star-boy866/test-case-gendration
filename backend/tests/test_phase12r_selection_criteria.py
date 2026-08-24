"""
Unit and Integration Tests for Phase 12R: Report Selection Criteria Validation (SELC-01).

Covers:
1. Applicability when selection criteria are populated vs empty.
2. Structure and content of PRV027-SELC-01 scenario (Category, Title, Objective, Steps, Expected Result).
3. Mapping of report fields to authoritative source columns:
   OPLC Term Date -> P_CMN_LIC_CERT_END_DT
   MMIS Lic Cert End Date -> P_LIC_CERT_END_DT
4. Normalized SQL WHERE conditions:
   P_CMN_LIC_CERT_END_DT >= CURRENT_DATE
   P_LIC_CERT_END_DT <= DATE('9999-12-31')
5. Deterministic Validation SQL generation for selection criteria.
6. Evidence references (DSD_SEMANTIC_PROOF and SOURCE_DSD_SNAPSHOT for Report Selection Criteria).
7. Authoritative 25-scenario order for PRV-INT-027 with SELC at position 04.
"""

from pathlib import Path
import pytest

from app.cognos.pipeline import run_cognos_pipeline
from app.cognos.rules.scenario_patterns import (
    MethodologyPattern,
    discover_applicable_patterns,
)
from app.cognos.rules.test_case_builder import (
    assign_test_case_ids,
    order_cognos_test_cases,
    _CATEGORY_ID_MAP,
    _CATEGORY_BASE_ORDER,
)
from app.domain.cognos_models import (
    ReportDefinition,
    ReportMetadata,
    SelectionCriterion,
    ReportField,
)
from app.domain.cognos_requirement import (
    RequirementSet,
    CognosRequirement,
    RequirementCategory,
)
from app.cognos.rules.scenario_expander import ScenarioExpander
from app.cognos.rules.sql_generator import DeterministicSqlGenerator


SAMPLE_DOCX = Path("runs/94/source/source.docx")


def test_selection_criteria_applicability_populated():
    """SELECTION_CRITERIA_VALIDATION should be generated when selection criteria exist."""
    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="PRV-INT-027"),
        selection_criteria=[
            SelectionCriterion(field="OPLC Term Date", filter_logic="OPLC Term Date >= current date"),
            SelectionCriterion(field="MMIS Lic Cert End Date", filter_logic="MMIS Lic Cert End Date <= 31/12/9999"),
        ]
    )
    req_set = RequirementSet(
        requirements=[
            CognosRequirement(
                requirement_id="REQ-SEL-01",
                category=RequirementCategory.SELECTION_CRITERIA,
                field="OPLC Term Date",
                requirement_text="Selection criterion: OPLC Term Date >= current date"
            ),
            CognosRequirement(
                requirement_id="REQ-SEL-02",
                category=RequirementCategory.SELECTION_CRITERIA,
                field="MMIS Lic Cert End Date",
                requirement_text="Selection criterion: MMIS Lic Cert End Date <= 31/12/9999"
            ),
        ]
    )
    report = discover_applicable_patterns(req_set.requirements, rd)
    pattern_names = [p.pattern for p in report.generated]
    assert MethodologyPattern.SELECTION_CRITERIA_VALIDATION in pattern_names


def test_selection_criteria_applicability_empty():
    """SELECTION_CRITERIA_VALIDATION should NOT be generated when selection criteria section is empty."""
    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="RPT-EMPTY-001"),
        selection_criteria=[]
    )
    req_set = RequirementSet(requirements=[])
    report = discover_applicable_patterns(req_set.requirements, rd)
    pattern_names = [p.pattern for p in report.generated]
    assert MethodologyPattern.SELECTION_CRITERIA_VALIDATION not in pattern_names

    not_gen = {p.pattern: p.reason for p in report.not_generated}
    assert MethodologyPattern.SELECTION_CRITERIA_VALIDATION in not_gen


def test_selection_criteria_scenario_expansion_and_sql():
    """Verify detailed expansion, source mapping, and deterministic SQL for selection criteria."""
    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="PRV-INT-027", report_title="Provider License Interface"),
        selection_criteria=[
            SelectionCriterion(field="OPLC Term Date", filter_logic="OPLC Term Date >= current date", prompt=False),
            SelectionCriterion(field="MMIS Lic Cert End Date", filter_logic="MMIS Lic Cert End Date <= 31/12/9999", prompt=False),
        ],
        report_fields=[
            ReportField(field_name="Prov ID", source_column="P_CURR_ALT_ID", source_table="P_RPT_CLDI_TERM_TB"),
            ReportField(field_name="OPLC Term Date", source_column="P_CMN_LIC_CERT_END_DT", source_table="P_RPT_CLDI_TERM_TB"),
            ReportField(field_name="MMIS Lic Cert End Date", source_column="P_LIC_CERT_END_DT", source_table="P_RPT_CLDI_TERM_TB"),
        ]
    )
    reqs = [
        CognosRequirement(
            requirement_id="REQ-SEL-01",
            category=RequirementCategory.SELECTION_CRITERIA,
            field="OPLC Term Date",
            requirement_text="Selection criterion: OPLC Term Date >= current date"
        ),
        CognosRequirement(
            requirement_id="REQ-SEL-02",
            category=RequirementCategory.SELECTION_CRITERIA,
            field="MMIS Lic Cert End Date",
            requirement_text="Selection criterion: MMIS Lic Cert End Date <= 31/12/9999"
        ),
    ]
    req_set = RequirementSet(requirements=reqs)

    report = discover_applicable_patterns(reqs, rd)
    sel_pattern = next(p for p in report.generated if p.pattern == MethodologyPattern.SELECTION_CRITERIA_VALIDATION)

    expander = ScenarioExpander(rd, req_set)
    tcs = expander.expand([sel_pattern])
    assert len(tcs) == 1
    tc = tcs[0]

    assert tc.category == "Selection Criteria Validation"
    assert "Verify report selection criteria for PRV-INT-027" in tc.test_case_title
    assert "OPLC Term Date >= current date" in tc.test_steps
    assert "MMIS Lic Cert End Date <= 31/12/9999" in tc.test_steps
    assert "OPLC Term Date >= current date" in tc.expected_result
    assert "MMIS Lic Cert End Date <= 31/12/9999" in tc.expected_result

    # Check source mappings
    mapped_fields = {m["field"]: m["column"] for m in tc.source_mappings}
    assert mapped_fields.get("OPLC Term Date") == "P_CMN_LIC_CERT_END_DT"
    assert mapped_fields.get("MMIS Lic Cert End Date") == "P_LIC_CERT_END_DT"

    # Check SQL
    assert tc.sql_status == "AVAILABLE"
    assert "P_CMN_LIC_CERT_END_DT >= CURRENT_DATE" in tc.validation_sql
    assert "P_LIC_CERT_END_DT <= DATE('9999-12-31')" in tc.validation_sql
    assert "FROM P_RPT_CLDI_TERM_TB" in tc.validation_sql


@pytest.mark.skipif(not SAMPLE_DOCX.exists(), reason="Sample DOCX not present")
def test_full_pipeline_prv027_authoritative_order_and_selc():
    """Verify complete end-to-end pipeline produces exactly 25 scenarios with SELC at position 04."""
    ctx = run_cognos_pipeline(SAMPLE_DOCX)
    ts = ctx.test_suite

    assert len(ts.test_cases) == 25, f"Expected 25 test cases, got {len(ts.test_cases)}"

    # Authoritative Expected Scenarios Order:
    expected_order = [
        ("PRV027-REPO-01", "Report Name Description Validation", 10),
        ("PRV027-RHDR-01", "Report Header Validation", 20),
        ("PRV027-SECT-01", "Report Section Heading Validation", 30),
        ("PRV027-SELC-01", "Selection Criteria Validation", 40),
        ("PRV027-LABE-01", "Label Validation", 50),
        ("PRV027-LAYO-01", "Layout Validation", 60),
        ("PRV027-LOOK-01", "Lookup Validation", 70),
        ("PRV027-OUTP-01", "Output Delivery Validation", 80),
        ("PRV027-OUTP-02", "Output Delivery Validation", 90),
        ("PRV027-SCRI-01", "Script Output Validation", 100),
        ("PRV027-SCRI-02", "Script Output Validation", 110),
        ("PRV027-SCHE-01", "Scheduled Execution Validation", 120),
        ("PRV027-SORT-01", "Sort Validation", 130),
        ("PRV027-SORT-02", "Sort Validation", 140),
        ("PRV027-SPEC-01", "Special Processing Validation", 150),
        ("PRV027-DATE-01", "Date Format Validation", 160),
        ("PRV027-DATE-02", "Date Format Validation", 170),
        ("PRV027-DBRE-01", "DB Report Data Validation", 180),
        ("PRV027-DBRE-02", "DB Report Data Validation", 190),
        ("PRV027-DBRE-03", "DB Report Data Validation", 200),
        ("PRV027-DBRE-04", "DB Report Data Validation", 210),
        ("PRV027-DBRE-05", "DB Report Data Validation", 220),
        ("PRV027-DBRE-06", "DB Report Data Validation", 230),
        ("PRV027-DBCO-01", "DB Count Validation", 240),
        ("PRV027-DUPL-01", "Duplicate Validation", 250),
    ]

    for idx, (exp_id, exp_cat, exp_order) in enumerate(expected_order):
        actual_tc = ts.test_cases[idx]
        assert actual_tc.test_case_id == exp_id, f"Index {idx}: expected {exp_id}, got {actual_tc.test_case_id}"
        assert actual_tc.category == exp_cat, f"Index {idx}: expected category {exp_cat}, got {actual_tc.category}"
        assert actual_tc.scenario_order == exp_order, f"Index {idx}: expected order {exp_order}, got {actual_tc.scenario_order}"

    # Verify SELC-01 specific contents
    selc = ts.test_cases[3]
    assert selc.test_case_id == "PRV027-SELC-01"
    assert selc.category == "Selection Criteria Validation"
    assert "OPLC Term Date >= current date" in selc.selection_criteria
    assert "MMIS Lic Cert End Date <= 31/12/9999" in selc.selection_criteria
    assert "P_CMN_LIC_CERT_END_DT >= CURRENT_DATE" in selc.validation_sql
    assert "P_LIC_CERT_END_DT <= DATE('9999-12-31')" in selc.validation_sql

    # Verify Evidence References
    ev_types = [e.evidence_type for e in selc.evidence_references]
    assert "DSD_SEMANTIC_PROOF" in ev_types
    assert "SOURCE_DSD_SNAPSHOT" in ev_types
    snap_ev = next(e for e in selc.evidence_references if e.evidence_type == "SOURCE_DSD_SNAPSHOT")
    assert snap_ev.section == "Report Selection Criteria"
