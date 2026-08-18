"""
Validation tests for Phase 8: Comprehensive Test Engine.
Validates the new engine Mode B capabilities.
"""

import pytest
from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import RequirementSet, CognosRequirement, RequirementCategory, TestOrigin
from app.domain.cognos_test_case import TestSuite, TestType
from app.cognos.test_design.comprehensive_test_design_engine import run_comprehensive_engine

@pytest.fixture
def sample_requirement():
    return CognosRequirement(
        requirement_id="REQ-01",
        report_id="RPT-01",
        field="Birth Date",
        category=RequirementCategory.COLUMN,
        requirement_text="Must be a valid date",
        processing_rule="date format",
        source_section="1.1"
    )

@pytest.fixture
def mock_comments():
    return [
        {"author": "Reviewer 1", "text": "This field contains PII, please ensure it is masked."},
        {"author": "Reviewer 2", "text": "The rule here contradicts section 3.2."}
    ]

def test_ep_and_bva_generation(sample_requirement):
    """Test 1: Generates BVA for dates."""
    req_set = RequirementSet(requirements=[sample_requirement])
    base_suite = TestSuite(report_id="RPT-01")
    
    comp_suite = run_comprehensive_engine(ReportDefinition(), req_set, [], base_suite)
    
    # Expect 2 BVA tests for dates
    bva_tests = [t for t in comp_suite.comprehensive_tests if t.test_type == TestType.BOUNDARY]
    assert len(bva_tests) == 2
    assert "Lower Bound" in bva_tests[0].test_case_title
    assert "Upper Bound" in bva_tests[1].test_case_title

def test_negative_testing(sample_requirement):
    """Test 2: Generates negative tests for fields."""
    req_set = RequirementSet(requirements=[sample_requirement])
    base_suite = TestSuite(report_id="RPT-01")
    
    comp_suite = run_comprehensive_engine(ReportDefinition(), req_set, [], base_suite)
    
    neg_tests = [t for t in comp_suite.comprehensive_tests if t.test_type == TestType.NEGATIVE]
    assert len(neg_tests) == 1
    assert "Null" in neg_tests[0].test_case_title

def test_risk_derivation(sample_requirement, mock_comments):
    """Test 3: Derives risks correctly."""
    req_set = RequirementSet(requirements=[sample_requirement])
    base_suite = TestSuite(report_id="RPT-01")
    
    # Inject PII text
    req_set.requirements[0].requirement_text += " (PII)"
    
    comp_suite = run_comprehensive_engine(ReportDefinition(), req_set, mock_comments, base_suite)
    
    assert len(comp_suite.risks) == 1
    assert "PII" in comp_suite.risks[0].description
    
    sec_tests = [t for t in comp_suite.comprehensive_tests if t.test_type == TestType.SECURITY]
    assert len(sec_tests) == 1
    assert sec_tests[0].origin == TestOrigin.RISK_DERIVED

def test_comment_extraction(sample_requirement, mock_comments):
    """Test 4: Maps comments to validatable test cases."""
    req_set = RequirementSet(requirements=[sample_requirement])
    base_suite = TestSuite(report_id="RPT-01")
    
    comp_suite = run_comprehensive_engine(ReportDefinition(), req_set, mock_comments, base_suite)
    
    com_tests = [t for t in comp_suite.comprehensive_tests if t.origin == TestOrigin.COMMENT_DERIVED]
    assert len(com_tests) == 2
    
    assert "Review Comment - RISK" in com_tests[0].test_case_title
    assert "Review Comment - CONTRADICTION" in com_tests[1].test_case_title

def test_methodology_attached():
    """Test 5: Validates methodology is attached to output."""
    comp_suite = run_comprehensive_engine(ReportDefinition(), RequirementSet(), [], TestSuite())
    assert comp_suite.methodology is not None
    assert "Equivalence Partitioning (EP)" in comp_suite.methodology.techniques_used
