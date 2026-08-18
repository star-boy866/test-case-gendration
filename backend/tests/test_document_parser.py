"""
Tests for app.services.document_parser.

These fixtures were generated once (see docs/PHASES.md Phase 1 notes) with
openpyxl/python-docx and are checked in under tests/fixtures/ so the suite
is deterministic and doesn't need to regenerate files on every run.
"""

from pathlib import Path

import pytest

from app.services.document_parser import parse_document

FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_column_level_ldm_sheet():
    result = parse_document(FIXTURES / "sample_ldm.xlsx")

    table_names = {t["table_name"] for t in result.tables}
    assert table_names == {"MEMBERS", "CLAIMS"}
    assert len(result.columns) == 4

    member_id_col = next(c for c in result.columns if c["column_name"] == "MEMBER_ID" and c["table_name"] == "MEMBERS")
    assert member_id_col["key_type"] == "PK"
    assert member_id_col["data_type"] == "VARCHAR(20)"


def test_parses_joins_sheet_separately_from_columns():
    result = parse_document(FIXTURES / "sample_ldm.xlsx")

    assert len(result.joins) == 1
    join = result.joins[0]
    assert join["from_table"] == "CLAIMS"
    assert join["to_table"] == "MEMBERS"
    assert join["join_type"] == "INNER"


def test_parses_valid_values_without_polluting_columns():
    result = parse_document(FIXTURES / "sample_ldm.xlsx")

    vv_values = {v["valid_value"] for v in result.valid_values}
    assert vv_values == {"Y", "N"}

    # Regression guard: valid-values sheet also has table_name/column_name
    # context columns and must NOT be double-counted as LDM columns.
    assert len(result.columns) == 4


def test_parses_business_rules_without_polluting_columns():
    result = parse_document(FIXTURES / "sample_ldm.xlsx")

    assert len(result.business_rules) == 1
    rule = result.business_rules[0]
    assert "SWIPE_CARD_IND" in rule["rule_text"]
    assert rule["related_table"] == "MEMBERS"
    assert len(result.columns) == 4  # regression guard, see above


def test_unrecognized_sheet_is_skipped_with_warning():
    result = parse_document(FIXTURES / "sample_ldm.xlsx")

    assert result.sheets_skipped == 1
    assert any("RandomNotes" in w for w in result.warnings)


def test_docx_table_extraction_and_paragraph_isolation():
    result = parse_document(FIXTURES / "sample_rdd.docx")

    assert len(result.columns) == 1
    assert result.columns[0]["table_name"] == "PROVIDERS"

    # Free-form paragraph content (including an embedded business rule in
    # prose) must land in unstructured_notes, NEVER in business_rules.
    assert len(result.business_rules) == 0
    assert len(result.unstructured_notes) == 1
    assert "policy 4.2" in result.unstructured_notes[0]["content"]


def test_no_recognizable_structure_yields_no_structured_content():
    result = parse_document(FIXTURES / "junk.csv")

    assert result.has_structured_content is False
    assert len(result.warnings) == 1


def test_unsupported_extension_raises():
    with pytest.raises(ValueError):
        parse_document(FIXTURES / "sample_ldm.xlsx.txt")
