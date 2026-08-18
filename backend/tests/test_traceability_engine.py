import pytest
from pathlib import Path

from app.domain.cognos_models import (
    ReportDefinition, ReportField, SortDefinition, SortDirection, 
    LayoutDefinition, PresentationType, SelectionCriterion
)
from app.domain.cognos_requirement import RequirementSet, CognosRequirement
from app.cognos.extraction.xml_parser import parse_cognos_xml
from app.cognos.validation.traceability_engine import TraceabilityEngine
from app.domain.traceability_models import MappingStatus, ReviewStatus, MatchStrategy

@pytest.fixture
def real_xml_model():
    xml_path = Path(__file__).parent / "fixtures" / "PRV-INT-027.xml"
    if not xml_path.exists():
        pytest.skip("Real PRV-INT-027.xml not found")
    return parse_cognos_xml(xml_path)

@pytest.fixture
def mock_dsd():
    dsd = ReportDefinition()
    
    # Add fields
    dsd.report_fields.extend([
        ReportField(field_name="Prov ID", business_label="Prov ID", source_columns=["P_CURR_ALT_ID"]),
        ReportField(field_name="Prov Sort Name", business_label="Prov Sort Name", source_columns=[]),
        ReportField(field_name="Prov Lic Cert Num", business_label="Prov Lic Cert Num", source_columns=["PROV_LIC_CERT_NUM"]),
        ReportField(field_name="OPLC Term Date", business_label="OPLC Term Date", source_columns=["P_CMN_LIC_CERT_END_DT"]),
        ReportField(field_name="MMIS Lic Cert End Date", business_label="MMIS Lic Cert End Date", source_columns=["P_MMIS_LIC_CERT_END_DT"]),
        ReportField(field_name="Reval Stat Cd", business_label="Reval Status CD", source_columns=["P_REVLDTN_STAT_CD"]),
        ReportField(field_name="Total Errors", business_label="Total Errors", source_columns=[]),
        ReportField(field_name="Missing Field", business_label="Missing Field", source_columns=["FAKE_COL"]),
        ReportField(field_name="Ambiguous", business_label="Ambiguous", source_columns=[])
    ])
    
    # Sorts
    dsd.sort_definitions.extend([
        SortDefinition(field="Prov Lic Cert Num", direction=SortDirection.ASCENDING),
        SortDefinition(field="Error Field", direction=SortDirection.ASCENDING)
    ])
    
    # Layout
    dsd.layout.presentation_type_str = "List"
    
    # Selection Criteria
    dsd.selection_criteria.extend([
        SelectionCriterion(field="P_CMN_LIC_CERT_END_DT", description="incoming termination date does not match")
    ])
    
    return dsd

@pytest.fixture
def engine(mock_dsd, real_xml_model):
    req_set = RequirementSet()
    return TraceabilityEngine(mock_dsd, req_set, real_xml_model)

def test_01_prov_id_match(engine):
    res = engine.run()
    trace = next(f for f in res.field_traces if f.dsd_field_name == "Prov ID")
    assert trace.mapping_status == MappingStatus.MATCH
    assert trace.review_status == ReviewStatus.OK

def test_02_prov_sort_name_match(engine):
    res = engine.run()
    trace = next(f for f in res.field_traces if f.dsd_field_name == "Prov Sort Name")
    assert trace.mapping_status == MappingStatus.MATCH

def test_03_prov_lic_cert_num_match(engine):
    res = engine.run()
    trace = next(f for f in res.field_traces if f.dsd_field_name == "Prov Lic Cert Num")
    assert trace.mapping_status == MappingStatus.MATCH

def test_04_oplc_term_date_trace(engine):
    res = engine.run()
    trace = next(f for f in res.field_traces if f.dsd_field_name == "OPLC Term Date")
    assert trace.mapping_status == MappingStatus.MATCH
    assert trace.xml_data_item_name == "OPLC Term Date"

def test_05_mmis_lic_cert_end_date_trace(engine):
    res = engine.run()
    trace = next(f for f in res.field_traces if f.dsd_field_name == "MMIS Lic Cert End Date")
    assert trace.mapping_status == MappingStatus.MATCH

def test_06_reval_stat_cd_implementation(engine):
    res = engine.run()
    trace = next(f for f in res.field_traces if f.dsd_field_name == "Reval Stat Cd")
    assert trace.mapping_status == MappingStatus.MATCH
    assert trace.transformation_present is True
    assert trace.implementation_type in ("LOOKUP", "CALCULATED", "CONDITIONAL", "CONCATENATED")

def test_07_total_errors_aggregation(engine):
    res = engine.run()
    trace = next(f for f in res.field_traces if f.dsd_field_name == "Total Errors")
    assert trace.mapping_status == MappingStatus.MATCH
    assert trace.implementation_type == "AGGREGATED"
    assert trace.transformation_present is True

def test_08_sort_prov_lic_cert_num(engine):
    res = engine.run()
    sort_trace = next(s for s in res.sort_traces if s.dsd_field_name == "Prov Lic Cert Num")
    assert sort_trace.mapping_status == MappingStatus.MATCH

def test_09_sort_error_field_missing(engine):
    res = engine.run()
    sort_trace = next(s for s in res.sort_traces if s.dsd_field_name == "Error Field")
    assert sort_trace.mapping_status == MappingStatus.MISSING_IN_XML
    assert sort_trace.review_status == ReviewStatus.REVIEW_REQUIRED

def test_10_layout_trace(engine):
    res = engine.run()
    layout_trace = next(l for l in res.layout_traces if l.dsd_element == "List")
    assert layout_trace.mapping_status == MappingStatus.MATCH

def test_11_selection_criteria_trace(engine):
    res = engine.run()
    crit_trace = next(c for c in res.selection_traces)
    assert crit_trace.mapping_status == MappingStatus.MATCH

def test_12_xml_only_detection(engine):
    res = engine.run()
    assert any(x for x in res.implementation_only_items if x.item_name == "CognosUserID")

def test_13_ambiguous_mapping(engine):
    res = engine.run()
    trace = next(f for f in res.field_traces if f.dsd_field_name == "Ambiguous")
    # Will probably be NOT_MATCHED or FALLBACK, so Review Required
    assert trace.review_status == ReviewStatus.REVIEW_REQUIRED

def test_14_missing_xml(engine):
    res = engine.run()
    trace = next(f for f in res.field_traces if f.dsd_field_name == "Missing Field")
    assert trace.mapping_status == MappingStatus.MISSING_IN_XML

def test_15_provenance(engine):
    res = engine.run()
    trace = next(f for f in res.field_traces if f.dsd_field_name == "Prov ID")
    assert trace.xml_provenance != ""

def test_16_no_test_case_generation(engine):
    res = engine.run()
    # explicitly check we just returned TraceabilityResult and didn't touch RequirementSet logic
    assert isinstance(res.field_traces, list)
    # The requirement set should remain completely unmodified
    assert len(engine.req_set.requirements) == 0
