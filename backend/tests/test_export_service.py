"""
Tests for app.services.export_service.

DB-dependent (sessions, refinement rows, source documents, export
records), so — consistent with test_gatekeeper.py/test_knowledge_base.py/
test_semantic_cache.py/test_refinement.py in earlier phases —
this is syntax-checked only in this sandbox (no sqlalchemy here). The
underlying workbook-building logic it wires together is covered for real
by test_excel_compiler.py.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models import audit, knowledge_base as kb_models, cache as cache_models, refinement as refinement_models, export as export_models  # noqa: F401
from app.models.audit import Session as SessionModel
from app.models.knowledge_base import SourceDocument
from app.services.refinement import add_generated_rows
from app.services.export_service import export_session_to_excel, get_latest_export, ExportError

SAMPLE_SCENARIOS = [
    {
        "sl_no": 1, "test_scenario": "Validate SWIPE_CARD_IND values",
        "detailed_test_steps": "1. Query MEMBERS.", "expected_results": "Only Y or N.",
        "verification_sql": "SELECT MEMBERS.SWIPE_CARD_IND FROM MEMBERS;", "category": "valid_value_check",
    },
]


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "EXPORT_DIR", str(tmp_path / "exports"))

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def session_id(db_session):
    s = SessionModel(user_id="tester", report_id="RPT-1", cr_id="CR-1", cr_description="desc", status="gatekeeper_confirmed")
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s.id


def test_export_with_no_grid_rows_raises_export_error(db_session, session_id):
    with pytest.raises(ExportError):
        export_session_to_excel(db_session, session_id=session_id)


def test_export_missing_session_raises_export_error(db_session):
    with pytest.raises(ExportError):
        export_session_to_excel(db_session, session_id=99999)


def test_successful_export_creates_file_and_record(db_session, session_id):
    add_generated_rows(
        db_session, session_id=session_id, report_id="RPT-1",
        requirement_text="req", scenarios=SAMPLE_SCENARIOS,
    )
    record = export_session_to_excel(db_session, session_id=session_id, exported_by="jane.tester")

    assert record.row_count == 1
    assert Path(record.file_path).exists()
    assert len(record.file_sha256) == 64


def test_get_latest_export_returns_most_recent(db_session, session_id):
    add_generated_rows(
        db_session, session_id=session_id, report_id="RPT-1",
        requirement_text="req", scenarios=SAMPLE_SCENARIOS,
    )
    first = export_session_to_excel(db_session, session_id=session_id)
    second = export_session_to_excel(db_session, session_id=session_id)

    latest = get_latest_export(db_session, session_id)
    assert latest.id == second.id
    assert latest.id != first.id


def test_export_includes_source_documents(db_session, session_id):
    db_session.add(SourceDocument(
        report_id="RPT-1", filename="sample_ldm.xlsx", file_sha256="a" * 64,
        file_type="xlsx", parse_status="parsed",
    ))
    db_session.commit()

    add_generated_rows(
        db_session, session_id=session_id, report_id="RPT-1",
        requirement_text="req", scenarios=SAMPLE_SCENARIOS,
    )
    record = export_session_to_excel(db_session, session_id=session_id)
    assert Path(record.file_path).exists()


def test_export_writes_audit_log_entry(db_session, session_id):
    from app.models.audit import AuditLogEntry

    add_generated_rows(
        db_session, session_id=session_id, report_id="RPT-1",
        requirement_text="req", scenarios=SAMPLE_SCENARIOS,
    )
    export_session_to_excel(db_session, session_id=session_id, exported_by="jane.tester")

    logs = db_session.query(AuditLogEntry).filter(AuditLogEntry.event_type == "EXPORT").all()
    assert len(logs) == 1
    assert logs[0].user_id == "jane.tester"
