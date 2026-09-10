"""
Administrative Role-Based Access Control (RBAC) Endpoints.

Enforces:
- Standard Admin vs Admin permission boundaries.
- Admin cannot approve or create other Admins.
- Standard Admin account is strictly protected from modification, deletion, or downgrade.
- Mandatory reasons for approvals, rejections, status changes, and role assignments.
- Re-authentication requirement for high-privilege operations.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.rbac import (
    require_role,
    require_standard_admin,
    require_recent_auth,
    CurrentUser,
)
from app.core.immutable_audit import verify_audit_chain
from app.db.session import get_db
from app.models.user import User
from app.models.audit import AuditLogEntry
from app.services.approval_service import (
    get_pending_requests,
    get_approval_history,
    get_all_requests,
    submit_access_request,
    approve_access_request,
    reject_access_request,
    ApprovalError,
)
from app.services.user_service import (
    update_user_status,
    update_user_role,
    UserError,
)
from app.services.session_service import (
    list_user_sessions,
    revoke_all_user_sessions,
)

router = APIRouter(prefix="/api/admin", tags=["admin_rbac"])


class ApprovalActionRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Reason must be at least 3 characters.")
        return v


class UpdateStatusRequest(BaseModel):
    status: str  # ACTIVE | SUSPENDED | REVOKED
    reason: str


class UpdateRoleRequest(BaseModel):
    role: str  # tester | admin | approver
    reason: str


class CreateUserAdminRequest(BaseModel):
    username: str
    password: str
    role: str = "tester"  # tester | admin


# ─── ACCESS REQUEST APPROVALS ────────────────────────────────────────────────

@router.get("/approvals")
def list_approvals(
    status: Optional[str] = Query(None, description="Optional filter: ALL | PENDING | APPROVED | REJECTED"),
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Lists pending access requests, decision history, and all requests.
    - Standard Admin sees all requests (Tester and Admin).
    - Regular Admin sees Tester requests ONLY (cannot see or approve Admin requests).
    """
    pending = get_pending_requests(db, current_user)
    history = get_approval_history(db, current_user)
    all_reqs = get_all_requests(db, current_user, status=status)
    return {
        "pending_requests": pending,
        "history": history,
        "all_requests": all_reqs,
        "total_pending": len(pending),
        "total_history": len(history),
    }


@router.post("/approvals/demo-seed")
def seed_demo_request(
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Creates a sample access request to test the approval pipeline."""
    from app.core.security import hash_password
    import time
    timestamp = int(time.time()) % 10000
    candidate_username = f"analyst_qa_{timestamp}"
    new_user = User(
        username=candidate_username,
        hashed_password=hash_password("Analyst#Pass2026!"),
        role="pending",
        status="PENDING",
        is_active=True,
        must_change_password=False,
        mfa_enabled=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    req = submit_access_request(
        db=db,
        user_id=cast(int, new_user.id),
        requested_role="tester",
        reason="Healthcare QA analyst requesting access to generate and review MMIS test scenarios.",
    )
    return {
        "status": "SUCCESS",
        "message": f"Demo access request created for '{candidate_username}'.",
        "request_id": req.id,
        "username": candidate_username,
    }


@router.post("/approvals/{request_id}/approve")
def approve_request(
    request_id: int,
    payload: ApprovalActionRequest,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Approves an access request:
    - Tester requests can be approved by Standard Admin or Admin.
    - Admin requests can be approved EXCLUSIVELY by Standard Admin.
    - Self-approval is strictly forbidden.
    """
    try:
        req = approve_access_request(
            db=db,
            request_id=request_id,
            reviewer=current_user,
            reason=payload.reason,
        )
        return {
            "status": "SUCCESS",
            "message": f"Approved access for '{req.user.username}' as '{req.requested_role}'.",
            "request_id": req.id,
            "approved_role": req.requested_role,
        }
    except ApprovalError as ae:
        status_code = 403 if "exclusively" in str(ae) or "forbidden" in str(ae).lower() or "cannot approve" in str(ae).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(ae))


@router.post("/approvals/{request_id}/reject")
def reject_request(
    request_id: int,
    payload: ApprovalActionRequest,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Rejects an access request with mandatory justification reason."""
    try:
        req = reject_access_request(
            db=db,
            request_id=request_id,
            reviewer=current_user,
            reason=payload.reason,
        )
        return {
            "status": "SUCCESS",
            "message": f"Rejected access request for '{req.user.username}'.",
            "request_id": req.id,
        }
    except ApprovalError as ae:
        status_code = 403 if "exclusively" in str(ae) or "forbidden" in str(ae).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(ae))


# ─── USER AND ROLE MANAGEMENT ───────────────────────────────────────────────

@router.get("/users")
def list_all_users(
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Lists all user accounts with roles, account status, and MFA indicators."""
    users = db.query(User).order_by(User.id.asc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "status": u.status,
            "is_active": u.is_active,
            "must_change_password": u.must_change_password,
            "mfa_enabled": u.mfa_enabled,
            "failed_login_attempts": u.failed_login_attempts,
            "is_locked": bool(u.locked_until),
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "is_standard_admin": (u.role == "standard_admin"),
            "can_modify": current_user.is_standard_admin or (u.role not in ("admin", "standard_admin")),
        }
        for u in users
    ]


