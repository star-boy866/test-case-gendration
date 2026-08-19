"""
Cognos Test Case Rule Engine — REPORT-AGNOSTIC REWRITE.

Generates detailed, executable, traceable manual Cognos Unit Test cases
by discovering scenario patterns from extracted requirements and report
field evidence.

Zero hardcoded report IDs, zero hardcoded field names, zero hardcoded tables.
Works for any of ~500 Cognos reports.
"""

from __future__ import annotations

from typing import Optional

from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import CognosRequirement, RequirementCategory, RequirementSet
from app.domain.cognos_test_case import CognosTestCase, TestCasePriority
from app.cognos.rules.scenario_patterns import discover_applicable_patterns
from app.cognos.rules.scenario_composer import ScenarioComposer


def generate_all_test_cases(
    rd: ReportDefinition,
    req_set: Optional[RequirementSet] = None,
) -> list[CognosTestCase]:
    """
    Generate the complete test suite from a RequirementSet and ReportDefinition
    using the Scenario Composer based on methodology patterns.
    """
    cases: list[CognosTestCase] = []
    rid = rd.metadata.report_id or "COGNOS-RPT"
    rname = rd.metadata.report_title or "Cognos Report"
    doc_name = rd.source_document or ""

    # Primary source table
    primary_table = _get_primary_source_table(rd)

    # Base precondition
    base_precondition = (
        f"Cognos Report '{rid}' ({rname}) is published and accessible. "
        f"Test data exists in source table '{primary_table}'."
    )

    # Requirements to process
    requirements: list[CognosRequirement] = []
    if req_set and req_set.requirements:
        requirements = [r for r in req_set.requirements if not r.is_duplicate_of]

    if not requirements:
        cases.append(_build_metadata_header_case(rd, base_precondition))
        return cases

    applicable_patterns = discover_applicable_patterns(requirements)
    composer = ScenarioComposer(rd, base_precondition)
    cases.extend(composer.compose(applicable_patterns))

    # Guarantee report metadata validation test
    if not any(c.category == "Header" or "metadata" in c.category.lower() or c.category == "Metadata" for c in cases):
        cases.append(_build_metadata_header_case(rd, base_precondition))

    return cases


def _get_primary_source_table(rd: ReportDefinition) -> str:
    """Find the most frequently referenced source table."""
    tables: dict[str, int] = {}
    for f in rd.report_fields:
        if f.source_table:
            tables[f.source_table] = tables.get(f.source_table, 0) + 1
    if tables:
        return max(tables, key=tables.get)
    return "REVIEW_REQUIRED"



def _build_metadata_header_case(rd: ReportDefinition, precondition: str) -> CognosTestCase:
    """Guarantee a report metadata/header validation test case exists."""
    rid = rd.metadata.report_id or "COGNOS-RPT"
    rname = rd.metadata.report_title or "Cognos Report"
    desc = rd.metadata.report_description or "Report Description"

    return CognosTestCase(
        category="Header",
        report_id=rid,
        report_name=rname,
        test_case_title=f"Verify report header metadata ({rid})",
        test_case_description=f"Verify header displays correct Report Title ('{rname}'), Report ID ('{rid}'), and metadata.",
        objective=f"Validate that report header displays exact metadata values.",
        requirement_ids=[f"REQ-{rid}-META-001"],
        source_document=rd.source_document,
        source_section="Report Definition",
        preconditions=precondition,
        test_data=f"Expected Header Values:\nReport ID: {rid}\nReport Title: {rname}\nDescription: {desc}",
        test_steps=(
            f"1. Run report {rid}.\n"
            f"2. Inspect top header area.\n"
            f"3. Verify Report ID is '{rid}'.\n"
            f"4. Verify Report Title is '{rname}'."
        ),
        expected_result=f"Header displays correct static values: ID='{rid}', Title='{rname}'. No truncation or missing text.",
        priority=TestCasePriority.HIGH,
        evidence_type="REPORT",
        evidence_required="- Generated report output showing header metadata: [REPORT EVIDENCE — INSERT SCREENSHOT]",
        origin="DIRECT_SPECIFICATION",
    )
