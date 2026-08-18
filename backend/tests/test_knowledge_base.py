"""
Tests for app.services.knowledge_base.

Uses an in-memory SQLite DB per test so these are fast and fully isolated
from the real app_metadata.db file.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models import audit, knowledge_base as kb_models  # noqa: F401  (register tables)
from app.services.document_parser import parse_document
from app.services.knowledge_base import (
    persist_parsed_document,
    get_knowledge_base_summary,
    compute_file_sha256,
    INSUFFICIENT_METADATA_MESSAGE,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_persist_creates_kb_rows_scoped_to_report_id(db_session):
    parsed = parse_document(FIXTURES / "sample_ldm.xlsx")
    result = persist_parsed_document(
        db_session,
        report_id="RPT-100",
        cr_id="CR-2026-001",
        filename="sample_ldm.xlsx",
        file_path=FIXTURES / "sample_ldm.xlsx",
        file_type="xlsx",
        uploaded_by="jane.tester",
        parsed=parsed,
    )

    assert result["parse_status"] == "parsed"
    assert result["counts"]["columns"] == 4
    assert result["counts"]["joins"] == 1
    assert result["message"] is None

    summary = get_knowledge_base_summary(db_session, "RPT-100")
    assert len(summary["columns"]) == 4
    assert len(summary["source_documents"]) == 1


def test_insufficient_metadata_message_on_junk_file(db_session):
    parsed = parse_document(FIXTURES / "junk.csv")
    result = persist_parsed_document(
        db_session,
        report_id="RPT-200",
        cr_id=None,
        filename="junk.csv",
        file_path=FIXTURES / "junk.csv",
        file_type="csv",
        uploaded_by=None,
        parsed=parsed,
    )

    assert result["parse_status"] == "insufficient_metadata"
    assert result["message"] == INSUFFICIENT_METADATA_MESSAGE


def test_cache_busting_invalidates_prior_kb_on_file_change(db_session, tmp_path):
    parsed1 = parse_document(FIXTURES / "sample_ldm.xlsx")
    persist_parsed_document(
        db_session,
        report_id="RPT-300",
        cr_id="CR-1",
        filename="sample_ldm.xlsx",
        file_path=FIXTURES / "sample_ldm.xlsx",
        file_type="xlsx",
        uploaded_by="jane.tester",
        parsed=parsed1,
    )
    summary_before = get_knowledge_base_summary(db_session, "RPT-300")
    assert len(summary_before["columns"]) == 4

    # Simulate a DIFFERENT file for the same report_id (different content ->
    # different hash) — this must invalidate the old KB rows per the
    # cache-busting rule.
    modified_path = tmp_path / "sample_ldm_modified.docx"
    # reuse the docx fixture as a stand-in for "a different file"
    modified_path.write_bytes((FIXTURES / "sample_rdd.docx").read_bytes())

    parsed2 = parse_document(modified_path)
    result2 = persist_parsed_document(
        db_session,
        report_id="RPT-300",
        cr_id="CR-1",
        filename="sample_ldm_modified.docx",
        file_path=modified_path,
        file_type="docx",
        uploaded_by="jane.tester",
        parsed=parsed2,
    )

    assert result2["kb_invalidated_prior_version"] is True

    summary_after = get_knowledge_base_summary(db_session, "RPT-300")
    # Old MEMBERS/CLAIMS columns gone, replaced by PROVIDERS from the new file
    table_names = {c["table_name"] for c in summary_after["columns"]}
    assert table_names == {"PROVIDERS"}
    assert len(summary_after["source_documents"]) == 1


def test_reupload_of_identical_file_does_not_invalidate(db_session):
    parsed1 = parse_document(FIXTURES / "sample_ldm.xlsx")
    persist_parsed_document(
        db_session, report_id="RPT-400", cr_id="CR-1", filename="sample_ldm.xlsx",
        file_path=FIXTURES / "sample_ldm.xlsx", file_type="xlsx",
        uploaded_by="jane.tester", parsed=parsed1,
    )

    parsed2 = parse_document(FIXTURES / "sample_ldm.xlsx")
    result2 = persist_parsed_document(
        db_session, report_id="RPT-400", cr_id="CR-1", filename="sample_ldm.xlsx",
        file_path=FIXTURES / "sample_ldm.xlsx", file_type="xlsx",
        uploaded_by="jane.tester", parsed=parsed2,
    )

    assert result2["kb_invalidated_prior_version"] is False


def test_compute_file_sha256_is_deterministic():
    h1 = compute_file_sha256(FIXTURES / "sample_ldm.xlsx")
    h2 = compute_file_sha256(FIXTURES / "sample_ldm.xlsx")
    assert h1 == h2
    assert len(h1) == 64  # hex-encoded SHA-256