@router.post("/users")
def create_user_admin(
    payload: CreateUserAdminRequest,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Provisions a new user account with role boundaries."""
    from app.core.security import hash_password, validate_password_strength
    from datetime import datetime, timezone
    import json

    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")

    role = payload.role.lower().strip()
    if role not in ("tester", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'tester' or 'admin'.")

    if role == "admin" and not current_user.is_standard_admin:
        raise HTTPException(status_code=403, detail="Admin accounts can be created exclusively by the Standard Administrator.")

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Username '{username}' already exists.")

    is_strong, err_msg = validate_password_strength(payload.password, username)
    if not is_strong:
        raise HTTPException(status_code=400, detail=err_msg)

    now = datetime.now(timezone.utc)
    new_user = User(
        username=username,
        hashed_password=hash_password(payload.password),
        role=role,
        status="ACTIVE",
        is_active=True,
        must_change_password=True,
        mfa_enabled=False,
        created_at=now,
    )
    db.add(new_user)
    db.flush()

    db.add(AuditLogEntry(
        user_id=current_user.username,
        event_type="USER_CREATED",
        detail=json.dumps({
            "created_user": username,
            "assigned_role": role,
            "creator": current_user.username,
        }),
    ))
    db.commit()
    db.refresh(new_user)

    return {
        "status": "SUCCESS",
        "message": f"User '{username}' created successfully.",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "role": new_user.role,
            "status": new_user.status,
            "created_at": new_user.created_at.isoformat(),
        },
    }


@router.patch("/users/{user_id}/status")
def change_user_status(
    user_id: int,
    payload: UpdateStatusRequest,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Activates, suspends, or revokes a user account:
    - Standard Admin cannot be suspended or revoked.
    - Regular Admin cannot suspend or revoke other Admins.
    """
    try:
        updated = update_user_status(
            db=db,
            target_user_id=user_id,
            new_status=payload.status,
            actor=current_user,
            reason=payload.reason,
        )
        return {
            "status": "SUCCESS",
            "message": f"Account '{updated.username}' status set to {updated.status}.",
            "user": {"id": updated.id, "username": updated.username, "status": updated.status},
        }
    except UserError as ue:
        status_code = 403 if "Standard Administrator" in str(ue) or "permission" in str(ue).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(ue))


@router.patch("/users/{user_id}/role")
def change_user_role(
    user_id: int,
    payload: UpdateRoleRequest,
    current_user: CurrentUser = Depends(require_standard_admin()),
    recent_check: CurrentUser = Depends(require_recent_auth(300)),
    db: Session = Depends(get_db),
):
    """
    Changes user role (Standard Admin exclusive).
    Requires recent authentication (within 5 minutes).
    Standard Admin account cannot be modified or downgraded.
    """
    try:
        updated = update_user_role(
            db=db,
            target_user_id=user_id,
            new_role=payload.role,
            actor=current_user,
            reason=payload.reason,
        )
        return {
            "status": "SUCCESS",
            "message": f"User '{updated.username}' role changed to '{updated.role}'.",
            "user": {"id": updated.id, "username": updated.username, "role": updated.role},
        }
    except UserError as ue:
        status_code = 403 if "Standard Administrator" in str(ue) or "permission" in str(ue).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(ue))


@router.get("/users/{user_id}/sessions")
def get_user_sessions_admin(
    user_id: int,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Inspects active sessions and devices for a given user."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    return {
        "username": target.username,
        "sessions": list_user_sessions(db, user_id),
    }


