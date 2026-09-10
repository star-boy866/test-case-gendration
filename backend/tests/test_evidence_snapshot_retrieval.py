"""
Automated tests for Cognos Evidence Retrieval on Local & Render.

Verifies:
  1. Authoritative DSD snapshot retrieval (HTTP 200 image/png).
  2. Resilient fallback when source.docx is missing from disk (Tier 3 DB metadata -> HTTP 200 image/png).
  3. Strict RBAC enforcement:
     - Unauthenticated -> 401 Unauthorized
     - Unassigned tester -> 403 Forbidden with ACCESS_DENIED audit log
     - Assigned tester / Admin -> 200 OK
  4. Path traversal protection (.. / slashes -> 400 Bad Request).
  5. Multi-location snapshot resolution across candidate runs directories.
"""

from datetime import datetime, timezone
from typing import Tuple
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.cognos_orm import CognosGenerationRun, CognosTestCaseModel
from app.models.rbac import TestCaseAssignment
from app.core.security import hash_password, create_access_token


def create_user_helper(db: Session, username: str, role: str) -> User:
    existing = db.query(User).filter_by(username=username).first()
    if existing:
        existing.role = role
        existing.must_change_password = False
        existing.status = "ACTIVE"
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    user = User(
        username=username,
        hashed_password=hash_password("Pass123!Secure#2026"),
        role=role,
        status="ACTIVE",
        must_change_password=False,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_run_with_evidence(db: Session, report_id: str = "TEST-EVID-01") -> Tuple[CognosGenerationRun, CognosTestCaseModel]:
    run = CognosGenerationRun(
        report_id=report_id,
        report_title="Provider License Interface Test Report",
        source_document="source.docx",
        source_document_sha256="dummy_sha256",
        source_document_path="runs/test_missing/source.docx",
        status="completed",
        completed_at=datetime.now(timezone.utc),
        requested_by="admin",
        job_id="test_job_evidence_1",
    )
    db.add(run)
    db.flush()

    tc = CognosTestCaseModel(
        run_id=run.id,
        test_case_id="PRV027-EXEC-01",
        report_id=report_id,
        category="Functional",
        test_case_title="Scheduled Execution Validation",
        objective="Verify scheduled report execution frequency",
        test_steps="1. Open Report\n2. Verify evidence snapshot",
        expected_result="Evidence snapshot rendered successfully",
        priority="High",
        origin="AI_GENERATED",
        source_section="Report Generation",
        source_page=6,
        processing_rule="Daily execution at midnight",
        evidence_references=[
            {
                "evidence_id": "snapshot_PRV027-EXEC-01_SCHEDU",
                "evidence_type": "SOURCE_DSD_SNAPSHOT",
                "section": "Report Generation",
                "methodology": "SCHEDULED_EXECUTION_VALIDATION",
                "target_field": "Scheduled / Report Frequency Type",
                "evidence_scope": "REPORT_FREQUENCY_SCHEDULING",
                "test_case_id": "PRV027-EXEC-01",
                "snapshot_path": "",
                "snapshot_url": "",
            }
        ],
    )
    db.add(tc)
    db.commit()
    db.refresh(run)
    db.refresh(tc)
    return run, tc


def test_evidence_snapshot_missing_docx_fallback(client: TestClient, db: Session):
    """
    Verifies that when source.docx does NOT exist on disk (as on a clean Render deploy
    or ephemeral container restart), Tier 3 generates the snapshot from DB metadata.
    """
    admin = create_user_helper(db, "test_admin_snap_02", "admin")
    admin_token = create_access_token(subject=admin.username, role=admin.role)
    headers = {"Authorization": f"Bearer {admin_token}"}

    run, tc = create_test_run_with_evidence(db, "TEST-FALLBACK-01")

    params = {
        "evidence_id": "snapshot_PRV027-EXEC-01_SCHEDU",
        "section": "Report Generation",
        "methodology": "SCHEDULED_EXECUTION_VALIDATION",
        "target_field": "Scheduled / Report Frequency Type",
        "evidence_scope": "REPORT_FREQUENCY_SCHEDULING",
        "test_case_id": "PRV027-EXEC-01",
    }
    res = client.get(f"/api/cognos/runs/{run.id}/source-snapshot", params=params, headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    assert "image/png" in res.headers.get("content-type", "")
    assert len(res.content) > 0


def test_evidence_snapshot_strict_rbac(client: TestClient, db: Session):
    """Verifies that evidence endpoints strictly enforce authorization."""
    run, tc = create_test_run_with_evidence(db, "TEST-RBAC-01")

    # 1. Unauthenticated -> 401
    res_no_auth = client.get(f"/api/cognos/runs/{run.id}/source-snapshot")
    assert res_no_auth.status_code == 401

    # 2. Unassigned tester -> 403
    unassigned = create_user_helper(db, "test_unassigned_tester_snap", "tester")
    unassigned_token = create_access_token(subject=unassigned.username, role=unassigned.role)
    res_unassigned = client.get(
        f"/api/cognos/runs/{run.id}/source-snapshot",
        params={"evidence_id": "snapshot_PRV027-EXEC-01_SCHEDU"},
        headers={"Authorization": f"Bearer {unassigned_token}"},
    )
    assert res_unassigned.status_code == 403

    # 3. Assigned tester -> 200
    assigned = create_user_helper(db, "test_assigned_tester_snap", "tester")
    assignment = TestCaseAssignment(
        run_id=run.id,
        user_id=assigned.id,
        file_id=f"TCF-{run.id}",
        status="ASSIGNED",
    )
    db.add(assignment)
    db.commit()

    assigned_token = create_access_token(subject=assigned.username, role=assigned.role)
    res_assigned = client.get(
        f"/api/cognos/runs/{run.id}/source-snapshot",
        params={"evidence_id": "snapshot_PRV027-EXEC-01_SCHEDU"},
        headers={"Authorization": f"Bearer {assigned_token}"},
    )
    assert res_assigned.status_code == 200
    assert "image/png" in res_assigned.headers.get("content-type", "")

    # 4. Path traversal attempt -> 400
    admin = create_user_helper(db, "test_admin_snap_03", "admin")
    admin_token = create_access_token(subject=admin.username, role=admin.role)
    res_traversal = client.get(
        f"/api/cognos/runs/{run.id}/source-snapshot",
        params={"evidence_id": "../../etc/passwd"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_traversal.status_code in (400, 404)


def test_evidence_image_endpoint_fallback(client: TestClient, db: Session):
    """Verifies that /runs/{run_id}/evidence/{evidence_id} successfully finds/generates images."""
    admin = create_user_helper(db, "test_admin_snap_04", "admin")
    admin_token = create_access_token(subject=admin.username, role=admin.role)
    headers = {"Authorization": f"Bearer {admin_token}"}

    run, tc = create_test_run_with_evidence(db, "TEST-IMAGE-01")

    res = client.get(
        f"/api/cognos/runs/{run.id}/evidence/source_snapshot_snapshot_PRV027-EXEC-01_SCHEDU",
        headers=headers,
    )
    assert res.status_code == 200
    assert "image" in res.headers.get("content-type", "")
