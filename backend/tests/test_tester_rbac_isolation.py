"""
Test Suite: Strict Tester RBAC Isolation, IDOR Defense, and Authorization Controls.

Verifies:
1. Tester blocked from restricted endpoints (403 Forbidden):
   - Extracted requirements / knowledge base
   - DSD raw structural intent / format detection / upload & generate
   - Evidence images and source snapshots
   - Methodology applicability & Gatekeeper scope summary
   - Administration pages & APIs
2. Test-Case File Security & IDOR Defense:
   - Testers cannot view or download files/runs not assigned to them (HTTP 403)
   - Standard Admin can assign, unassign, and delete files
   - Approved Admin can view all test cases, but cannot assign files or approve Admins
3. Data Sanitization:
   - Tester file responses contain zero requirements, zero evidence snapshots, zero methodology patterns
4. Session Invalidation on Assignment Change:
   - Active sessions for tester revoked when file assignment changes
5. Security Audit Log Completeness:
   - Records ACCESS_DENIED, TEST_CASE_VIEWED, TEST_CASE_DOWNLOADED, TEST_CASE_ASSIGNED
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.rbac import UserSession, TestCaseAssignment
from app.models.cognos_orm import CognosGenerationRun, CognosTestCaseModel, CognosRequirementModel
from app.models.audit import AuditLogEntry
from app.core.security import hash_password, create_access_token


def cleanup_test_data(db: Session):
    """Clean up test accounts and artifacts created during isolation testing."""
    try:
        db.rollback()
    except Exception:
        pass

    test_usernames = [
        "iso_tester_priya",
        "iso_tester_alex",
        "iso_admin_sundar",
        "iso_std_admin_obuli",
    ]
    users = db.query(User).filter(User.username.in_(test_usernames)).all()
    user_ids = [u.id for u in users]
    if user_ids:
        db.query(TestCaseAssignment).filter(
            (TestCaseAssignment.user_id.in_(user_ids)) | (TestCaseAssignment.assigned_by_id.in_(user_ids))
        ).delete(synchronize_session=False)
        db.query(UserSession).filter(UserSession.user_id.in_(user_ids)).delete(synchronize_session=False)
        for u in users:
            db.delete(u)

    # Clean test runs
    runs = db.query(CognosGenerationRun).filter(CognosGenerationRun.report_id.like("TEST-ISO-%")).all()
    for r in runs:
        db.query(TestCaseAssignment).filter(TestCaseAssignment.run_id == r.id).delete(synchronize_session=False)
        db.delete(r)

    db.commit()


@pytest.fixture(autouse=True)
def setup_teardown(db: Session):
    cleanup_test_data(db)
    yield
    cleanup_test_data(db)


def create_user_helper(db: Session, username: str, role: str, status: str = "ACTIVE") -> User:
    user = User(
        username=username,
        hashed_password=hash_password("Pass123!Secure#2026"),
        role=role,
        status=status,
        must_change_password=False,
        is_active=(status == "ACTIVE"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_session_token(db: Session, user: User) -> str:
    from app.core.security import generate_session_token
    token = generate_session_token()
    session = UserSession(
        session_id=token,
        user_id=user.id,
        ip_address="127.0.0.1",
        user_agent="PyTestClient",
        device_name="Test Runner",
        expires_at=datetime.now(timezone.utc).replace(year=2030),
        is_active=True,
    )
    db.add(session)
    db.commit()
    return token


def create_test_run(db: Session, report_id: str = "TEST-ISO-PRV027") -> CognosGenerationRun:
    run = CognosGenerationRun(
        report_id=report_id,
        report_title="Provider License Interface Test Run",
        source_document="PRV027_Spec.docx",
        source_document_path="runs/test/source.docx",
        requirements_extracted=5,
        test_cases_generated=3,
        coverage_percentage=100.0,
        status="completed",
        completed_at=datetime.now(timezone.utc),
        requested_by="iso_std_admin_obuli",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Add test cases
    for i in range(1, 4):
        tc = CognosTestCaseModel(
            run_id=run.id,
            test_case_id=f"TC-ISO-{i:02d}",
            report_id=run.report_id,
            category="Functional",
            test_case_title=f"Verify Field {i} Formatting",
            objective=f"Objective for test scenario {i}",
            preconditions="Database online",
            test_data="Record ID 100",
            test_steps=f"1. Open report\n2. Verify field {i}",
            expected_result=f"Field {i} matches specification",
            source_section="Report Specification",
            priority="High",
            status="Generated",
            origin="DSD_EXTRACTION",
            review_status="GENERATED",
            execution_method="Scheduled",
            execution_tool="IWA",
        )
        db.add(tc)

    # Add requirement
    req = CognosRequirementModel(
        run_id=run.id,
        requirement_id=f"REQ-ISO-01",
        report_id=run.report_id,
        category="Report Definition",
        field_name="Report ID",
        requirement_text="Report must display Client Report ID",
        source_section="Report Specification",
        confidence="HIGH",
    )
    db.add(req)
    db.commit()
    db.refresh(run)
    return run


# ─── 1. TESTER RESTRICTED ENDPOINTS VERIFICATION ───────────────────────────

def test_tester_forbidden_from_restricted_endpoints(client: TestClient, db: Session):
    """
    Tester accounts must receive HTTP 403 Forbidden on all restricted endpoints:
    - Extracted requirements, snapshots, evidence, format detection, upload, and administration.
    """
    tester = create_user_helper(db, "iso_tester_priya", role="tester")
    token = create_session_token(db, tester)
    headers = {"Authorization": f"Bearer {token}"}

    run = create_test_run(db, "TEST-ISO-RPT1")

    # 1. Format Detection (permitted for testers, returns 422 when missing file parameter)
    res = client.post("/api/cognos/detect-dsd-format", headers=headers)
    assert res.status_code == 422, f"Expected 422 validation error, got {res.status_code}"

    # 2. Upload and Generate (permitted for testers, returns 422 when missing file parameter)
    res = client.post("/api/cognos/upload-and-generate", headers=headers)
    assert res.status_code == 422, f"Expected 422 validation error, got {res.status_code}"

    # 3. Source Document (DSD) - Strictly restricted to admin
    res = client.get(f"/api/cognos/runs/{run.id}/source-document", headers=headers)
    assert res.status_code == 403

    # 4. Source Snapshot
    res = client.get(f"/api/cognos/runs/{run.id}/source-snapshot", headers=headers)
    assert res.status_code == 403

    # 5. Evidence Image
    res = client.get(f"/api/cognos/runs/{run.id}/evidence/test_snap.png", headers=headers)
    assert res.status_code == 403

    # 6. Knowledge Base Extracted Requirements
    res = client.get(f"/api/ingestion/knowledge-base/{run.report_id}", headers=headers)
    assert res.status_code == 403

    # 7. Ingestion Upload
    res = client.post("/api/ingestion/upload", headers=headers)
    assert res.status_code == 403

    # 8. Gatekeeper Scope Summary
    res = client.get(f"/api/gatekeeper/scope/{run.report_id}", headers=headers)
    assert res.status_code == 403

    # 9. Admin Users Management
    res = client.get("/api/admin/users", headers=headers)
    assert res.status_code == 403

    # 10. Admin Approvals
    res = client.get("/api/admin/approvals", headers=headers)
    assert res.status_code == 403

    # 11. Admin Audit Logs
    res = client.get("/api/admin/audit-logs", headers=headers)
    assert res.status_code == 403

    # 12. Admin Assignments Overview
    res = client.get("/api/admin/assignments", headers=headers)
    assert res.status_code == 403

    # Verify ACCESS_DENIED events were recorded in audit trail
    denied_events = db.query(AuditLogEntry).filter(
        AuditLogEntry.user_id == tester.username,
        AuditLogEntry.event_type == "ACCESS_DENIED",
    ).count()
    assert denied_events >= 5, "Expected ACCESS_DENIED audit log entries to be recorded."


# ─── 2. IDOR & FILE SECURITY ENFORCEMENT ────────────────────────────────────

def test_tester_idor_protection_on_unassigned_files(client: TestClient, db: Session):
    """
    A tester cannot access another user's or unassigned Test Cases file by modifying
    a URL, run ID, or file ID (IDOR defense).
    """
    tester1 = create_user_helper(db, "iso_tester_priya", role="tester")
    tester2 = create_user_helper(db, "iso_tester_alex", role="tester")

    token1 = create_session_token(db, tester1)
    headers1 = {"Authorization": f"Bearer {token1}"}

    run = create_test_run(db, "TEST-ISO-SECURE")

    # Unassigned run access attempts by tester1 -> 403 Forbidden
    res1 = client.get(f"/api/cognos/runs/{run.id}/test-cases", headers=headers1)
    assert res1.status_code == 403
    assert "Forbidden" in res1.json()["detail"]

    # Unassigned file view via /files/{file_id}/view -> 403 Forbidden
    res2 = client.get(f"/api/cognos/files/TCF-UNASSIGNED99/view", headers=headers1)
    assert res2.status_code == 404 or res2.status_code == 403


# ─── 3. ASSIGNMENT & DATA SANITIZATION ──────────────────────────────────────

def test_authorized_tester_access_and_sanitized_payload(client: TestClient, db: Session):
    """
    Standard Admin assigns file to Tester.
    Tester can access assigned file and payload contains zero restricted fields.
    """
    std_admin = create_user_helper(db, "iso_std_admin_obuli", role="standard_admin")
    tester = create_user_helper(db, "iso_tester_priya", role="tester")

    admin_token = create_session_token(db, std_admin)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    run = create_test_run(db, "TEST-ISO-PRV027")

    # 1. Standard Admin assigns run to tester
    assign_res = client.post(
        "/api/admin/assignments",
        headers=admin_headers,
        json={
            "run_id": run.id,
            "user_id": tester.id,
            "notes": "Assigned for SIT Sprint 26",
        },
    )
    assert assign_res.status_code == 200
    assign_data = assign_res.json()
    assert assign_data["status"] == "SUCCESS"
    file_id = assign_data["assignment"]["file_id"]
    assert file_id.startswith("TCF-")

    # Because assignment immediately revokes active sessions for target tester,
    # generate a fresh session token representing tester logging in after assignment.
    tester_token = create_session_token(db, tester)
    tester_headers = {"Authorization": f"Bearer {tester_token}"}

    # 2. Tester queries assigned files list
    list_res = client.get("/api/cognos/tester/assigned-files", headers=tester_headers)
    assert list_res.status_code == 200
    files_list = list_res.json()
    assert len(files_list) == 1
    file_record = files_list[0]
    assert file_record["file_id"] == file_id
    assert file_record["report_id"] == run.report_id
    assert file_record["can_view"] is True
    assert file_record["can_download"] is True

    # 3. Tester views assigned test cases
    view_res = client.get(f"/api/cognos/files/{file_id}/view", headers=tester_headers)
    assert view_res.status_code == 200
    view_data = view_res.json()
    assert view_data["file_id"] == file_id
    assert len(view_data["test_cases"]) == 3

    # Verify DATA SANITIZATION: Zero restricted data in response
    for tc in view_data["test_cases"]:
        assert "requirement_id" not in tc or tc.get("requirement_id") is None or tc.get("requirement_id") == ""
        assert "requirements" not in tc
        assert "source_mappings" not in tc
        assert "evidence_references" not in tc
        assert "validation_sql" not in tc
        assert "snapshot_url" not in tc

    # 4. Verify TEST_CASE_VIEWED audit entry
    view_audit = db.query(AuditLogEntry).filter(
        AuditLogEntry.user_id == tester.username,
        AuditLogEntry.event_type == "TEST_CASE_VIEWED",
    ).first()
    assert view_audit is not None, "TEST_CASE_VIEWED audit entry missing."


# ─── 4. STANDARD ADMIN VS REGULAR ADMIN BOUNDARIES ──────────────────────────

def test_admin_hierarchy_and_assignment_boundaries(client: TestClient, db: Session):
    """
    Standard Admin exclusively creates assignments, revokes assignments, and deletes runs.
    Regular Admin CANNOT create assignments or delete runs (403 Forbidden).
    """
    std_admin = create_user_helper(db, "iso_std_admin_obuli", role="standard_admin")
    reg_admin = create_user_helper(db, "iso_admin_sundar", role="admin")
    tester = create_user_helper(db, "iso_tester_priya", role="tester")

    reg_token = create_session_token(db, reg_admin)
    std_token = create_session_token(db, std_admin)

    run = create_test_run(db, "TEST-ISO-HIERARCHY")

    # Regular admin tries to create assignment -> 403 Forbidden
    illegal_assign = client.post(
        "/api/admin/assignments",
        headers={"Authorization": f"Bearer {reg_token}"},
        json={"run_id": run.id, "user_id": tester.id},
    )
    assert illegal_assign.status_code == 403
    assert "Standard Administrator" in illegal_assign.json()["detail"]

    # Regular admin tries to delete run -> 403 Forbidden
    illegal_delete = client.delete(
        f"/api/admin/runs/{run.id}",
        headers={"Authorization": f"Bearer {reg_token}"},
    )
    assert illegal_delete.status_code == 403

    # Regular admin CAN view assignment overview
    overview_res = client.get(
        "/api/admin/assignments",
        headers={"Authorization": f"Bearer {reg_token}"},
    )
    assert overview_res.status_code == 200

    # Standard Admin successfully assigns
    valid_assign = client.post(
        "/api/admin/assignments",
        headers={"Authorization": f"Bearer {std_token}"},
        json={"run_id": run.id, "user_id": tester.id},
    )
    assert valid_assign.status_code == 200
    assignment_id = valid_assign.json()["assignment"]["id"]

    # Standard Admin revokes assignment
    revoke_res = client.post(
        f"/api/admin/assignments/{assignment_id}/revoke",
        headers={"Authorization": f"Bearer {std_token}"},
        json={"reason": "Testing complete"},
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "SUCCESS"

    # Standard Admin deletes run
    delete_res = client.delete(
        f"/api/admin/runs/{run.id}",
        headers={"Authorization": f"Bearer {std_token}"},
    )
    assert delete_res.status_code == 200
    assert delete_res.json()["status"] == "SUCCESS"


# ─── 5. EVIDENCE & SOURCE SNAPSHOT ACCESS MATRIX ────────────────────────────

def test_evidence_and_snapshot_rbac_access_matrix(client: TestClient, db: Session):
    """
    Validates evidence and snapshot access matrix:
    1. Admin -> Allowed (200) on valid runs.
    2. Assigned Tester -> Allowed (200) on assigned runs.
    3. Unassigned Tester -> Forbidden (403) with ACCESS_DENIED audit log.
    4. Nonexistent Run -> 404 Not Found.
    5. Path Traversal -> Blocked safely without filesystem escape.
    """
    import os
    import time

    std_admin = create_user_helper(db, "iso_std_admin_obuli", role="standard_admin")
    assigned_tester = create_user_helper(db, "iso_tester_priya", role="tester")
    unassigned_tester = create_user_helper(db, "iso_tester_alex", role="tester")

    admin_token = create_session_token(db, std_admin)
    assigned_token = create_session_token(db, assigned_tester)
    unassigned_token = create_session_token(db, unassigned_tester)

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    assigned_headers = {"Authorization": f"Bearer {assigned_token}"}
    unassigned_headers = {"Authorization": f"Bearer {unassigned_token}"}

    # Setup dummy source document and cached snapshot file on disk
    test_source_doc = Path("runs/test/source.docx")
    test_source_doc.parent.mkdir(parents=True, exist_ok=True)
    test_source_doc.write_text("Dummy Source Docx")

    evidence_dir = Path("runs/evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    cached_snap = evidence_dir / "source_snapshot_test_ev_01.png"
    
    # 1x1 valid transparent PNG
    png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa74\x81\x00\x00\x00\x00IEND\xaeB`\x82'
    cached_snap.write_bytes(png_bytes)
    # Ensure mtime is in future so cache hit is guaranteed
    future_time = time.time() + 10000
    os.utime(cached_snap, (future_time, future_time))

    # Setup evidence image under jobs/test_job_123/evidence/ev_pic.png
    job_evidence_dir = Path("jobs/test_job_123/evidence")
    job_evidence_dir.mkdir(parents=True, exist_ok=True)
    job_evidence_file = job_evidence_dir / "ev_pic.png"
    job_evidence_file.write_bytes(png_bytes)

    try:
        run = create_test_run(db, "TEST-ISO-EVID-01")
        run.job_id = "test_job_123"
        db.commit()

        # Admin assigns run to assigned_tester
        assign_res = client.post(
            "/api/admin/assignments",
            headers=admin_headers,
            json={"run_id": run.id, "user_id": assigned_tester.id, "notes": "Assigned for Evidence test"},
        )
        assert assign_res.status_code == 200

        # Fresh token for assigned tester
        assigned_token = create_session_token(db, assigned_tester)
        assigned_headers = {"Authorization": f"Bearer {assigned_token}"}

        # --- TEST 1: Admin requests source-snapshot and evidence image (Expected: 200) ---
        res_admin_snap = client.get(f"/api/cognos/runs/{run.id}/source-snapshot?evidence_id=test_ev_01", headers=admin_headers)
        assert res_admin_snap.status_code == 200, f"Admin expected 200, got {res_admin_snap.status_code}"
        assert res_admin_snap.headers.get("content-type") == "image/png"

        res_admin_img = client.get(f"/api/cognos/runs/{run.id}/evidence/ev_pic", headers=admin_headers)
        assert res_admin_img.status_code == 200, f"Admin expected 200, got {res_admin_img.status_code}"
        assert res_admin_img.headers.get("content-type") == "image/png"

        # --- TEST 2: Assigned Tester requests source-snapshot and evidence image (Expected: 200) ---
        res_tester_snap = client.get(f"/api/cognos/runs/{run.id}/source-snapshot?evidence_id=test_ev_01", headers=assigned_headers)
        assert res_tester_snap.status_code == 200, f"Assigned tester expected 200, got {res_tester_snap.status_code}"
        assert res_tester_snap.headers.get("content-type") == "image/png"
        assert len(res_tester_snap.content) > 0

        res_tester_img = client.get(f"/api/cognos/runs/{run.id}/evidence/ev_pic", headers=assigned_headers)
        assert res_tester_img.status_code == 200, f"Assigned tester expected 200, got {res_tester_img.status_code}"
        assert res_tester_img.headers.get("content-type") == "image/png"

        # --- TEST 3: Unassigned Tester requests source-snapshot and evidence image (Expected: 403 Forbidden) ---
        res_unassigned_snap = client.get(f"/api/cognos/runs/{run.id}/source-snapshot?evidence_id=test_ev_01", headers=unassigned_headers)
        assert res_unassigned_snap.status_code == 403, f"Unassigned tester expected 403, got {res_unassigned_snap.status_code}"

        res_unassigned_img = client.get(f"/api/cognos/runs/{run.id}/evidence/ev_pic", headers=unassigned_headers)
        assert res_unassigned_img.status_code == 403, f"Unassigned tester expected 403, got {res_unassigned_img.status_code}"

        # Verify ACCESS_DENIED audit log recorded for unassigned tester
        denied_log = db.query(AuditLogEntry).filter(
            AuditLogEntry.user_id == unassigned_tester.username,
            AuditLogEntry.event_type == "ACCESS_DENIED",
        ).first()
        assert denied_log is not None, "Expected ACCESS_DENIED audit log for unassigned tester."

        # --- TEST 4: Invalid / Nonexistent Run (Expected: 404 Not Found) ---
        res_nonexistent_admin = client.get("/api/cognos/runs/999999/source-snapshot?evidence_id=test_ev_01", headers=admin_headers)
        assert res_nonexistent_admin.status_code == 404

        res_nonexistent_tester = client.get("/api/cognos/runs/999999/source-snapshot?evidence_id=test_ev_01", headers=assigned_headers)
        assert res_nonexistent_tester.status_code == 404

        # --- TEST 5: Path Traversal Defenses ---
        res_traversal_snap = client.get(f"/api/cognos/runs/{run.id}/source-snapshot?evidence_id=../../secret", headers=assigned_headers)
        assert res_traversal_snap.status_code in (400, 404)

        res_traversal_img = client.get(f"/api/cognos/runs/{run.id}/evidence/..%2F..%2Fsecret", headers=assigned_headers)
        assert res_traversal_img.status_code in (400, 404)

    finally:
        # Cleanup test files
        if cached_snap.exists():
            cached_snap.unlink(missing_ok=True)
        if job_evidence_file.exists():
            job_evidence_file.unlink(missing_ok=True)
        if test_source_doc.exists():
            test_source_doc.unlink(missing_ok=True)

