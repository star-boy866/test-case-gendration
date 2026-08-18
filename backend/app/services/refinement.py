"""
Refinement service — Phase 6 (Interactive Refinement Grid / HITL).

Backs the Step 3 UI: testers can edit any AI-generated scenario field,
append entirely manual scenarios, or remove rows, before final
serialization (Phase 7's Excel export).

Every edit to an AI-generated row is diffed against that row's frozen
`original_snapshot_json` (set once, at row creation, never touched again)
and logged as an immutable audit entry — one entry per changed field, not
a vague "row was edited" — per the Master System Prompt's requirement to
capture "explicit logs of any human overrides made during the interactive
UI refinement step."
"""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditLogEntry
from app.models.refinement import RefinementRow

EDITABLE_FIELDS = ("test_scenario", "detailed_test_steps", "expected_results", "verification_sql")


class RefinementError(Exception):
    """Raised for refinement operations on rows/sessions that don't exist or don't match."""


def add_generated_rows(
    db: Session,
    *,
    session_id: int,
    report_id: str,
    requirement_text: str,
    scenarios: list[dict],
) -> list[RefinementRow]:
    """
    Appends a batch of freshly-generated scenarios (already TestScenario-
    shaped dicts, i.e. have sl_no/test_scenario/detailed_test_steps/
    expected_results/verification_sql) to a session's grid. Existing rows
    are untouched — a session accumulates scenarios across multiple
    generation runs for different requirements, rather than each run
    replacing the last.
    """
    current_max_order = (
        db.query(RefinementRow)
        .filter(RefinementRow.session_id == session_id)
        .count()
    )

    rows = []
    for i, s in enumerate(scenarios):
        snapshot = {f: s.get(f, "") for f in EDITABLE_FIELDS}
        row = RefinementRow(
            session_id=session_id,
            report_id=report_id,
            requirement_text=requirement_text,
            test_scenario=snapshot["test_scenario"],
            detailed_test_steps=snapshot["detailed_test_steps"],
            expected_results=snapshot["expected_results"],
            verification_sql=snapshot["verification_sql"],
            category=s.get("category"),
            source="ai_generated",
            original_snapshot_json=json.dumps(snapshot),
            display_order=current_max_order + i,
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def add_manual_row(
    db: Session,
    *,
    session_id: int,
    report_id: str,
    fields: dict,
    added_by: str,
) -> RefinementRow:
    """A tester-authored scenario, not touched by AST validation — the
    human is directly accountable for what they type here, same as they
    would be hand-writing a test case with no tool at all."""
    missing = [f for f in EDITABLE_FIELDS if not str(fields.get(f, "")).strip()]
    if missing:
        raise RefinementError(f"Manual scenario missing required field(s): {missing}")

    current_max_order = (
        db.query(RefinementRow)
        .filter(RefinementRow.session_id == session_id)
        .count()
    )
    snapshot = {f: fields[f] for f in EDITABLE_FIELDS}

    row = RefinementRow(
        session_id=session_id,
        report_id=report_id,
        requirement_text=None,
        test_scenario=snapshot["test_scenario"],
        detailed_test_steps=snapshot["detailed_test_steps"],
        expected_results=snapshot["expected_results"],
        verification_sql=snapshot["verification_sql"],
        category=fields.get("category") or "manual",
        source="manual",
        original_snapshot_json=json.dumps(snapshot),
        display_order=current_max_order,
    )
    db.add(row)

    db.add(AuditLogEntry(
        user_id=added_by,
        session_id=session_id,
        event_type="MANUAL_SCENARIO_ADDED",
        detail=json.dumps({"row_fields": snapshot}),
    ))

    db.commit()
    db.refresh(row)
    return row


def get_grid(db: Session, session_id: int) -> list[dict]:
    rows = (
        db.query(RefinementRow)
        .filter(RefinementRow.session_id == session_id)
        .order_by(RefinementRow.display_order, RefinementRow.id)
        .all()
    )
    return [
        {
            "row_id": r.id,
            "sl_no": i + 1,
            "test_scenario": r.test_scenario,
            "detailed_test_steps": r.detailed_test_steps,
            "expected_results": r.expected_results,
            "verification_sql": r.verification_sql,
            "category": r.category,
            "source": r.source,
            "requirement_text": r.requirement_text,
            "is_edited": r.source == "ai_generated_edited",
        }
        for i, r in enumerate(rows)
    ]


def update_row(
    db: Session,
    *,
    session_id: int,
    row_id: int,
    fields: dict,
    edited_by: str,
) -> dict:
    """
    Applies edits to a row's editable fields. Diffs each incoming field
    against the row's CURRENT stored value (not the original snapshot —
    that stays frozen forever) and logs one audit entry per changed field,
    with old_value/new_value/original_value(from the frozen snapshot) all
    present, so the audit trail distinguishes "still matches the AI
    original" from "already edited once before, edited again."
    """
    row = (
        db.query(RefinementRow)
        .filter(RefinementRow.id == row_id, RefinementRow.session_id == session_id)
        .first()
    )
    if row is None:
        raise RefinementError(f"No refinement row id={row_id} in session {session_id}.")

    original_snapshot = json.loads(row.original_snapshot_json)
    changed_fields = []

    for field_name in EDITABLE_FIELDS:
        if field_name not in fields:
            continue
        new_value = fields[field_name]
        old_value = getattr(row, field_name)
        if new_value == old_value:
            continue

        changed_fields.append(field_name)
        setattr(row, field_name, new_value)

        db.add(AuditLogEntry(
            user_id=edited_by,
            session_id=session_id,
            event_type="HUMAN_OVERRIDE",
            detail=json.dumps({
                "row_id": row_id,
                "field": field_name,
                "old_value": old_value,
                "new_value": new_value,
                "original_ai_value": original_snapshot.get(field_name),
            }),
        ))

    if changed_fields and row.source == "ai_generated":
        row.source = "ai_generated_edited"

    db.commit()
    db.refresh(row)

    return {
        "row_id": row.id,
        "changed_fields": changed_fields,
        "source": row.source,
    }


def delete_row(db: Session, *, session_id: int, row_id: int, removed_by: str) -> None:
    row = (
        db.query(RefinementRow)
        .filter(RefinementRow.id == row_id, RefinementRow.session_id == session_id)
        .first()
    )
    if row is None:
        raise RefinementError(f"No refinement row id={row_id} in session {session_id}.")

    db.add(AuditLogEntry(
        user_id=removed_by,
        session_id=session_id,
        event_type="SCENARIO_REMOVED",
        detail=json.dumps({
            "row_id": row_id,
            "test_scenario": row.test_scenario,
            "source": row.source,
        }),
    ))
    db.delete(row)
    db.commit()
