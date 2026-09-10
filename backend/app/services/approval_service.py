"""
Access Request & Approval Workflow Service.

Enforces:
- New registrations start in PENDING status.
- Standard Admin can approve both Tester and Admin requests.
- Admin can approve Tester requests only (CANNOT approve or create another Admin).
- Users cannot approve their own access request (no self-approval).
- Mandatory approval reasons, atomic transactions, and audit history.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from app.core.rbac import CurrentUser
from app.models.rbac import AccessRequest, ApprovalHistory
from app.models.user import User
from app.models.audit import AuditLogEntry
from app.services.session_service import revoke_all_user_sessions


class ApprovalError(Exception):
    """Raised for business logic / authorization violations in approval workflows."""


def submit_access_request(
    db: Session,
    user_id: int,
    requested_role: str,
    reason: str,
) -> AccessRequest:
    """Submits a new role access request for a user."""
    requested_role = requested_role.lower().strip()
    if requested_role not in ("tester", "admin"):
        raise ApprovalError("Requested role must be either 'tester' or 'admin'.")

    if not reason or len(reason.strip()) < 5:
        raise ApprovalError("Please provide a clear justification reason (minimum 5 characters).")

    # Check for existing pending request
    existing = (
        db.query(AccessRequest)
        .filter(AccessRequest.user_id == user_id, AccessRequest.status == "PENDING")
        .first()
    )
    if existing:
        raise ApprovalError("You already have a pending access request under review.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ApprovalError("User account not found.")

    now = datetime.now(timezone.utc)
    req = AccessRequest(
        user_id=user_id,
        requested_role=requested_role,
        status="PENDING",
        request_reason=reason.strip(),
        created_at=now,
    )
    db.add(req)
    db.flush()

    # Record in approval history
    history = ApprovalHistory(
        request_id=req.id,
        target_user_id=user_id,
        actor_id=user_id,
        action="REQUESTED",
        previous_role=user.role,
        new_role=requested_role,
        previous_status=user.status,
        new_status="PENDING",
        reason=reason.strip(),
        created_at=now,
    )
    db.add(history)

    # Record in audit log
    db.add(AuditLogEntry(
        user_id=user.username,
        event_type="ACCESS_REQUESTED",
        detail=json.dumps({
            "requested_role": requested_role,
            "reason": reason.strip(),
            "request_id": req.id,
        }),
    ))

    db.commit()
    db.refresh(req)
    return req


def get_pending_requests(db: Session, caller: CurrentUser) -> List[Dict[str, Any]]:
    """
    Returns pending access requests.
    - Standard Admin sees all requests (tester and admin).
    - Regular Admin sees ONLY tester requests.
    """
    query = db.query(AccessRequest).filter(AccessRequest.status == "PENDING")
    if not caller.is_standard_admin:
        # Regular admin is restricted to tester requests only
        query = query.filter(AccessRequest.requested_role == "tester")

    requests = query.order_by(AccessRequest.created_at.asc()).all()
    out = []
    for r in requests:
        out.append({
            "id": r.id,
            "user_id": r.user_id,
            "username": r.user.username if r.user else "Unknown",
            "requested_role": r.requested_role,
            "status": r.status,
            "request_reason": r.request_reason,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out


def get_approval_history(db: Session, caller: CurrentUser, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Returns approval decision history.
    - Standard Admin sees all decisions (tester and admin).
    - Regular Admin sees tester decisions only.
    """
    query = db.query(ApprovalHistory).order_by(ApprovalHistory.created_at.desc())
    if not caller.is_standard_admin:
        query = query.filter((ApprovalHistory.new_role == "tester") | (ApprovalHistory.previous_role == "tester"))

    history_records = query.limit(limit).all()
    out = []
    for h in history_records:
        reviewer_name = h.actor.username if h.actor else "SYSTEM"
        target_name = h.target_user.username if h.target_user else "Unknown"
        out.append({
            "id": h.id,
            "request_id": h.request_id,
            "username": target_name,
            "requested_role": h.new_role or h.previous_role or "tester",
            "decision": h.action,  # APPROVED | REJECTED | REQUESTED | etc.
            "reviewer_username": reviewer_name,
            "reason": h.reason or "No justification provided",
            "previous_status": h.previous_status,
            "new_status": h.new_status,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        })
    return out


