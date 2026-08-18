"""
Assumption Analyzer for Comprehensive Test Mode.
Derives implicit assumptions or dependencies from requirements.
"""

from app.domain.cognos_requirement import CognosRequirement
from app.domain.cognos_comprehensive_models import Assumption
from app.domain.cognos_test_case import CognosTestCase, TestType, TestCasePriority
from app.domain.cognos_requirement import TestOrigin

def derive_assumptions(requirements: list[CognosRequirement]) -> list[Assumption]:
    """Identify implicit assumptions from the specification."""
    assumptions = []
    has_join = False
    
    for req in requirements:
        if "join" in req.processing_rule.lower() or "lookup" in req.processing_rule.lower():
            has_join = True
            break
            
    if has_join:
        assumptions.append(Assumption(
            assumption_id="ASM-DEP-01",
            description="Report relies on joined tables or lookups. Assumes referential integrity exists in the data warehouse.",
            dependency="Data Warehouse / ETL",
        ))
        
    return assumptions

def generate_assumption_tests(assumption: Assumption) -> list[CognosTestCase]:
    """Generate tests to validate assumptions."""
    tests = []
    if "referential integrity" in assumption.description.lower():
        tests.append(CognosTestCase(
            test_case_id=f"TEST-{assumption.assumption_id}",
            report_id="UNKNOWN",
            test_case_title=f"Integration Validation - {assumption.assumption_id}",
            category="DATA_MAPPING",
            requirement_ids=[],
            objective="Verify behavior when referential integrity is broken (missing lookup).",
            source_section="Assumptions",
            test_steps="1. Create record with missing foreign key\n2. Run report",
            expected_result="Record is either excluded (Inner Join) or included with blanks (Outer Join) based on design.",
            test_type=TestType.INTEGRATION,
            origin=TestOrigin.ASSUMPTION_DERIVED,
            priority=TestCasePriority.MEDIUM
        ))
    return tests
