"""
Tests for app.services.gatekeeper — the Phase 2 "strict blocking step".

Covers:
- Scope summary reflects real KB extraction counts.
- Confirmation is refused when there's no structured KB content.
- Confirmation succeeds and require_gatekeeper_confirmation then passes.
- require_gatekeeper_confirmation blocks when nothing has been confirmed.
- Re-uploading a changed file downgrades a prior confirmation (closing the
  loop with Phase 1's cache-busting rule).
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models import audit, knowledge_base as kb_models  # noqa: F401  (register tables)
from app.services.document_parser import parse_document
from app.services.knowledge_base import persist_parsed_document
from app.services.gatekeeper import (
    get_scope_summary,
    confirm_scope,
    require_gatekeeper_confirmation,
    GatekeeperError,
    GatekeeperBlockedError,
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


def _ingest_sample(db, report_id="RPT-500", cr_id="CR-500"):
    parsed = parse_document(FIXTURES / "sample_ldm.xlsx")
    return persist_parsed_document(
        db, report_id=report_id, cr_id=cr_id, filename="sample_ldm.xlsx",
        file_path=FIXTURES / "sample_ldm.xlsx", file_type="xlsx",
        uploaded_by="jane.tester", parsed=parsed,
    )


def test_scope_summary_reflects_kb_counts_and_is_unconfirmed(db_session):
    _ingest_sample(db_session)
    summary = get_scope_summary(db_session, "RPT-500")

    assert summary["can_confirm"] is True
    assert summary["is_confirmed"] is False
    assert summary["counts"]["columns"] == 4
    assert summary["cr_id"] == "CR-500"


def test_confirm_scope_refused_without_structured_kb(db_session):
    with pytest.raises(GatekeeperError):
        confirm_scope(
            db_session, report_id="RPT-EMPTY", cr_id="CR-1",
            cr_description="No docs uploaded yet", confirmed_by="jane.tester",
        )


def test_confirm_scope_requires_cr_description(db_session):
    _ingest_sample(db_session, report_id="RPT-501")
    with pytest.raises(GatekeeperError):
        confirm_scope(
            db_session, report_id="RPT-501", cr_id="CR-1",
            cr_description="   ", confirmed_by="jane.tester",
        )


def test_generation_blocked_before_confirmation(db_session):
    _ingest_sample(db_session, report_id="RPT-502")
    with pytest.raises(GatekeeperBlockedError):
        require_gatekeeper_confirmation(db_session, "RPT-502")


def test_generation_allowed_after_confirmation(db_session):
    _ingest_sample(db_session, report_id="RPT-503")
    confirm_scope(
        db_session, report_id="RPT-503", cr_id="CR-503",
        cr_description="Validate swipe card indicator logic",
        confirmed_by="jane.tester",
    )

    session = require_gatekeeper_confirmation(db_session, "RPT-503")
    assert session.status == "gatekeeper_confirmed"
    assert session.cr_id == "CR-503"


def test_reupload_of_changed_file_downgrades_confirmation(db_session, tmp_path):
    _ingest_sample(db_session, report_id="RPT-504")
    confirm_scope(
        db_session, report_id="RPT-504", cr_id="CR-504",
        cr_description="Validate swipe card indicator logic",
        confirmed_by="jane.tester",
    )
    # confirmed — generation should be allowed right now
    require_gatekeeper_confirmation(db_session, "RPT-504")

    # Simulate a DIFFERENT file landing on the same report_id.
    modified_path = tmp_path / "different.docx"
    modified_path.write_bytes((FIXTURES / "sample_rdd.docx").read_bytes())
    parsed2 = parse_document(modified_path)
    persist_parsed_document(
        db_session, report_id="RPT-504", cr_id="CR-504", filename="different.docx",
        file_path=modified_path, file_type="docx",
        uploaded_by="jane.tester", parsed=parsed2,
    )

    # Confirmation must now be invalid — re-confirmation required.
    with pytest.raises(GatekeeperBlockedError):
        require_gatekeeper_confirmation(db_session, "RPT-504")

    summary = get_scope_summary(db_session, "RPT-504")
    assert summary["is_confirmed"] is False