def get_all_requests(db: Session, caller: CurrentUser, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Returns all access requests (PENDING, APPROVED, REJECTED).
    - Standard Admin sees all requests.
    - Regular Admin sees tester requests only.
    """
    query = db.query(AccessRequest)
    if status and status.upper() != "ALL":
        query = query.filter(AccessRequest.status == status.upper())
    if not caller.is_standard_admin:
        query = query.filter(AccessRequest.requested_role == "tester")

    requests = query.order_by(AccessRequest.created_at.desc()).limit(limit).all()
    out = []
    for r in requests:
        out.append({
            "id": r.id,
            "user_id": r.user_id,
            "username": r.user.username if r.user else "Unknown",
            "requested_role": r.requested_role,
            "status": r.status,
            "request_reason": r.request_reason,
            "reviewer_username": r.reviewer.username if r.reviewer else None,
            "review_reason": r.review_reason,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out


def approve_access_request(
    db: Session,
    request_id: int,
    reviewer: CurrentUser,
    reason: str,
) -> AccessRequest:
    """
    Approves an access request with strict role-level guards.
    - Admin cannot approve another Admin (only Standard Admin can).
    - Self-approval is strictly forbidden.
    - Mandatory approval reason required.
    """
    if not reason or len(reason.strip()) < 3:
        raise ApprovalError("An approval reason is required (minimum 3 characters).")

    req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not req:
        raise ApprovalError("Access request not found.")

    if req.status != "PENDING":
        raise ApprovalError(f"Request is already resolved (status: {req.status}).")

    # Anti-self-approval rule
    if reviewer.id == req.user_id or reviewer.username == (req.user.username if req.user else ""):
        raise ApprovalError("Self-approval is strictly forbidden. Another administrator must review this request.")

    # Privilege hierarchy enforcement: Admin CANNOT approve Admin
    if req.requested_role == "admin" and not reviewer.is_standard_admin:
        raise ApprovalError("Admin access requests can be approved exclusively by the Standard Administrator.")

    target_user = db.query(User).filter(User.id == req.user_id).first()
    if not target_user:
        raise ApprovalError("Target user not found.")

    now = datetime.now(timezone.utc)
    old_role = target_user.role
    old_status = target_user.status

    # Apply approved role and activate account
    req.status = "APPROVED"
    req.reviewer_id = reviewer.id
    req.review_reason = reason.strip()
    req.reviewed_at = now

    target_user.role = req.requested_role
    target_user.status = "ACTIVE"
    target_user.is_active = True

    # Record history
    history = ApprovalHistory(
        request_id=req.id,
        target_user_id=target_user.id,
        actor_id=reviewer.id,
        action="APPROVED",
        previous_role=old_role,
        new_role=req.requested_role,
        previous_status=old_status,
        new_status="ACTIVE",
        reason=reason.strip(),
        created_at=now,
    )
    db.add(history)

    # Record audit log
    db.add(AuditLogEntry(
        user_id=reviewer.username,
        event_type="ACCESS_REQUEST_APPROVED",
        detail=json.dumps({
            "target_user": target_user.username,
            "approved_role": req.requested_role,
            "reviewer": reviewer.username,
            "reason": reason.strip(),
            "request_id": req.id,
        }),
    ))

    # Revoke any pre-existing sessions to force refresh with new role
    revoke_all_user_sessions(db, target_user.id, reason="ROLE_CHANGE")

    db.commit()
    db.refresh(req)
    return req


def reject_access_request(
    db: Session,
    request_id: int,
    reviewer: CurrentUser,
    reason: str,
) -> AccessRequest:
    """Rejects an access request with mandatory reason and audit logging."""
    if not reason or len(reason.strip()) < 3:
        raise ApprovalError("A rejection reason is required (minimum 3 characters).")

    req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not req:
        raise ApprovalError("Access request not found.")

    if req.status != "PENDING":
        raise ApprovalError(f"Request is already resolved (status: {req.status}).")

    if reviewer.id == req.user_id or reviewer.username == (req.user.username if req.user else ""):
        raise ApprovalError("Self-rejection is invalid.")

    if req.requested_role == "admin" and not reviewer.is_standard_admin:
        raise ApprovalError("Admin requests can be reviewed exclusively by the Standard Administrator.")

    target_user = db.query(User).filter(User.id == req.user_id).first()
    if not target_user:
        raise ApprovalError("Target user not found.")

    now = datetime.now(timezone.utc)
    old_role = target_user.role
    old_status = target_user.status

    req.status = "REJECTED"
    req.reviewer_id = reviewer.id
    req.review_reason = reason.strip()
    req.reviewed_at = now

    target_user.status = "REJECTED"

    history = ApprovalHistory(
        request_id=req.id,
        target_user_id=target_user.id,
        actor_id=reviewer.id,
        action="REJECTED",
        previous_role=old_role,
        new_role=old_role,
        previous_status=old_status,
        new_status="REJECTED",
        reason=reason.strip(),
        created_at=now,
    )
    db.add(history)

    db.add(AuditLogEntry(
        user_id=reviewer.username,
        event_type="ACCESS_REQUEST_REJECTED",
        detail=json.dumps({
            "target_user": target_user.username,
            "rejected_role": req.requested_role,
            "reviewer": reviewer.username,
            "reason": reason.strip(),
            "request_id": req.id,
        }),
    ))

    db.commit()
    db.refresh(req)
    return req
