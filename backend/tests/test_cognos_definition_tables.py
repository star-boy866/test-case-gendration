"""
Unit and golden tests for Part 3 — Generic Cognos Definition Table Extraction.
"""

from pathlib import Path
import pytest

from app.services.cognos_docx_parser import parse_cognos_docx
from app.cognos.extraction.sort_extractor import (
    extract_sorts_and_groups,
    extract_selection_criteria,
    extract_output_definition,
)
from app.domain.cognos_models import SortDirection


@pytest.fixture
def root_dir() -> Path:
    return Path(__file__).parent.parent.parent


def test_opr016_sorts(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    sorts, _, _, _, _ = extract_sorts_and_groups(doc, doc_path.name)

    assert len(sorts) == 4
    expected_fields = ["LOB Cd-Desc", "Filename", "Err Cd", "Mbr Alt ID"]
    for idx, expected in enumerate(expected_fields, start=1):
        assert sorts[idx - 1].priority == idx
        assert sorts[idx - 1].field == expected
        assert sorts[idx - 1].direction == SortDirection.ASCENDING


def test_opr004_sorts(root_dir: Path):
    doc_path = root_dir / "Report Definition OPR-TPL-004 - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    sorts, _, _, _, _ = extract_sorts_and_groups(doc, doc_path.name)

    assert len(sorts) == 7
    expected_fields = [
        "LOB Cd-Desc",
        "Process Name",
        "Src Cd-Desc",
        "TPL Carr Name",
        "TPL Group ID",
        "TPL Plcy Num",
        "Mbr Alt ID",
    ]
    for idx, expected in enumerate(expected_fields, start=1):
        assert sorts[idx - 1].priority == idx
        assert sorts[idx - 1].field == expected
        assert sorts[idx - 1].direction == SortDirection.ASCENDING

    # Strict isolation assertion: Distribution groups MUST NOT contaminate sorts
    sort_field_names = [s.field for s in sorts]
    assert "Insurance Carriers" not in sort_field_names
    assert "Operations" not in sort_field_names


def test_opr005_sorts(root_dir: Path):
    doc_path = root_dir / "Report Definition- OPT-TPL-005.docx"
    doc = parse_cognos_docx(doc_path)
    sorts, _, _, _, _ = extract_sorts_and_groups(doc, doc_path.name)

    assert len(sorts) == 2
    expected_fields = ["LOB Cd-Desc", "Src Cd-Desc"]
    for idx, expected in enumerate(expected_fields, start=1):
        assert sorts[idx - 1].priority == idx
        assert sorts[idx - 1].field == expected
        assert sorts[idx - 1].direction == SortDirection.ASCENDING


def test_opr016_control_breaks(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    _, control_breaks, _, _, _ = extract_sorts_and_groups(doc, doc_path.name)

    page_breaks = [cb.field for cb in control_breaks if cb.break_type == "Page"]
    section_breaks = [cb.field for cb in control_breaks if cb.break_type == "Section"]

    assert "LOB Cd-Desc" in page_breaks
    assert "Filename" in page_breaks
    assert "Err Cd" in page_breaks
    assert "TPL Group ID" in section_breaks


def test_opr004_control_breaks(root_dir: Path):
    doc_path = root_dir / "Report Definition OPR-TPL-004 - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    _, control_breaks, _, _, _ = extract_sorts_and_groups(doc, doc_path.name)

    page_breaks = [cb.field for cb in control_breaks if cb.break_type == "Page"]
    section_breaks = [cb.field for cb in control_breaks if cb.break_type == "Section"]

    assert "LOB Cd-Desc" in page_breaks
    assert "Process Name" in page_breaks
    assert "Src Cd-Desc" in page_breaks
    assert "TPL Carr ID" in page_breaks
    assert "TPL Group ID" in section_breaks


def test_opr016_selection(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    criteria = extract_selection_criteria(doc, doc_path.name)

    assert len(criteria) >= 1
    filename_crit = next((c for c in criteria if c.field == "Filename"), None)
    assert filename_crit is not None
    assert filename_crit.parameter_name in ("", "No", "Prompt") or not filename_crit.parameter_name


def test_opr004_selection(root_dir: Path):
    doc_path = root_dir / "Report Definition OPR-TPL-004 - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    criteria = extract_selection_criteria(doc, doc_path.name)

    proc_crit = next((c for c in criteria if c.field == "Process Name"), None)
    assert proc_crit is not None
    assert "<Parameter passed from process>" in proc_crit.parameter_name


def test_opr005_counts(root_dir: Path):
    doc_path = root_dir / "Report Definition- OPT-TPL-005.docx"
    doc = parse_cognos_docx(doc_path)
    _, _, _, counts, _ = extract_sorts_and_groups(doc, doc_path.name)

    count_fields = [c.field for c in counts]
    assert "Total Records Exchanged" in count_fields
    assert "Exact Matches" in count_fields
    assert any("Partial Matches" in cf for cf in count_fields)
    assert "Number of Records Added to Carrier File" in count_fields
    assert "Number of Existing Records Modified" in count_fields


def test_opr004_distribution(root_dir: Path):
    doc_path = root_dir / "Report Definition OPR-TPL-004 - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    output = extract_output_definition(doc, doc_path.name)

    assert output.distribution_enabled is True
    assert "Insurance Carriers" in output.distribution_groups
    assert "Operations" in output.distribution_groups


def test_opr004_retention(root_dir: Path):
    doc_path = root_dir / "Report Definition OPR-TPL-004 - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    output = extract_output_definition(doc, doc_path.name)

    assert output.retention_type == "EDMS" or output.retention == "EDMS"
    assert output.output_versions == "7 Years" or "7" in output.output_versions
