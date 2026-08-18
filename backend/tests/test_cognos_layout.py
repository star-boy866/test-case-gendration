"""
Unit and golden tests for Part 4 — Cognos Presentation Type and Layout.
"""

from pathlib import Path
import pytest

from app.services.cognos_docx_parser import parse_cognos_docx
from app.cognos.extraction.layout_extractor import extract_layout
from app.domain.cognos_models import PresentationType


@pytest.fixture
def root_dir() -> Path:
    return Path(__file__).parent.parent.parent


def test_opr016_list_layout(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    layout, _ = extract_layout(doc, doc_path.name)

    assert layout.presentation_type == PresentationType.LIST_OBJECT
    assert layout.presentation_type_str == "LIST_OBJECT"
    assert len(layout.header_elements) > 0
    assert len(layout.footer_elements) > 0


def test_opr004_list_layout(root_dir: Path):
    doc_path = root_dir / "Report Definition OPR-TPL-004 - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    layout, _ = extract_layout(doc, doc_path.name)

    assert layout.presentation_type == PresentationType.LIST_OBJECT
    assert layout.presentation_type_str == "LIST_OBJECT"
    assert len(layout.header_elements) > 0
    assert len(layout.footer_elements) > 0


@pytest.mark.skip
def test_opr005_crosstab_layout(root_dir: Path):
    doc_path = root_dir / "Report Definition- OPT-TPL-005.docx"
    doc = parse_cognos_docx(doc_path)
    layout, _ = extract_layout(doc, doc_path.name)

    assert layout.presentation_type == PresentationType.CROSSTAB_OBJECT
    assert layout.presentation_type_str == "CROSSTAB_OBJECT"

    # Assert Crosstab Measures
    expected_measures = [
        "Records Read",
        "Exact Matches",
        "Partial Matches",
        "New Coverage",
        "New Members",
        "Policies Added",
        "Active Policies",
        "Pended Policies",
        "Existing Policies Modified",
    ]
    for measure in expected_measures:
        assert measure in layout.measures, f"Missing crosstab measure: {measure}"

    assert len(layout.row_dimensions) > 0
    assert "Total" in layout.column_dimensions


def test_layout_does_not_import_specification_body_mappings(root_dir: Path):
    golden_files = [
        "Report Definition - OPR.docx",
        "Report Definition OPR-TPL-004 - OPR.docx",
        "Report Definition- OPT-TPL-005.docx",
    ]
    body_fields_to_guard = [
        "Policy Dates",
        "Mbr Cvrg Dates",
        "Coverage Codes",
        "Records Read",
        "Exact Matches",
        "Partial Matches",
        "New Coverage",
        "New Members",
        "Policies Added",
        "Active Policies",
        "Pended Policies",
        "Existing Policies Modified",
    ]

    for filename in golden_files:
        doc_path = root_dir / filename
        doc = parse_cognos_docx(doc_path)
        layout, _ = extract_layout(doc, filename)

        header_names = [h.element_name.strip().lower() for h in layout.header_elements]
        for body_field in body_fields_to_guard:
            assert body_field.lower() not in header_names, (
                f"Body field '{body_field}' was incorrectly classified as a visual header in {filename}"
            )
