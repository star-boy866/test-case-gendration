"""
Unit and golden document structural tests for Part 1 Generic Cognos DOCX Parser.
"""

from pathlib import Path
import pytest
import docx

from app.services.cognos_docx_parser import (
    parse_cognos_docx,
    dump_document_structure,
    CheckboxState,
    _extract_checkboxes,
    iter_block_items,
)


@pytest.fixture
def root_dir() -> Path:
    return Path(__file__).parent.parent.parent


def test_document_blocks_are_in_order(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    assert doc_path.exists(), f"Golden doc not found at {doc_path}"
    
    document = docx.Document(str(doc_path))
    blocks = list(iter_block_items(document))
    assert len(blocks) > 0
    p_count = sum(1 for b in blocks if isinstance(b, docx.text.paragraph.Paragraph))
    t_count = sum(1 for b in blocks if isinstance(b, docx.table.Table))
    assert p_count > 0
    assert t_count > 0


def test_section_assignment_uses_document_order(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    
    prev_order = 0
    for sec in doc.sections:
        assert sec.start_order >= prev_order
        prev_order = sec.start_order
        for t in sec.tables:
            assert t.source_order >= sec.start_order


def test_table_rows_are_preserved(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    
    table1 = doc.all_parsed_tables[0]
    assert table1.row_count == 49
    assert len(table1.rows) == 49


def test_cell_order_is_preserved(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    
    table1 = doc.all_parsed_tables[0]
    first_row = table1.rows[0]
    for idx, cell in enumerate(first_row.cells):
        assert cell.column_index == idx
        assert cell.row_index == 0


def test_checkbox_checked_detected():
    boxes = _extract_checkboxes("☑ Option A  ☐ Option B")
    assert len(boxes) == 2
    assert boxes[0]["label"] == "Option A"
    assert boxes[0]["state"] == CheckboxState.CHECKED
    assert boxes[0]["checked"] is True


def test_checkbox_unchecked_detected():
    boxes = _extract_checkboxes("☐ Option B")
    assert len(boxes) == 1
    assert boxes[0]["label"] == "Option B"
    assert boxes[0]["state"] == CheckboxState.UNCHECKED
    assert boxes[0]["checked"] is False


def test_unknown_checkbox_state_supported():
    boxes = _extract_checkboxes("Plain text without checkbox")
    assert len(boxes) == 0


def test_no_fake_page_numbers(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    
    for sec in doc.sections:
        assert sec.source_page is None or isinstance(sec.source_page, int)


def test_golden_structure_opr016(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    doc = parse_cognos_docx(doc_path)
    
    dump = dump_document_structure(doc)
    assert "DOCUMENT STRUCTURE DUMP: Report Definition - OPR.docx" in dump
    assert "SECTION: Report Definition" in dump
    assert "SECTION: Report Layout" in dump
    assert "SECTION: Report Specification" in dump
    assert len(doc.sections) >= 3
    assert len(doc.all_parsed_tables) >= 3


def test_golden_structure_opr004(root_dir: Path):
    doc_path = root_dir / "Report Definition OPR-TPL-004 - OPR.docx"
    assert doc_path.exists()
    doc = parse_cognos_docx(doc_path)
    
    dump = dump_document_structure(doc)
    assert "SECTION: Report Definition" in dump
    assert "SECTION: Report Layout" in dump
    assert "SECTION: Report Specification" in dump
    assert len(doc.all_parsed_tables) >= 3


def test_golden_structure_opr005(root_dir: Path):
    doc_path = root_dir / "Report Definition- OPT-TPL-005.docx"
    assert doc_path.exists()
    doc = parse_cognos_docx(doc_path)
    
    dump = dump_document_structure(doc)
    assert "SECTION: Report Definition" in dump
    assert "SECTION: Report Layout" in dump
    assert "SECTION: Report Specification" in dump
    assert len(doc.all_parsed_tables) >= 3
