import pytest

from app.domain.cognos_models import ReportDefinition, ReportField, ReportMetadata, SortDefinition, SortDirection
from app.domain.cognos_requirement import CognosRequirement, RequirementCategory, RequirementSet
from app.domain.traceability_models import TraceabilityResult, SortTrace, MappingStatus, ReviewStatus
from app.domain.cognos_test_case import TestSuite
from app.cognos.rules.rule_engine import generate_all_test_cases
from app.domain.reporting_context import FinalReportContext
from app.cognos.validation.coverage_analyzer import compute_coverage

@pytest.fixture
def sample_dsd():
    return ReportDefinition(
        metadata=ReportMetadata(report_id="PRV-INT-027", report_title="Provider Report"),
        report_fields=[
            ReportField(field_name="Prov ID", business_label="Prov ID", source_columns=["P_CURR_ALT_ID"])
        ],
        sort_definitions=[
            SortDefinition(field="Prov Lic Cert Num", direction=SortDirection.ASCENDING),
            SortDefinition(field="Error Field", direction=SortDirection.ASCENDING),
        ]
    )

@pytest.fixture
def sample_reqs():
    return RequirementSet(
        report_id="PRV-INT-027",
        requirements=[
            CognosRequirement(
                requirement_id="REQ-1",
                category=RequirementCategory.COLUMN,
                field="Prov ID",
                requirement_text="Display Prov ID"
            ),
            CognosRequirement(
                requirement_id="REQ-2",
                category=RequirementCategory.SORT,
                field="Prov Lic Cert Num",
                requirement_text="Sort 1"
            ),
            CognosRequirement(
                requirement_id="REQ-3",
                category=RequirementCategory.SORT,
                field="Error Field",
                requirement_text="Sort 2"
            )
        ]
    )

@pytest.fixture
def sample_trace():
    return TraceabilityResult(
        sort_traces=[
            SortTrace(
                dsd_field_name="Error Field",
                dsd_direction="ASCENDING",
                mapping_status=MappingStatus.MISSING_IN_XML,
                review_status=ReviewStatus.REVIEW_REQUIRED
            )
        ]
    )

def test_rule_engine_independence(sample_dsd, sample_reqs, sample_trace):
    # 1. Generate without Traceability
    cases_pure_dsd = generate_all_test_cases(sample_dsd, sample_reqs)
    
    # 2. Assert Traceability does NOT modify generate_all_test_cases signature or functionality
    # Rule Engine is strictly blind to XML. We can't even pass trace_result to it.
    import inspect
    sig = inspect.signature(generate_all_test_cases)
    assert "trace_result" not in sig.parameters, "Rule Engine must NOT accept TraceabilityResult"
    
    # 3. Prove Error Field sort case is generated exactly as DSD requests
    error_field_cases = [c for c in cases_pure_dsd if c.source_field == "Error Field"]
    assert len(error_field_cases) == 1
    error_case = error_field_cases[0]
    
    # Prove XML discrepancy does NOT inject warnings into test steps or data
    assert "XML" not in error_case.test_steps
    assert "MISSING" not in error_case.test_steps
    assert "WARNING" not in error_case.test_steps
    assert "XML" not in error_case.test_data

def test_final_report_context_composition(sample_dsd, sample_reqs, sample_trace):
    # 1. Generate purely DSD-driven test suite
    cases = generate_all_test_cases(sample_dsd, sample_reqs)
    suite = TestSuite(report_id="PRV-INT-027", test_cases=cases)
    
    # Coverage is computed using ONLY DSD logic
    coverage = compute_coverage(sample_reqs, suite.test_cases)
    suite.coverage = coverage
    
    # 2. Compose the final reporting context
    context = FinalReportContext(
        report_definition=sample_dsd,
        requirement_set=sample_reqs,
        test_suite=suite,
        traceability_result=sample_trace
    )
    
    # 3. Prove XML missing status doesn't impact coverage
    assert context.test_suite.coverage.requirements_covered > 0
    # The Error Field case is considered covered by the UT because the UT was generated.
    # The TraceabilityResult holds the fact that it's MISSING_IN_XML separately.
    error_trace = next(s for s in context.traceability_result.sort_traces if s.dsd_field_name == "Error Field")
    assert error_trace.mapping_status == MappingStatus.MISSING_IN_XML
    
    # The test case model remains free of XML state
    error_test_case = next(c for c in context.test_suite.test_cases if c.source_field == "Error Field")
    assert not hasattr(error_test_case, "xml_mapping_status")
