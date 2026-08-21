import pytest
from app.domain.cognos_requirement import CognosRequirement, RequirementCategory
from app.domain.cognos_test_case import CognosTestCase
from app.domain.cognos_models import SourceLogicType
from app.cognos.extraction.spec_table_extractor import is_structural_label
from app.cognos.validation.coverage_analyzer import compute_coverage
from app.domain.cognos_requirement import RequirementSet
from app.domain.cognos_models import ReportDefinition, ReportMetadata

def test_structural_label_filtering():
    assert is_structural_label("Presentation Type:") == True
    assert is_structural_label("Report Body") == True
    assert is_structural_label("Chart Footer (opt)") == True
    assert is_structural_label("Unknown") == True
    assert is_structural_label("Review Required") == True
    assert is_structural_label("Valid Field Name") == False

def test_coverage_calculation():
    req1 = CognosRequirement(requirement_id="REQ-01", category=RequirementCategory.COLUMN)
    req2 = CognosRequirement(requirement_id="REQ-02", category=RequirementCategory.COLUMN)
    
    req_set = RequirementSet(report_id="RPT1", requirements=[req1, req2])
    
    # Test case with missing ID mapping
    tc = CognosTestCase(
        test_case_id="TC-01",
        requirement_ids=["REQ-03"],  # Invalid link
        category="Column"
    )
    
    report_def = ReportDefinition(metadata=ReportMetadata(report_id="RPT1"))
    coverage = compute_coverage(req_set, [tc], report_def)
    
    assert coverage.total_requirements == 2
    assert coverage.requirements_covered == 0
    assert coverage.overall_coverage_percentage == 0.0

def test_coverage_calculation_empty_ids():
    req1 = CognosRequirement(requirement_id="", category=RequirementCategory.COLUMN)
    req_set = RequirementSet(report_id="RPT1", requirements=[req1])
    tc = CognosTestCase(
        test_case_id="TC-01",
        requirement_ids=[],
        category="Column"
    )
    report_def = ReportDefinition(metadata=ReportMetadata(report_id="RPT1"))
    coverage = compute_coverage(req_set, [tc], report_def)
    
    assert coverage.total_requirements == 0
    assert coverage.requirements_covered == 0
    assert coverage.overall_coverage_percentage == 0.0