@router.post("/users/{user_id}/terminate-sessions")
def terminate_user_sessions(
    user_id: int,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Administratively terminates all active sessions for a user."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    if target.role == "standard_admin" and not current_user.is_standard_admin:
        raise HTTPException(status_code=403, detail="Cannot terminate Standard Admin sessions.")

    count = revoke_all_user_sessions(db, user_id, reason="ADMIN_TERMINATION")
    return {"status": "SUCCESS", "terminated_count": count}


# ─── AUDIT LOG VIEWER & MONITORING ──────────────────────────────────────────

@router.get("/audit-log")
@router.get("/audit-logs")
def get_admin_audit_log(
    limit: int = Query(100, ge=1, le=1000),
    page: int = Query(1, ge=1),
    page_size: Optional[int] = Query(None),
    event_type: Optional[str] = None,
    action: Optional[str] = None,
    actor: Optional[str] = None,
    target_user: Optional[str] = None,
    outcome: Optional[str] = None,
    user_id: Optional[str] = None,
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Searchable, append-only security audit log viewer.
    Restricted to authorized administrators.
    """
    query = db.query(AuditLogEntry)
    target_type = event_type or action
    if target_type:
        query = query.filter(AuditLogEntry.event_type.ilike(f"%{target_type.strip()}%"))
    target_u = user_id or actor or target_user
    if target_u:
        query = query.filter(AuditLogEntry.user_id.ilike(f"%{target_u.strip()}%"))

    total = query.count()
    actual_limit = page_size if page_size else limit
    offset = (page - 1) * actual_limit if page_size else 0
    rows = query.order_by(AuditLogEntry.id.desc()).offset(offset).limit(actual_limit).all()

    # Calculate summary security alerts
    failed_logins_count = db.query(AuditLogEntry).filter(AuditLogEntry.event_type == "LOGIN_FAILED").count()
    lockouts_count = db.query(AuditLogEntry).filter(AuditLogEntry.event_type == "ACCOUNT_LOCKED").count()

    formatted_records = [
        {
            "id": r.id,
            "created_at": r.timestamp.isoformat() if r.timestamp else None,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "actor_username": r.user_id,
            "user_id": r.user_id,
            "target_username": None,
            "session_id": r.session_id,
            "action": r.event_type,
            "event_type": r.event_type,
            "outcome": "FAILURE" if "FAIL" in (r.event_type or "") or "LOCK" in (r.event_type or "") else "SUCCESS",
            "details": r.detail,
            "detail": r.detail,
            "file_sha256": r.file_sha256,
            "chain_hash": r.chain_hash,
            "ip_address": "127.0.0.1",
        }
        for r in rows
    ]

    return {
        "total": total,
        "page": page,
        "page_size": actual_limit,
        "alerts_summary": {
            "failed_logins": failed_logins_count,
            "account_lockouts": lockouts_count,
        },
        "records": formatted_records,
        "logs": formatted_records,
    }


@router.get("/audit-log/verify")
def verify_audit_log(
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Validates the tamper-evident cryptographic hash chain of the audit log."""
    is_intact, problems = verify_audit_chain(db)
    return {"is_intact": is_intact, "problems": problems}


# ─── TEST CASES FILE ASSIGNMENT & GOVERNANCE ───────────────────────────────

class CreateAssignmentRequest(BaseModel):
    run_id: int
    user_id: int
    notes: Optional[str] = None


class RevokeAssignmentRequest(BaseModel):
    reason: Optional[str] = None


@router.get("/assignments")
def get_all_assignments(
    current_user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Overview of all Test Cases generation runs and their active assignments.
    Accessible to authorized administrators.
    """
    from app.services.assignment_service import list_all_assignments
    return list_all_assignments(db)


@router.post("/assignments")
def create_test_case_assignment(
    payload: CreateAssignmentRequest,
    current_user: CurrentUser = Depends(require_standard_admin()),
    db: Session = Depends(get_db),
):
    """
    Assigns a Test Cases file / run to a tester.
    Restricted exclusively to the Standard Administrator.
    Revokes the target user's active sessions immediately so permissions update.
    """
    from app.services.assignment_service import assign_test_case_file, AssignmentError
    try:
        assignment = assign_test_case_file(
            db=db,
            run_id=payload.run_id,
            user_id=payload.user_id,
            actor=current_user,
            notes=payload.notes,
        )
        return {
            "status": "SUCCESS",
            "message": f"Assigned test case file to user ID {payload.user_id}.",
            "assignment": {
                "id": assignment.id,
                "file_id": assignment.file_id,
                "run_id": assignment.run_id,
                "user_id": assignment.user_id,
                "status": assignment.status,
            },
        }
    except AssignmentError as ae:
        raise HTTPException(status_code=400, detail=str(ae))


@router.post("/assignments/{assignment_id}/revoke")
@router.delete("/assignments/{assignment_id}")
def revoke_assignment_endpoint(
    assignment_id: int,
    payload: Optional[RevokeAssignmentRequest] = None,
    current_user: CurrentUser = Depends(require_standard_admin()),
    db: Session = Depends(get_db),
):
    """
    Revokes a tester's assignment to a Test Cases file.
    Restricted exclusively to the Standard Administrator.
    """
    from app.services.assignment_service import revoke_test_case_file, AssignmentError
    try:
        reason = payload.reason if payload else "Revoked by Standard Administrator"
        revoked = revoke_test_case_file(
            db=db,
            assignment_id=assignment_id,
            actor=current_user,
            reason=reason,
        )
        return {
            "status": "SUCCESS",
            "message": f"Assignment {assignment_id} revoked.",
            "assignment": {
                "id": revoked.id,
                "file_id": revoked.file_id,
                "status": revoked.status,
            },
        }
    except AssignmentError as ae:
        raise HTTPException(status_code=400, detail=str(ae))


@router.delete("/runs/{run_id}")
def delete_test_case_run_endpoint(
    run_id: int,
    reason: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(require_standard_admin()),
    db: Session = Depends(get_db),
):
    """
    Permanently deletes a Test Cases generation run and files.
    Restricted exclusively to the Standard Administrator.
    """
    from app.services.assignment_service import delete_test_case_run, AssignmentError
    try:
        delete_test_case_run(
            db=db,
            run_id=run_id,
            actor=current_user,
            reason=reason,
        )
        return {"status": "SUCCESS", "message": f"Test case run {run_id} and associated files deleted."}
    except AssignmentError as ae:
        raise HTTPException(status_code=400, detail=str(ae))
