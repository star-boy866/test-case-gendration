"""
Scenario Builder for Comprehensive Test Mode.
Orchestrates the application of test design techniques to requirements.
"""

from app.domain.cognos_requirement import RequirementSet
from app.domain.cognos_test_case import CognosTestCase
from app.cognos.test_design.test_design_techniques import generate_ep_tests, generate_bva_tests, generate_negative_tests

def build_comprehensive_scenarios(req_set: RequirementSet) -> list[CognosTestCase]:
    """Apply all test design techniques to all requirements."""
    comprehensive_tests = []
    for req in req_set.requirements:
        if req.is_duplicate_of:
            continue
            
        comprehensive_tests.extend(generate_ep_tests(req))
        comprehensive_tests.extend(generate_bva_tests(req))
        comprehensive_tests.extend(generate_negative_tests(req))
        
    return comprehensive_tests
