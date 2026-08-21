"""
Cognos Test Case Rule Engine — PHASE 10.6 REWRITE.

Generates granular, developer-quality Cognos UT scenarios by:
1. Discovering applicable methodology patterns from DSD semantics.
2. Running the Phase 10.6 ScenarioExpander to produce N detailed scenarios
   per methodology family (not 1 test per pattern).

Zero hardcoded report IDs, field names, or table names.
Works for any Cognos report whose DSD is properly extracted.
"""

from __future__ import annotations

from typing import Optional

from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import CognosRequirement, RequirementCategory, RequirementSet
from app.domain.cognos_test_case import CognosTestCase, TestCasePriority
from app.cognos.rules.scenario_patterns import discover_applicable_patterns
from app.cognos.rules.scenario_expander import ScenarioExpander


def generate_all_test_cases(
    rd: ReportDefinition,
    req_set: Optional[RequirementSet] = None,
) -> list[CognosTestCase]:
    """
    Generate the complete test suite from a RequirementSet and ReportDefinition
    using the Phase 10.6 Scenario Expansion Engine.

    The 14 methodology patterns are treated as FAMILIES. Each family expands
    into N granular, developer-quality test scenarios based on the DSD semantics.
    """
    cases: list[CognosTestCase] = []
    rid = rd.metadata.report_id or "COGNOS-RPT"
    rname = rd.metadata.report_title or "Cognos Report"

    # Requirements to process (exclude duplicates)
    requirements: list[CognosRequirement] = []
    if req_set and req_set.requirements:
        requirements = [r for r in req_set.requirements if not r.is_duplicate_of]

    if not requirements:
        cases.append(_build_metadata_header_case(rd))
        return cases

    # Discover which methodology families apply
    applicability_report = discover_applicable_patterns(requirements, rd)

    print(f"{type(applicability_report).__name__}")
    print(f"Applicable patterns: {len(applicability_report.generated)}")
    for pattern in applicability_report.generated:
        print(f"Pattern name: {pattern.pattern.value}")
        print(f"Reason: {pattern.applicable_reason}")
        print(f"Confidence: {pattern.confidence.value}")

    # Expand each pattern into granular scenarios using Phase 10.6 engine
    expander = ScenarioExpander(rd, req_set or RequirementSet())
    cases.extend(expander.expand(applicability_report.generated))

    return cases


def _get_primary_source_table(rd: ReportDefinition) -> str:
    """Find the most frequently referenced source table."""
    tables: dict[str, int] = {}
    for f in rd.report_fields:
        if f.source_table:
            tables[f.source_table] = tables.get(f.source_table, 0) + 1
    if tables:
        return max(tables, key=lambda k: tables[k])
    return "NOT_DEFINED"


def _build_metadata_header_case(rd: ReportDefinition, req_ids: list[str] | None = None) -> CognosTestCase:
    """Guarantee a report metadata/header validation test case exists when no requirements found."""
    rid = rd.metadata.report_id or "NOT_DEFINED"
    rname = rd.metadata.report_title or "NOT_DEFINED"
    desc = rd.metadata.report_description or "NOT_DEFINED"

    return CognosTestCase(
        category="Header",
        report_id=rid,
        report_name=rname,
        test_case_title=f"Verify report header metadata ({rid})",
        test_case_description=f"Verify header displays correct Report Title ('{rname}'), Report ID ('{rid}'), and metadata.",
        objective=f"Validate that report header displays exact metadata values.",
        requirement_ids=req_ids or [],
        source_document=rd.source_document,
        source_section="Report Definition",
        preconditions=f"Cognos Report '{rid}' ({rname}) is published and accessible.",
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
