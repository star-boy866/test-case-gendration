"""
Test Case Assignment and Authorization Security Service.

Implements:
- Standard Admin assignment, unassignment, and deletion of test case files.
- Role-scoped file query (Testers see only their assigned files; Admins see all).
- IDOR (Insecure Direct Object Reference) defense on file view and download operations.
- Immediate session revocation upon assignment changes.
- Security audit logging for assignments, unassignments, deletions, and access denials.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import CurrentUser
from app.models.audit import AuditLogEntry
from app.models.cognos_orm import CognosGenerationRun, CognosTestCaseModel
from app.models.rbac import TestCaseAssignment
from app.models.user import User
from app.services.session_service import revoke_all_user_sessions


class AssignmentError(Exception):
    """Business rule violation in test case assignment."""


def _is_standard_admin(actor: Any) -> bool:
    return getattr(actor, "is_standard_admin", False) or getattr(actor, "role", "") == "standard_admin"


def assign_test_case_file(
    db: Session,
    run_id: int,
    user_id: int,
    actor: CurrentUser,
    notes: Optional[str] = None,
) -> TestCaseAssignment:
    """
    Assigns a test case file / generation run to a tester.
    Restricted strictly to the Standard Administrator.
    """
    if not _is_standard_admin(actor):
        raise AssignmentError("Only the Standard Administrator can assign Test Cases files.")

    run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
    if not run:
        raise AssignmentError(f"Test case run {run_id} not found.")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise AssignmentError(f"User {user_id} not found.")

    if target_user.status != "ACTIVE":
        raise AssignmentError(f"Cannot assign files to account with status '{target_user.status}'.")

    # Check for existing assignment
    assignment = (
        db.query(TestCaseAssignment)
        .filter(TestCaseAssignment.run_id == run_id, TestCaseAssignment.user_id == user_id)
        .first()
    )

    now = datetime.now(timezone.utc)
    if assignment:
        assignment.status = "ASSIGNED"
        assignment.assigned_by_id = actor.id
        assignment.updated_at = now
        assignment.notes = notes or assignment.notes
    else:
        file_id = f"TCF-{uuid.uuid4().hex[:12].upper()}"
        assignment = TestCaseAssignment(
            file_id=file_id,
            run_id=run.id,
            user_id=target_user.id,
            assigned_by_id=actor.id,
            status="ASSIGNED",
            assigned_at=now,
            updated_at=now,
            notes=notes,
        )
        db.add(assignment)

    db.flush()

    # Revoke active sessions for target user so their assignment changes take effect immediately
    revoke_all_user_sessions(db, int(target_user.id), reason="FILE_ASSIGNMENT_UPDATED")

    # Audit log entry
    db.add(
        AuditLogEntry(
            user_id=actor.username,
            event_type="TEST_CASE_ASSIGNED",
            detail=json.dumps({
                "assignment_id": assignment.id,
                "file_id": assignment.file_id,
                "run_id": run.id,
                "target_user_id": target_user.id,
                "target_username": target_user.username,
                "assigned_by": actor.username,
                "notes": notes,
            }),
        )
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def revoke_test_case_file(
    db: Session,
    assignment_id: int,
    actor: CurrentUser,
    reason: Optional[str] = None,
) -> TestCaseAssignment:
    """
    Revokes a tester's assignment to a test case file.
    Restricted strictly to the Standard Administrator.
    """
    if not _is_standard_admin(actor):
        raise AssignmentError("Only the Standard Administrator can revoke Test Cases file assignments.")

    assignment = db.query(TestCaseAssignment).filter(TestCaseAssignment.id == assignment_id).first()
    if not assignment:
        raise AssignmentError(f"Assignment {assignment_id} not found.")

    assignment.status = "REVOKED"
    assignment.updated_at = datetime.now(timezone.utc)

    # Revoke target user's sessions immediately
    revoke_all_user_sessions(db, int(assignment.user_id), reason="FILE_ASSIGNMENT_REVOKED")

    db.add(
        AuditLogEntry(
            user_id=actor.username,
            event_type="TEST_CASE_UNASSIGNED",
            detail=json.dumps({
                "assignment_id": assignment.id,
                "file_id": assignment.file_id,
                "run_id": assignment.run_id,
                "user_id": assignment.user_id,
                "revoked_by": actor.username,
                "reason": reason or "Revoked by Standard Administrator",
            }),
        )
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def delete_test_case_run(
    db: Session,
    run_id: int,
    actor: CurrentUser,
    reason: Optional[str] = None,
) -> bool:
    """
    Permanently deletes a Test Cases generation run, assignments, and files.
    Restricted strictly to the Standard Administrator.
    """
    if not _is_standard_admin(actor):
        raise AssignmentError("Only the Standard Administrator can delete Test Cases files.")

    run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
    if not run:
        raise AssignmentError(f"Run {run_id} not found.")

    # Find affected users to revoke their sessions
    assignments = db.query(TestCaseAssignment).filter(TestCaseAssignment.run_id == run_id).all()
    affected_user_ids = {a.user_id for a in assignments}

    report_id = run.report_id
    run_id_val = run.id

    # Delete physical exported Excel file if present
    export_dir = Path(settings.EXPORT_DIR)
    excel_path = export_dir / f"Cognos_UT_{run.id}.xlsx"
    if excel_path.exists():
        try:
            excel_path.unlink()
        except Exception:
            pass

    # Delete assignments first
    db.query(TestCaseAssignment).filter(TestCaseAssignment.run_id == run_id).delete(synchronize_session=False)

    # Delete run (cascades to test cases, and requirements)
    db.delete(run)

    for uid in affected_user_ids:
        revoke_all_user_sessions(db, int(uid), reason="TEST_CASE_FILE_DELETED")

    db.add(
        AuditLogEntry(
            user_id=actor.username,
            event_type="TEST_CASE_DELETED",
            detail=json.dumps({
                "run_id": run_id_val,
                "report_id": report_id,
                "deleted_by": actor.username,
                "reason": reason or "Deleted by Standard Administrator",
            }),
        )
    )
    db.commit()
    return True


def list_tester_assigned_files(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """
    Returns sanitized test-case file records assigned exclusively to or generated by the given tester.
    Restricted information (requirements, snapshots, methodology) is strictly excluded.
    """
    user = db.query(User).filter(User.id == user_id).first()
    username = user.username if user else ""

    assignments = (
        db.query(TestCaseAssignment)
        .join(CognosGenerationRun, TestCaseAssignment.run_id == CognosGenerationRun.id)
        .filter(TestCaseAssignment.user_id == user_id, TestCaseAssignment.status == "ASSIGNED")
        .order_by(TestCaseAssignment.assigned_at.desc())
        .all()
    )

    assigned_run_ids = set()
    results = []
    for a in assignments:
        r = a.run
        if not r:
            continue
        assigned_run_ids.add(r.id)
        results.append({
            "assignment_id": a.id,
            "file_id": a.file_id,
            "run_id": a.run_id,
            "file_name": f"Cognos_UT_{r.report_id or r.id}.xlsx",
            "project_name": r.work_item_title or r.report_title or r.report_id or "Cognos Project",
            "dsd_name": r.source_document or r.report_id or "Cognos DSD",
            "report_id": r.report_id,
            "report_title": r.report_title or "Cognos Report",
            "status": "Ready" if r.status == "completed" else "Assigned",
            "assigned_date": a.assigned_at.isoformat() if a.assigned_at else None,
            "updated_date": a.updated_at.isoformat() if a.updated_at else (a.assigned_at.isoformat() if a.assigned_at else None),
            "test_case_count": r.test_cases_generated or 0,
            "can_view": True,
            "can_download": True,
            "source_type": "ASSIGNED",
        })

    # Include runs generated directly by this tester
    if username:
        created_runs = (
            db.query(CognosGenerationRun)
            .filter(CognosGenerationRun.requested_by == username)
            .order_by(CognosGenerationRun.id.desc())
            .all()
        )
        for r in created_runs:
            if r.id in assigned_run_ids:
                continue
            results.append({
                "assignment_id": None,
                "file_id": f"GEN-{r.id}",
                "run_id": r.id,
                "file_name": f"Cognos_UT_{r.report_id or r.id}.xlsx",
                "project_name": r.work_item_title or r.report_title or r.report_id or "Cognos Project",
                "dsd_name": r.source_document or r.report_id or "Cognos DSD",
                "report_id": r.report_id,
                "report_title": r.report_title or "Cognos Report",
                "status": "Ready" if r.status == "completed" else "Assigned",
                "assigned_date": r.completed_at.isoformat() if r.completed_at else None,
                "updated_date": r.completed_at.isoformat() if r.completed_at else None,
                "test_case_count": r.test_cases_generated or 0,
                "can_view": True,
                "can_download": True,
                "source_type": "SELF_GENERATED",
            })

    return results


def list_all_assignments(db: Session) -> Dict[str, Any]:
    """
    Returns all generation runs and their active assignments for administrative overview.
    """
    runs = db.query(CognosGenerationRun).order_by(CognosGenerationRun.id.desc()).all()
    active_testers = db.query(User).filter(User.role.in_(["tester", "approver"]), User.status == "ACTIVE").all()

    runs_data = []
    for r in runs:
        assignments = (
            db.query(TestCaseAssignment)
            .filter(TestCaseAssignment.run_id == r.id, TestCaseAssignment.status == "ASSIGNED")
            .all()
        )
        runs_data.append({
            "run_id": r.id,
            "report_id": r.report_id,
            "report_title": r.report_title,
            "source_document": r.source_document,
            "status": r.status,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "test_case_count": r.test_cases_generated,
            "assignments": [
                {
                    "assignment_id": a.id,
                    "file_id": a.file_id,
                    "user_id": a.user_id,
                    "username": a.user.username if a.user else "Unknown",
                    "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
                }
                for a in assignments
            ],
        })

    return {
        "runs": runs_data,
        "available_testers": [
            {"id": u.id, "username": u.username, "status": u.status, "role": u.role}
            for u in active_testers
        ],
    }


def validate_test_case_file_access(
    db: Session,
    file_id_or_run_id: str | int,
    current_user: CurrentUser,
) -> Tuple[CognosGenerationRun, Optional[TestCaseAssignment]]:
    """
    IDOR & RBAC Validator:
    - Admins can access any Test Cases file.
    - Testers can access ONLY files specifically assigned to them.
    - Any unauthorized attempt is audited as 'ACCESS_DENIED' and raises HTTP 403.
    """
    run: Optional[CognosGenerationRun] = None
    assignment: Optional[TestCaseAssignment] = None

    # Check if identifier is secure file_id (e.g. TCF-...)
    if isinstance(file_id_or_run_id, str) and file_id_or_run_id.startswith("TCF-"):
        assignment = db.query(TestCaseAssignment).filter(TestCaseAssignment.file_id == file_id_or_run_id).first()
        if assignment:
            run = assignment.run
    else:
        try:
            rid = int(file_id_or_run_id)
            run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == rid).first()
            if run:
                assignment = (
                    db.query(TestCaseAssignment)
                    .filter(
                        TestCaseAssignment.run_id == run.id,
                        TestCaseAssignment.user_id == current_user.id,
                        TestCaseAssignment.status == "ASSIGNED",
                    )
                    .first()
                )
        except (ValueError, TypeError):
            pass

    if not run:
        raise HTTPException(status_code=404, detail="Test case file or run not found.")

    # Standard Admin or approved Admin have universal access
    user_role = (getattr(current_user, "role", "") or "").lower().replace("-", "_")
    is_admin_or_higher = (
        getattr(current_user, "is_admin_or_higher", False) 
        or user_role in ("admin", "standard_admin")
    )
    if is_admin_or_higher:
        return run, assignment

    # Tester access validation:
    # A Tester can access their own created run OR a run assigned to them
    if user_role == "tester":
        is_owner = bool(run.requested_by and current_user and run.requested_by == current_user.username)
        valid_assignment = (
            db.query(TestCaseAssignment)
            .filter(
                TestCaseAssignment.run_id == run.id,
                TestCaseAssignment.user_id == current_user.id,
                TestCaseAssignment.status == "ASSIGNED",
            )
            .first()
        )
        if is_owner or valid_assignment:
            return run, valid_assignment

        # Audit denied attempt
        db.add(
            AuditLogEntry(
                user_id=current_user.username,
                event_type="ACCESS_DENIED",
                detail=json.dumps({
                    "reason": "IDOR violation: Tester attempted to access unassigned test case file",
                    "target_run_id": run.id,
                    "file_identifier": str(file_id_or_run_id),
                    "caller_username": current_user.username,
                }),
            )
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You do not have permission to access this test case file.",
        )

    # Any other role
    db.add(
        AuditLogEntry(
            user_id=current_user.username,
            event_type="ACCESS_DENIED",
            detail=json.dumps({
                "reason": "Unauthorized role attempting test case file access",
                "target_run_id": run.id,
                "caller_role": current_user.role,
            }),
        )
    )
    db.commit()
    raise HTTPException(status_code=403, detail="Forbidden: Insufficient privileges.")
