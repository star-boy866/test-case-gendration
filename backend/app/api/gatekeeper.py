"""
Gatekeeper confirmation endpoints — Phase 2.

Implements the "strict blocking step": the UI must show CR ID, CR
Description, and Report ID (with real extracted scope counts) and require
explicit human confirmation before generation is allowed to run.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.rbac import require_role, get_current_user, CurrentUser
from app.services.gatekeeper import (
    get_scope_summary,
    confirm_scope,
    GatekeeperError,
)

router = APIRouter(prefix="/api/gatekeeper", tags=["gatekeeper"])


class ScopeSummaryResponse(BaseModel):
    report_id: str
    session_id: Optional[int] = None
    cr_id: Optional[str] = None
    cr_description: Optional[str] = None
    counts: dict
    source_documents: list
    is_confirmed: bool
    confirmed_at: Optional[str] = None
    confirmed_by: Optional[str] = None
    can_confirm: bool


class GatekeeperConfirmRequest(BaseModel):
    report_id: str
    cr_id: str
    cr_description: str


class GatekeeperConfirmResponse(BaseModel):
    session_id: int
    report_id: str
    cr_id: str
    cr_description: str
    confirmed_at: str
    confirmed_by: str


@router.get("/scope/{report_id}", response_model=ScopeSummaryResponse)
def scope_summary(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return get_scope_summary(db, report_id)


@router.post("/confirm", response_model=GatekeeperConfirmResponse)
def confirm(
    payload: GatekeeperConfirmRequest,
    db: Session = Depends(get_db),
    # Confirming scope is the human sign-off this whole step exists for —
    # per core/rbac.py's design, that requires 'approver' or higher, NOT
    # just whoever happens to be logged in as a 'tester'. Before this fix,
    # `confirmed_by` was a client-supplied free-text field with no
    # authentication behind it at all, which made the "approver as a
    # genuine second, higher-trust sign-off" security model fictional —
    # anyone could type any name into that field.
    current_user: CurrentUser = Depends(require_role("approver")),
):
    try:
        result = confirm_scope(
            db,
            report_id=payload.report_id,
            cr_id=payload.cr_id,
            cr_description=payload.cr_description,
            confirmed_by=current_user.username,
        )
    except GatekeeperError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result
