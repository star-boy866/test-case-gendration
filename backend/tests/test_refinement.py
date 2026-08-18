"""
Tests for app.services.refinement.

Uses an in-memory SQLite DB per test, same pattern as test_knowledge_base.py
and test_gatekeeper.py.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models import audit, knowledge_base as kb_models, cache as cache_models, refinement as refinement_models  # noqa: F401
from app.models.audit import Session as SessionModel, AuditLogEntry
from app.services.refinement import (
    add_generated_rows,
    add_manual_row,
    get_grid,
    update_row,
    delete_row,
    RefinementError,
)

SAMPLE_SCENARIOS = [
    {
        "sl_no": 1,
        "test_scenario": "Validate SWIPE_CARD_IND values",
        "detailed_test_steps": "1. Query MEMBERS.",
        "expected_results": "Only Y or N present.",
        "verification_sql": "SELECT MEMBERS.SWIPE_CARD_IND FROM MEMBERS;",
        "category": "valid_value_check",
    },
    {
        "sl_no": 2,
        "test_scenario": "Validate MEMBER_ID not null",
        "detailed_test_steps": "1. Query MEMBERS.",
        "expected_results": "No nulls.",
        "verification_sql": "SELECT MEMBERS.MEMBER_ID FROM MEMBERS WHERE MEMBERS.MEMBER_ID IS NULL;",
        "category": "null_check",
    },
]


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def session_id(db_session):
    s = SessionModel(user_id="tester", report_id="RPT-1", status="gatekeeper_confirmed")
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s.id


def test_add_generated_rows_and_view_grid(db_session, session_id):
    add_generated_rows(
        db_session, session_id=session_id, report_id="RPT-1",
        requirement_text="validate members table", scenarios=SAMPLE_SCENARIOS,
    )
    grid = get_grid(db_session, session_id)
    assert len(grid) == 2
    assert grid[0]["sl_no"] == 1
    assert grid[0]["source"] == "ai_generated"
    assert grid[0]["is_edited"] is False


def test_multiple_generation_runs_accumulate_not_replace(db_session, session_id):
    add_generated_rows(db_session, session_id=session_id, report_id="RPT-1", requirement_text="req A", scenarios=SAMPLE_SCENARIOS[:1])
    add_generated_rows(db_session, session_id=session_id, report_id="RPT-1", requirement_text="req B", scenarios=SAMPLE_SCENARIOS[1:])
    grid = get_grid(db_session, session_id)
    assert len(grid) == 2
    assert grid[0]["requirement_text"] == "req A"
    assert grid[1]["requirement_text"] == "req B"


def test_manual_row_requires_all_fields(db_session, session_id):
    with pytest.raises(RefinementError):
        add_manual_row(
            db_session, session_id=session_id, report_id="RPT-1",
            fields={"test_scenario": "Only title, missing other fields"},
            added_by="tester",
        )


def test_manual_row_added_and_logged(db_session, session_id):
    row = add_manual_row(
        db_session, session_id=session_id, report_id="RPT-1",
        fields={
            "test_scenario": "Manual edge case", "detailed_test_steps": "1. Do X.",
            "expected_results": "Y happens.", "verification_sql": "SELECT 1;",
        },
        added_by="jane.tester",
    )
    grid = get_grid(db_session, session_id)
    assert any(r["row_id"] == row.id and r["source"] == "manual" for r in grid)

    logs = db_session.query(AuditLogEntry).filter(AuditLogEntry.event_type == "MANUAL_SCENARIO_ADDED").all()
    assert len(logs) == 1
    assert logs[0].user_id == "jane.tester"


def test_edit_row_diffs_against_current_value_and_logs_override(db_session, session_id):
    rows = add_generated_rows(
        db_session, session_id=session_id, report_id="RPT-1",
        requirement_text="req", scenarios=SAMPLE_SCENARIOS[:1],
    )
    row_id = rows[0].id

    result = update_row(
        db_session, session_id=session_id, row_id=row_id,
        fields={"test_scenario": "Edited title"}, edited_by="jane.tester",
    )
    assert result["changed_fields"] == ["test_scenario"]
    assert result["source"] == "ai_generated_edited"

    grid = get_grid(db_session, session_id)
    edited = next(r for r in grid if r["row_id"] == row_id)
    assert edited["test_scenario"] == "Edited title"
    assert edited["is_edited"] is True

    logs = db_session.query(AuditLogEntry).filter(AuditLogEntry.event_type == "HUMAN_OVERRIDE").all()
    assert len(logs) == 1
    detail = json.loads(logs[0].detail)
    assert detail["field"] == "test_scenario"
    assert detail["old_value"] == SAMPLE_SCENARIOS[0]["test_scenario"]
    assert detail["new_value"] == "Edited title"
    assert detail["original_ai_value"] == SAMPLE_SCENARIOS[0]["test_scenario"]


def test_editing_to_the_same_value_logs_nothing(db_session, session_id):
    rows = add_generated_rows(
        db_session, session_id=session_id, report_id="RPT-1",
        requirement_text="req", scenarios=SAMPLE_SCENARIOS[:1],
    )
    row_id = rows[0].id

    result = update_row(
        db_session, session_id=session_id, row_id=row_id,
        fields={"test_scenario": SAMPLE_SCENARIOS[0]["test_scenario"]},  # identical value
        edited_by="jane.tester",
    )
    assert result["changed_fields"] == []
    assert result["source"] == "ai_generated"  # unchanged, not promoted to edited

    logs = db_session.query(AuditLogEntry).filter(AuditLogEntry.event_type == "HUMAN_OVERRIDE").all()
    assert len(logs) == 0


def test_second_edit_diffs_against_current_not_frozen_original(db_session, session_id):
    rows = add_generated_rows(
        db_session, session_id=session_id, report_id="RPT-1",
        requirement_text="req", scenarios=SAMPLE_SCENARIOS[:1],
    )
    row_id = rows[0].id

    update_row(db_session, session_id=session_id, row_id=row_id, fields={"test_scenario": "First edit"}, edited_by="jane")
    result2 = update_row(db_session, session_id=session_id, row_id=row_id, fields={"test_scenario": "Second edit"}, edited_by="jane")

    assert result2["changed_fields"] == ["test_scenario"]

    logs = db_session.query(AuditLogEntry).filter(AuditLogEntry.event_type == "HUMAN_OVERRIDE").order_by(AuditLogEntry.id).all()
    assert len(logs) == 2
    second_detail = json.loads(logs[1].detail)
    assert second_detail["old_value"] == "First edit"  # diffed against current, not original
    assert second_detail["new_value"] == "Second edit"
    assert second_detail["original_ai_value"] == SAMPLE_SCENARIOS[0]["test_scenario"]  # snapshot stays frozen


def test_delete_row_removes_and_logs(db_session, session_id):
    rows = add_generated_rows(
        db_session, session_id=session_id, report_id="RPT-1",
        requirement_text="req", scenarios=SAMPLE_SCENARIOS,
    )
    delete_row(db_session, session_id=session_id, row_id=rows[0].id, removed_by="jane.tester")

    grid = get_grid(db_session, session_id)
    assert len(grid) == 1
    assert grid[0]["sl_no"] == 1  # renumbered after deletion

    logs = db_session.query(AuditLogEntry).filter(AuditLogEntry.event_type == "SCENARIO_REMOVED").all()
    assert len(logs) == 1


def test_edit_nonexistent_row_raises_refinement_error(db_session, session_id):
    with pytest.raises(RefinementError):
        update_row(db_session, session_id=session_id, row_id=99999, fields={"test_scenario": "x"}, edited_by="jane")


def test_edit_row_from_wrong_session_raises_refinement_error(db_session, session_id):
    other_session = SessionModel(user_id="other", report_id="RPT-2", status="gatekeeper_confirmed")
    db_session.add(other_session)
    db_session.commit()
    db_session.refresh(other_session)

    rows = add_generated_rows(
        db_session, session_id=session_id, report_id="RPT-1",
        requirement_text="req", scenarios=SAMPLE_SCENARIOS[:1],
    )
    with pytest.raises(RefinementError):
        update_row(db_session, session_id=other_session.id, row_id=rows[0].id, fields={"test_scenario": "x"}, edited_by="jane")
