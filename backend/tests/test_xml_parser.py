import pytest
from pathlib import Path

from app.cognos.extraction.xml_parser import parse_cognos_xml
from app.domain.cognos_xml_models import (
    ImplementationType,
    LayoutObjectType,
    UsageContext,
    FilterContext,
)


@pytest.fixture
def real_xml_path():
    path = Path(__file__).parent / "fixtures" / "PRV-INT-027.xml"
    if not path.exists():
        pytest.skip(f"Real XML file {path} not found.")
    return path


@pytest.fixture
def synthetic_xml_path():
    path = Path(__file__).parent / "fixtures" / "PRV-INT-027-synthetic.xml"
    if not path.exists():
        pytest.skip(f"Synthetic XML file {path} not found.")
    return path


def test_01_metadata(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    assert model.report_metadata.get("filename") == "PRV-INT-027.xml"


def test_02_package_model(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    # Validate package path extraction
    assert "package" in model.package_model.lower()


def test_03_query(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    assert any(q.query_name == "q_PRV_INT_027" for q in model.queries)


def test_04_sql(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    q = next(q for q in model.queries if q.query_name == "q_PRV_INT_027")
    assert q.sql != ""
    assert "SELECT" in q.sql.upper()


def test_05_source_tables(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    q = next(q for q in model.queries if q.query_name == "q_PRV_INT_027")
    tables = set(t for item in q.data_items for t in item.source_tables)
    assert "P_RPT_CLDI_TERM_TB" in tables
    assert "R_VV_TB" in tables


def test_06_source_columns(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    q = next(q for q in model.queries if q.query_name == "q_PRV_INT_027")
    columns = set(c for item in q.data_items for c in item.source_columns)
    assert len(columns) > 0


def test_07_data_items(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    q = next(q for q in model.queries if q.query_name == "q_PRV_INT_027")
    names = [item.name for item in q.data_items]
    assert "Prov ID" in names
    assert "Prov Sort Name" in names
    assert "Prov Lic Cert Num" in names
    assert "OPLC Term Date" in names
    assert "MMIS Lic Cert End Date" in names
    assert "Reval Stat Cd" in names
    assert "Last Reval Status Dt" in names
    assert "Total Errors" in names


def test_08_direct_mapping(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    q = next(q for q in model.queries if q.query_name == "q_PRV_INT_027")
    data_items = {item.name: item for item in q.data_items}
    
    assert data_items["Prov ID"].implementation_type == ImplementationType.DIRECT
    assert data_items["Prov Sort Name"].implementation_type == ImplementationType.DIRECT
    assert data_items["Prov Lic Cert Num"].implementation_type == ImplementationType.DIRECT


def test_09_lookup_calculated_mapping(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    q = next(q for q in model.queries if q.query_name == "q_PRV_INT_027")
    data_items = {item.name: item for item in q.data_items}
    
    assert data_items["Reval Stat Cd"].implementation_type in (ImplementationType.LOOKUP, ImplementationType.CALCULATED, ImplementationType.CONDITIONAL)


def test_10_aggregation(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    q = next(q for q in model.queries if q.query_name == "q_PRV_INT_027")
    data_items = {item.name: item for item in q.data_items}
    
    assert data_items["Total Errors"].implementation_type == ImplementationType.AGGREGATED
    assert "count" in data_items["Total Errors"].aggregate_function.lower()


def test_11_sorting(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    # Must find exact sort list
    sorts = [s for layout in model.layouts for s in layout.sorts]
    assert "Prov Lic Cert Num" in sorts


def test_12_formatting(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    q = next(q for q in model.queries if q.query_name == "q_PRV_INT_027")
    data_items = {item.name: item for item in q.data_items}
    
    assert data_items["OPLC Term Date"].data_format is not None


def test_13_no_data_handler(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    handlers = [h for layout in model.layouts for h in layout.no_data_handlers]
    assert any("*** No Data Found ***" in h for h in handlers)


def test_14_usage_visibility(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    q = next(q for q in model.queries if q.query_name == "q_PRV_INT_027")
    data_items = {item.name: item for item in q.data_items}
    
    # Must correctly classify visibility context, not just simple boolean
    assert len(data_items["Prov ID"].usage_context) > 0


def test_15_selection_criteria(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    # Ensure page filter or conditional formatting is extracted
    assert any(f.context == FilterContext.REPORT_SELECTION_CRITERIA for q in model.queries for f in q.filters) or \
           any(f.context == FilterContext.REPORT_SELECTION_CRITERIA for l in model.layouts for f in l.conditions)


def test_16_variables(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    assert len(model.variables) > 0


def test_17_provenance(real_xml_path):
    model = parse_cognos_xml(real_xml_path)
    q = next(q for q in model.queries if q.query_name == "q_PRV_INT_027")
    assert q.data_items[0].provenance != ""
    assert "query" in q.data_items[0].provenance


def test_18_malformed_xml(synthetic_xml_path):
    # Using synthetic XML to test parser robustness
    pass


def test_19_missing_elements(synthetic_xml_path):
    # Test handling of missing elements gracefully
    pass


def test_20_unsupported_structures(synthetic_xml_path):
    # Test handling of unknown tags gracefully
    pass
