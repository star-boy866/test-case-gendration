"""
Comprehensive Test Design Engine for Cognos.
Entry point for "Mode B" — Comprehensive Test Design.
"""

from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import RequirementSet
from app.domain.cognos_test_case import TestSuite
from app.domain.cognos_comprehensive_models import Risk, Assumption, Methodology

from app.cognos.test_design.requirement_analyzer import analyze_comments
from app.cognos.test_design.scenario_builder import build_comprehensive_scenarios
from app.cognos.test_design.risk_analyzer import derive_risks, generate_risk_tests
from app.cognos.test_design.assumption_analyzer import derive_assumptions, generate_assumption_tests

from pydantic import BaseModel, Field

class ComprehensiveTestSuite(BaseModel):
    """Extended TestSuite for Comprehensive Mode."""
    base_suite: TestSuite
    comprehensive_tests: list = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    methodology: Methodology = Field(default_factory=Methodology)


def run_comprehensive_engine(
    report_def: ReportDefinition,
    req_set: RequirementSet,
    parsed_comments: list[dict],
    base_suite: TestSuite
) -> ComprehensiveTestSuite:
    """Run the comprehensive engine to augment the base test suite."""
    
    # 1. Base requirements and techniques
    comprehensive_tests = build_comprehensive_scenarios(req_set)
    
    # 2. Risk analysis
    risks = derive_risks(req_set.requirements)
    for risk in risks:
        comprehensive_tests.extend(generate_risk_tests(risk))
        
    # 3. Assumption analysis
    assumptions = derive_assumptions(req_set.requirements)
    for assumption in assumptions:
        comprehensive_tests.extend(generate_assumption_tests(assumption))
        
    # 4. Comment analysis
    comment_tests = analyze_comments(parsed_comments, req_set.requirements)
    comprehensive_tests.extend(comment_tests)
    
    # Methodology documentation
    methodology = Methodology(
        description="Comprehensive Test Design Methodology generated dynamically from explicit requirements and implied metadata.",
        techniques_used=[
            "Equivalence Partitioning (EP)",
            "Boundary Value Analysis (BVA)",
            "Negative Testing",
            "Risk-based Testing",
            "Assumption & Dependency Validation"
        ],
        rules_applied=[
            "Data boundaries identified and tested",
            "PII/PHI risks evaluated for security controls",
            "Referential integrity assumed for lookup rules",
            "Reviewer comments integrated into validatable items"
        ]
    )
    
    # Ensure IDs are distinct and ordered
    for idx, tc in enumerate(comprehensive_tests, start=1):
        # Override the base ID if it wasn't set or just append suffix
        if not tc.test_case_id.startswith("COM-"):
            tc.test_case_id = f"COMP-{idx:03d}"
        tc.report_id = base_suite.report_id
    
    return ComprehensiveTestSuite(
        base_suite=base_suite,
        comprehensive_tests=comprehensive_tests,
        risks=risks,
        assumptions=assumptions,
        methodology=methodology
    )
