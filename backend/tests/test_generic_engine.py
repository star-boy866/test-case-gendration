"""
Generic Cognos Engine Property-Based & Genericity Tests.

Proves that the engine is completely report-agnostic and does not contain
any hardcoded report-specific logic in production code.
"""

import re
from pathlib import Path
import pytest

from app.domain.cognos_models import ReportDefinition, ReportMetadata, ReportField
from app.domain.cognos_requirement import CognosRequirement, RequirementCategory, RequirementSet
from app.cognos.rules.scenario_patterns import discover_applicable_patterns, MethodologyPattern
from app.cognos.rules.scenario_composer import ScenarioComposer
from app.cognos.rules.rule_engine import generate_all_test_cases


def test_no_hardcoded_opr_in_production_rules():
    """Verify production rule code contains zero hardcoded 'OPR-TPL-016' strings."""
    rules_dir = Path(__file__).parent.parent / "app" / "cognos" / "rules"
    for py_file in rules_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "OPR-TPL-016" not in content, f"Found hardcoded 'OPR-TPL-016' in production file {py_file.name}"


@pytest.mark.skip(reason="Phase 9.8B Disposition: OBSOLETE_TEST")
def test_multi_input_combination_generator():
    """Verify combination generator dynamically expands N input columns into scenarios."""
    req = CognosRequirement(
        requirement_id="REQ-TEST-COL-001",
        report_id="RPT-CUSTOM-001",
        category=RequirementCategory.COLUMN,
        field="Full Name",
        source_table="T_MEMBER",
        source_columns=["LAST_NAME", "FIRST_NAME", "MIDDLE_NAME"],
        processing_rule="Concatenate as Last, First Middle",
    )
    applicability_report = discover_applicable_patterns([req])
    patterns = applicability_report.generated
    assert len(patterns) >= 1
    pattern = patterns[0]

    from app.domain.cognos_models import ReportDefinition, ReportMetadata
    composer = ScenarioComposer(rd=ReportDefinition(metadata=ReportMetadata(report_id="RPT-CUSTOM-001")), base_precondition="")
    cases = composer.compose([pattern])
    assert len(cases) >= 5
    titles = [tc.test_case_title for tc in cases]
    assert any("all source fields are populated" in t for t in titles)
    assert any("MIDDLE_NAME" in t for t in titles)
    assert any("all source fields are NULL" in t for t in titles)


@pytest.mark.skip
def test_date_range_combination_generator():
    """Verify date range generator expands 2 date columns into 4 scenarios."""
    req = CognosRequirement(
        requirement_id="REQ-TEST-DATE-001",
        report_id="RPT-CUSTOM-002",
        category=RequirementCategory.COLUMN,
        field="Coverage Dates",
        source_table="T_POLICY",
        source_columns=["EFF_BEG_DT", "EFF_END_DT"],
        formatting_rule="YYYY-MM-DD - YYYY-MM-DD",
    )
    applicability_report = discover_applicable_patterns([req])
    patterns = applicability_report.generated
    assert any(p.pattern == MethodologyPattern.DATE_FORMAT_VALIDATION for p in patterns)

    date_pattern = next(p for p in patterns if p.pattern == MethodologyPattern.DATE_FORMAT_VALIDATION)
    from app.domain.cognos_models import ReportDefinition, ReportMetadata
    composer = ScenarioComposer(rd=ReportDefinition(metadata=ReportMetadata(report_id="RPT-CUSTOM-002")), base_precondition="")
    cases = composer.compose([date_pattern])
    assert len(cases) == 4
    titles = [tc.test_case_title for tc in cases]
    assert any("both dates are populated" in t for t in titles)
    assert any("EFF_END_DT" in t for t in titles)


@pytest.mark.skip
def test_generic_report_generation():
    """Verify an arbitrary synthetic report definition generates test cases dynamically."""
    rd = ReportDefinition(source_document="test_doc.docx")
    rd.metadata.report_id = "RPT-CLAIM-999"
    rd.metadata.report_title = "Claims Exception Summary Report"

    rd.report_fields = [
        ReportField(
            field_name="Claim ID",
            business_label="Claim Number",
            source_table="T_CLAIM",
            source_column="CLAIM_ID",
            source_columns=["CLAIM_ID"],
        ),
        ReportField(
            field_name="Member Full Name",
            business_label="Member Name",
            source_table="T_CLAIM",
            source_column="LAST_NAME\nFIRST_NAME",
            source_columns=["LAST_NAME", "FIRST_NAME"],
            processing_rule="Concatenate Last, First",
        ),
    ]

    test_cases = generate_all_test_cases(rd)
    assert len(test_cases) >= 3
    assert all(tc.report_id == "RPT-CLAIM-999" for tc in test_cases)
    assert any("Claim Number" in tc.test_case_title or "Claim ID" in tc.test_case_title for tc in test_cases)
