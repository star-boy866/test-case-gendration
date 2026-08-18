"""
Tests for app.services.semantic_cache — the DB-persisted half of the
Local Semantic Cache Layer.

Note: the underlying decision logic (cache_classification.py) and the
vector search (vector_index.py) are already covered by their own
DB-independent test files and were run for real in the sandbox that built
this. These tests exercise the persistence/integration layer on top —
SemanticCacheEntry storage, report_id + source_file_hash scoping, and
cache-busting — which requires sqlalchemy.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models import audit, knowledge_base as kb_models, cache as cache_models  # noqa: F401
from app.services.semantic_cache import check_cache, store_result, invalidate_cache_for_report

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


SAMPLE_SCENARIOS = [
    {
        "sl_no": 1,
        "test_scenario": "Validate swipe card indicator is Y or N",
        "detailed_test_steps": "1. Query MEMBERS.SWIPE_CARD_IND.",
        "expected_results": "Value is Y or N, never null.",
        "verification_sql": "SELECT SWIPE_CARD_IND FROM MEMBERS WHERE SWIPE_CARD_IND NOT IN ('Y','N') OR SWIPE_CARD_IND IS NULL;",
    }
]


def test_check_cache_on_empty_cache_is_a_miss(db_session):
    result = check_cache(
        db_session, report_id="RPT-1", source_file_hash="hash-a",
        prompt_text="validate swipe card indicator",
    )
    assert result["status"] == "miss"
    assert result["cached_entry"] is None


def test_store_then_check_identical_prompt_is_a_hit(db_session):
    store_result(
        db_session, report_id="RPT-1", source_file_hash="hash-a",
        prompt_text="validate swipe card indicator is Y or N",
        scenarios=SAMPLE_SCENARIOS,
    )
    result = check_cache(
        db_session, report_id="RPT-1", source_file_hash="hash-a",
        prompt_text="validate swipe card indicator is Y or N",
    )
    assert result["status"] == "hit"
    assert result["cached_entry"]["cached_payload"] == SAMPLE_SCENARIOS


def test_cache_scoped_to_source_file_hash(db_session):
    # Cached under hash-a; querying under hash-b (a re-uploaded/changed
    # file) must NOT return it, even with an identical prompt — this is
    # the belt-and-suspenders half of cache-busting described in
    # semantic_cache.py's docstring.
    store_result(
        db_session, report_id="RPT-1", source_file_hash="hash-a",
        prompt_text="validate swipe card indicator is Y or N",
        scenarios=SAMPLE_SCENARIOS,
    )
    result = check_cache(
        db_session, report_id="RPT-1", source_file_hash="hash-b",
        prompt_text="validate swipe card indicator is Y or N",
    )
    assert result["status"] == "miss"


def test_cache_scoped_to_report_id(db_session):
    store_result(
        db_session, report_id="RPT-1", source_file_hash="hash-a",
        prompt_text="validate swipe card indicator is Y or N",
        scenarios=SAMPLE_SCENARIOS,
    )
    result = check_cache(
        db_session, report_id="RPT-2", source_file_hash="hash-a",
        prompt_text="validate swipe card indicator is Y or N",
    )
    assert result["status"] == "miss"


def test_invalidate_cache_for_report_removes_all_entries(db_session):
    store_result(
        db_session, report_id="RPT-1", source_file_hash="hash-a",
        prompt_text="prompt one", scenarios=SAMPLE_SCENARIOS,
    )
    store_result(
        db_session, report_id="RPT-1", source_file_hash="hash-a",
        prompt_text="prompt two", scenarios=SAMPLE_SCENARIOS,
    )
    removed = invalidate_cache_for_report(db_session, "RPT-1")
    assert removed == 2

    result = check_cache(
        db_session, report_id="RPT-1", source_file_hash="hash-a",
        prompt_text="prompt one",
    )
    assert result["status"] == "miss"


def test_dissimilar_prompt_is_a_miss_not_a_hit(db_session):
    store_result(
        db_session, report_id="RPT-1", source_file_hash="hash-a",
        prompt_text="validate swipe card indicator is Y or N",
        scenarios=SAMPLE_SCENARIOS,
    )
    result = check_cache(
        db_session, report_id="RPT-1", source_file_hash="hash-a",
        prompt_text="completely unrelated golf scoring logic",
    )
    assert result["status"] == "miss"
