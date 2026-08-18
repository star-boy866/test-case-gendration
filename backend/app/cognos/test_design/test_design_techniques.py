"""
Test Design Techniques for Comprehensive Test Mode.
Implements Equivalence Partitioning (EP), Boundary Value Analysis (BVA), and Negative Testing.
"""

from app.domain.cognos_test_case import CognosTestCase, TestType, TestCasePriority
from app.domain.cognos_requirement import CognosRequirement, TestOrigin

def generate_ep_tests(requirement: CognosRequirement) -> list[CognosTestCase]:
    """Generate Equivalence Partitioning tests."""
    tests = []
    # If there is a rule like 'In (A, B, C)', test one valid partition
    if " in (" in requirement.processing_rule.lower() or " = " in requirement.processing_rule.lower():
        tests.append(CognosTestCase(
            test_case_id=f"EP-VALID-{requirement.requirement_id}",
            report_id=requirement.report_id,
            test_case_title=f"EP Valid - {requirement.field}",
            category=requirement.category.value,
            requirement_ids=[requirement.requirement_id],
            objective=f"Verify {requirement.field} accepts valid partitions",
            source_section=requirement.source_section,
            test_steps=f"1. Generate report with valid {requirement.field} partition\n2. Verify output",
            expected_result=f"{requirement.field} displays correctly per rule: {requirement.processing_rule}",
            test_type=TestType.POSITIVE,
            origin=TestOrigin.DSD_DERIVED,
            priority=TestCasePriority.HIGH
        ))
    return tests

def generate_bva_tests(requirement: CognosRequirement) -> list[CognosTestCase]:
    """Generate Boundary Value Analysis tests."""
    tests = []
    # Date boundaries
    if "date" in requirement.field.lower() or "date" in requirement.processing_rule.lower():
        tests.append(CognosTestCase(
            test_case_id=f"BVA-MIN-{requirement.requirement_id}",
            report_id=requirement.report_id,
            test_case_title=f"BVA Lower Bound - {requirement.field}",
            category=requirement.category.value,
            requirement_ids=[requirement.requirement_id],
            objective=f"Verify {requirement.field} at minimum boundary (e.g. first day of month)",
            source_section=requirement.source_section,
            test_steps=f"1. Set {requirement.field} to lowest boundary value\n2. Run report",
            expected_result=f"Report includes boundary record for {requirement.field}",
            test_type=TestType.BOUNDARY,
            origin=TestOrigin.DSD_DERIVED,
            priority=TestCasePriority.MEDIUM
        ))
        tests.append(CognosTestCase(
            test_case_id=f"BVA-MAX-{requirement.requirement_id}",
            report_id=requirement.report_id,
            test_case_title=f"BVA Upper Bound - {requirement.field}",
            category=requirement.category.value,
            requirement_ids=[requirement.requirement_id],
            objective=f"Verify {requirement.field} at maximum boundary (e.g. last day of month)",
            source_section=requirement.source_section,
            test_steps=f"1. Set {requirement.field} to highest boundary value\n2. Run report",
            expected_result=f"Report includes boundary record for {requirement.field}",
            test_type=TestType.BOUNDARY,
            origin=TestOrigin.DSD_DERIVED,
            priority=TestCasePriority.MEDIUM
        ))
    return tests

def generate_negative_tests(requirement: CognosRequirement) -> list[CognosTestCase]:
    """Generate Negative tests (invalid data, nulls, out of bounds)."""
    tests = []
    if requirement.field:
        tests.append(CognosTestCase(
            test_case_id=f"NEG-NULL-{requirement.requirement_id}",
            report_id=requirement.report_id,
            test_case_title=f"Negative - Null {requirement.field}",
            category=requirement.category.value,
            requirement_ids=[requirement.requirement_id],
            objective=f"Verify handling of NULL {requirement.field}",
            source_section=requirement.source_section,
            test_steps=f"1. Seed database with NULL {requirement.field}\n2. Run report",
            expected_result=f"Report displays blank or default value for {requirement.field} without crashing",
            test_type=TestType.NEGATIVE,
            origin=TestOrigin.DSD_DERIVED,
            priority=TestCasePriority.HIGH
        ))
    return tests
