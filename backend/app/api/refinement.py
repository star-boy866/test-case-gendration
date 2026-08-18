"""
Refinement endpoints — Phase 6 (Interactive Refinement Grid / HITL).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.rbac import require_role, CurrentUser
from app.services.refinement import (
    get_grid,
    add_manual_row,
    update_row,
    delete_row,
    RefinementError,
)

router = APIRouter(prefix="/api/refinement", tags=["refinement"])


class GridRow(BaseModel):
    row_id: int
    sl_no: int
    test_scenario: str
    detailed_test_steps: str
    expected_results: str
    verification_sql: str
    category: Optional[str] = None
    source: str
    requirement_text: Optional[str] = None
    is_edited: bool


class AddManualRowRequest(BaseModel):
    test_scenario: str
    detailed_test_steps: str
    expected_results: str
    verification_sql: str
    category: Optional[str] = None


class UpdateRowRequest(BaseModel):
    test_scenario: Optional[str] = None
    detailed_test_steps: Optional[str] = None
    expected_results: Optional[str] = None
    verification_sql: Optional[str] = None


class UpdateRowResponse(BaseModel):
    row_id: int
    changed_fields: List[str]
    source: str


@router.get("/{session_id}", response_model=List[GridRow])
def view_grid(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    return get_grid(db, session_id)


@router.post("/{session_id}/rows", response_model=GridRow)
def add_row(
    session_id: int,
    payload: AddManualRowRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    # report_id isn't in the request body — every row already belongs to a
    # session, and sessions are always scoped to one report_id, so we look
    # it up rather than trusting a client-supplied value that could drift.
    from app.models.audit import Session as SessionModel
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail=f"No session id={session_id}.")

    try:
        row = add_manual_row(
            db,
            session_id=session_id,
            report_id=session.report_id,
            fields=payload.model_dump(),
            added_by=current_user.username,
        )
    except RefinementError as e:
        raise HTTPException(status_code=400, detail=str(e))

    grid = get_grid(db, session_id)
    return next(r for r in grid if r["row_id"] == row.id)


@router.patch("/{session_id}/rows/{row_id}", response_model=UpdateRowResponse)
def edit_row(
    session_id: int,
    row_id: int,
    payload: UpdateRowRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    fields = payload.model_dump(exclude_none=True)
    try:
        result = update_row(
            db, session_id=session_id, row_id=row_id,
            fields=fields, edited_by=current_user.username,
        )
    except RefinementError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.delete("/{session_id}/rows/{row_id}")
def remove_row(
    session_id: int,
    row_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    try:
        delete_row(db, session_id=session_id, row_id=row_id, removed_by=current_user.username)
    except RefinementError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"deleted": row_id}
