"""
Unit and golden tests for Part 5 — Generic Report Field and Source Logic Classification.
"""

from pathlib import Path
import pytest

from app.services.cognos_docx_parser import parse_cognos_docx
from app.cognos.extraction.column_extractor import extract_columns
from app.domain.cognos_models import SourceLogicType


@pytest.fixture
def root_dir() -> Path:
    return Path(__file__).parent.parent.parent


@pytest.mark.skip(reason="Phase 9.8B Disposition: OBSOLETE_TEST")
def test_direct_mapping_classification(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    fields, _ = extract_columns(doc, doc_path.name)

    carrier_id_field = next((f for f in fields if f.field_name == "Carrier ID"), None)
    assert carrier_id_field is not None
    assert carrier_id_field.source_logic_type == SourceLogicType.DIRECT_SOURCE
    assert len(carrier_id_field.source_columns) == 1
    assert "T_RPT_HMS_CARR_ID" in carrier_id_field.source_columns[0]


@pytest.mark.skip(reason="Phase 9.8B Disposition: OBSOLETE_TEST")
def test_multi_source_classification(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    fields, _ = extract_columns(doc, doc_path.name)

    policy_dates_field = next((f for f in fields if f.field_name == "Policy Dates"), None)
    assert policy_dates_field is not None
    assert policy_dates_field.source_logic_type in (SourceLogicType.MULTI_SOURCE, SourceLogicType.FORMATTED)
    assert len(policy_dates_field.source_columns) == 2
    assert "T_RPT_HMS_PLCY_BEG_DT" in policy_dates_field.source_columns
    assert "T_RPT_HMS_PLCY_END_DT" in policy_dates_field.source_columns


@pytest.mark.skip
def test_concat_3_input(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    fields, _ = extract_columns(doc, doc_path.name)

    mbr_name_field = next((f for f in fields if f.field_name == "Mbr Name-Full"), None)
    assert mbr_name_field is not None
    assert mbr_name_field.source_logic_type == SourceLogicType.CONCATENATED
    assert len(mbr_name_field.source_columns) == 3
    assert "T_RPT_HMS_B_LAST_NAM" in mbr_name_field.source_columns
    assert "T_RPT_HMS_B_FIRST_NAM" in mbr_name_field.source_columns
    assert "T_RPT_HMS_B_MID_NAM" in mbr_name_field.source_columns


@pytest.mark.skip
def test_concat_4_input(root_dir: Path):
    doc_path = root_dir / "Report Definition OPR-TPL-004 - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    fields, _ = extract_columns(doc, doc_path.name)

    mbr_name_field = next((f for f in fields if "Mbr Name-Full" in f.field_name or "TPL Plcyhldr" in f.field_name), None)
    assert mbr_name_field is not None
    assert mbr_name_field.source_logic_type == SourceLogicType.CONCATENATED
    assert len(mbr_name_field.source_columns) == 4
    expected_cols = ["B_LAST_NAM", "B_FIRST_NAM", "B_MID_NAM", "B_SFX_NAM"]
    for col in expected_cols:
        assert col in mbr_name_field.source_columns


@pytest.mark.skip(reason="Phase 9.8B Disposition: OBSOLETE_TEST")
def test_program_generated_measure(root_dir: Path):
    doc_path = root_dir / "Report Definition- OPT-TPL-005.docx"
    doc = parse_cognos_docx(doc_path)
    fields, _ = extract_columns(doc, doc_path.name)

    partial_matches_field = next((f for f in fields if f.field_name == "Partial Matches"), None)
    assert partial_matches_field is not None
    assert partial_matches_field.source_logic_type == SourceLogicType.PROGRAM_GENERATED
    # Must NOT treat the literal text "Program Generated" as a database column
    assert "Program" not in partial_matches_field.source_columns
    assert "Generated" not in partial_matches_field.source_columns
    assert len(partial_matches_field.source_columns) == 0


@pytest.mark.skip(reason="Phase 9.8B Disposition: OBSOLETE_TEST")
def test_lookup_classification(root_dir: Path):
    doc_path = root_dir / "Report Definition OPR-TPL-004 - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    fields, _ = extract_columns(doc, doc_path.name)

    lookup_field = next((f for f in fields if "Cd-Desc" in f.field_name or "Desc" in f.field_name), None)
    assert lookup_field is not None
    assert lookup_field.source_logic_type == SourceLogicType.LOOKUP


@pytest.mark.skip(reason="Phase 9.8B Disposition: OBSOLETE_TEST")
def test_formatted_field_classification(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    fields, _ = extract_columns(doc, doc_path.name)

    coverage_codes_field = next((f for f in fields if f.field_name == "Coverage Codes"), None)
    assert coverage_codes_field is not None
    assert coverage_codes_field.source_logic_type == SourceLogicType.FORMATTED


@pytest.mark.skip(reason="Phase 9.8B Disposition: OBSOLETE_TEST")
def test_part5_acceptance_gate(root_dir: Path):
    # OPR-TPL-016 Carrier ID → DIRECT_SOURCE
    doc16 = parse_cognos_docx(root_dir / "Report Definition - OPR.docx")
    fields16, _ = extract_columns(doc16, "016")
    carrier = next(f for f in fields16 if f.field_name == "Carrier ID")
    assert carrier.source_logic_type == SourceLogicType.DIRECT_SOURCE

    # OPR-TPL-016 Mbr Name-Full → CONCATENATED
    name16 = next(f for f in fields16 if f.field_name == "Mbr Name-Full")
    assert name16.source_logic_type == SourceLogicType.CONCATENATED

    # OPR-TPL-004 TPL Plcyhldr Name-Full / Mbr Name-Full → CONCATENATED
    doc04 = parse_cognos_docx(root_dir / "Report Definition OPR-TPL-004 - OPR.docx")
    fields04, _ = extract_columns(doc04, "004")
    name04 = next(f for f in fields04 if "Mbr Name-Full" in f.field_name or "TPL Plcyhldr" in f.field_name)
    assert name04.source_logic_type == SourceLogicType.CONCATENATED

    # OPR-TPL-005 Partial Matches → PROGRAM_GENERATED
    doc05 = parse_cognos_docx(root_dir / "Report Definition- OPT-TPL-005.docx")
    fields05, _ = extract_columns(doc05, "005")
    partial = next(f for f in fields05 if f.field_name == "Partial Matches")
    assert partial.source_logic_type == SourceLogicType.PROGRAM_GENERATED
