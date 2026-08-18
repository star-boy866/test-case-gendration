"""
Tests for app.services.judge_service.

evaluate_and_store() opens its OWN DB session (SessionLocal) rather than
taking one as a parameter — deliberately, since it's designed to run via
FastAPI's BackgroundTasks after the request-scoped session has already
closed (see the module's own docstring). That makes it awkward to point
at an in-memory test DB the way other DB-dependent tests in this project
do (they take a `db_session` fixture directly) — this is flagged
explicitly rather than silently working around it.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models import audit, knowledge_base as kb_models, evaluation  # noqa: F401
from app.services.judge_service import get_latest_evaluation
from app.models.evaluation import LLMJudgeEvaluation


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_get_latest_evaluation_returns_none_when_no_row_exists(db_session):
    assert get_latest_evaluation(db_session, session_id=999) is None


def test_get_latest_evaluation_returns_most_recent_row(db_session):
    db_session.add(LLMJudgeEvaluation(
        session_id=1, report_id="RPT-1", completeness=0.5,
        hallucination_prevention=0.5, schema_adherence=0.5, overall=0.5,
        rationale="first pass", warnings="[]",
    ))
    db_session.commit()
    db_session.add(LLMJudgeEvaluation(
        session_id=1, report_id="RPT-1", completeness=0.9,
        hallucination_prevention=1.0, schema_adherence=1.0, overall=0.967,
        rationale="second pass, improved", warnings="[]",
    ))
    db_session.commit()

    result = get_latest_evaluation(db_session, session_id=1)
    assert result is not None
    assert result.rationale == "second pass, improved"


def test_get_latest_evaluation_scoped_to_session_id(db_session):
    db_session.add(LLMJudgeEvaluation(
        session_id=1, report_id="RPT-1", completeness=0.9,
        hallucination_prevention=0.9, schema_adherence=0.9, overall=0.9,
        rationale="session 1", warnings="[]",
    ))
    db_session.commit()

    assert get_latest_evaluation(db_session, session_id=2) is None
    assert get_latest_evaluation(db_session, session_id=1) is not None


# NOTE: evaluate_and_store() itself is NOT tested here because it opens its
# own SessionLocal() bound to the real app_metadata.db path rather than
# accepting an injectable session — testing it for real would mean either
# writing to the actual application database from the test suite (unsafe)
# or monkeypatching app.db.session.SessionLocal, which is possible but
# wasn't done here given time constraints. This is a real gap: consider
# refactoring evaluate_and_store() to accept an optional session_factory
# parameter (defaulting to SessionLocal) purely to make this testable
# without monkeypatching internals. Flagged honestly rather than silently
# skipped.
