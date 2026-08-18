"""
Coverage analyzer — computes requirement-to-test-case coverage statistics.

Provides category-level coverage, traceability matrix entries, and
specification quality analysis.
"""

from __future__ import annotations

from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import RequirementSet, RequirementCategory
from app.domain.cognos_test_case import (
    CognosTestCase,
    CoverageReport,
    CategoryCoverage,
    TraceabilityEntry,
    SpecificationQualityReport,
)


def compute_coverage(
    req_set: RequirementSet,
    test_cases: list[CognosTestCase],
    report_def: ReportDefinition,
) -> CoverageReport:
    """
    Compute requirement-to-test-case coverage.

    Returns a CoverageReport with overall and category-level statistics.
    """
    # Build requirement ID -> test case mapping (many-to-many support)
    req_to_tests: dict[str, list[str]] = {}
    for tc in test_cases:
        req_list = tc.requirement_ids if tc.requirement_ids else ([tc.requirement_id] if tc.requirement_id else [])
        for req_id in req_list:
            if req_id and tc.test_case_id not in req_to_tests.setdefault(req_id, []):
                req_to_tests[req_id].append(tc.test_case_id)

    # Non-duplicate requirements only
    active_reqs = [r for r in req_set.requirements if not r.is_duplicate_of]

    covered = sum(1 for r in active_reqs if r.requirement_id in req_to_tests)
    unmapped = sum(1 for r in active_reqs if r.requirement_id not in req_to_tests)
    ambiguous = sum(1 for r in active_reqs if r.is_ambiguous)
    duplicate = sum(1 for r in req_set.requirements if r.is_duplicate_of)

    total = len(active_reqs)
    pct = (covered / total * 100) if total > 0 else 0.0

    # Category-level coverage
    category_coverage = _compute_category_coverage(active_reqs, req_to_tests, test_cases)

    # Open questions from all requirements
    open_questions = []
    for r in req_set.requirements:
        open_questions.extend(r.open_questions)
    open_questions.extend(report_def.open_questions)

    return CoverageReport(
        report_id=req_set.report_id,
        total_requirements=total,
        requirements_covered=covered,
        requirements_unmapped=unmapped,
        requirements_ambiguous=ambiguous,
        requirements_duplicate=duplicate,
        overall_coverage_percentage=round(pct, 2),
        category_coverage=category_coverage,
        open_questions=open_questions,
    )


def _compute_category_coverage(
    active_reqs: list,
    req_to_tests: dict[str, list[str]],
    test_cases: list[CognosTestCase],
) -> list[CategoryCoverage]:
    """Compute per-category coverage."""
    categories: dict[str, dict] = {}

    for req in active_reqs:
        cat = req.category.value if hasattr(req.category, 'value') else str(req.category)
        if cat not in categories:
            categories[cat] = {
                "found": 0, "covered": 0, "unmapped": 0, "ambiguous": 0
            }
        categories[cat]["found"] += 1
        if req.requirement_id in req_to_tests:
            categories[cat]["covered"] += 1
        else:
            categories[cat]["unmapped"] += 1
        if req.is_ambiguous:
            categories[cat]["ambiguous"] += 1

    # Count test cases per category
    tc_by_cat: dict[str, int] = {}
    for tc in test_cases:
        tc_by_cat[tc.category] = tc_by_cat.get(tc.category, 0) + 1

    result = []
    for cat, stats in sorted(categories.items()):
        total = stats["found"]
        covered = stats["covered"]
        pct = (covered / total * 100) if total > 0 else 0.0
        result.append(CategoryCoverage(
            category=cat,
            requirements_found=total,
            requirements_covered=covered,
            requirements_unmapped=stats["unmapped"],
            requirements_ambiguous=stats["ambiguous"],
            test_cases_generated=tc_by_cat.get(cat, 0),
            coverage_percentage=round(pct, 2),
        ))

    return result


def build_traceability_matrix(
    req_set: RequirementSet,
    test_cases: list[CognosTestCase],
) -> list[TraceabilityEntry]:
    """Build the requirement → test case traceability matrix."""
    req_to_tests: dict[str, list[str]] = {}
    for tc in test_cases:
        req_list = tc.requirement_ids if tc.requirement_ids else ([tc.requirement_id] if tc.requirement_id else [])
        for req_id in req_list:
            if req_id and tc.test_case_id not in req_to_tests.setdefault(req_id, []):
                req_to_tests[req_id].append(tc.test_case_id)

    matrix = []
    for req in req_set.requirements:
        if req.is_duplicate_of:
            continue  # Skip duplicates in the matrix

        test_ids = req_to_tests.get(req.requirement_id, [])
        if test_ids:
            status = "Covered"
        elif req.is_ambiguous:
            status = "Ambiguous"
        else:
            status = "Uncovered"

        matrix.append(TraceabilityEntry(
            requirement_id=req.requirement_id,
            requirement_text=req.requirement_text[:200],
            category=req.category.value,
            source_page=req.source_page,
            test_case_ids=test_ids,
            coverage_status=status,
        ))

    return matrix


def build_quality_report(
    report_def: ReportDefinition,
    req_set: RequirementSet,
) -> SpecificationQualityReport:
    """Build the specification quality analysis."""
    active_reqs = [r for r in req_set.requirements if not r.is_duplicate_of]

    missing_info: list[str] = []
    if not report_def.metadata.report_id:
        missing_info.append("Report ID not found in the document.")
    if not report_def.metadata.report_title:
        missing_info.append("Report Title not found in the document.")
    if not report_def.metadata.report_description:
        missing_info.append("Report Description not found in the document.")
    if not report_def.report_fields:
        missing_info.append("No report fields/columns found in the specification.")
    if not report_def.sort_definitions:
        missing_info.append("No sort definitions found in the document.")

    # Add missing info from parse warnings
    missing_info.extend(report_def.parse_warnings)

    # Collect open questions
    open_questions = list(report_def.open_questions)
    for req in req_set.requirements:
        open_questions.extend(req.open_questions)

    return SpecificationQualityReport(
        report_id=report_def.metadata.report_id,
        report_title=report_def.metadata.report_title,
        requirements_found=len(active_reqs),
        testable_requirements=sum(1 for r in active_reqs if r.is_complete),
        ambiguous_requirements=sum(1 for r in active_reqs if r.is_ambiguous),
        missing_information=missing_info,
        conflicts=report_def.conflicts,
        open_questions=open_questions,
    )
