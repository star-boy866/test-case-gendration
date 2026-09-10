import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User
from app.models.rbac import UserSession, TestCaseAssignment
from app.models.cognos_orm import CognosGenerationRun, CognosTestCaseModel, CognosRequirementModel
from app.core.security import hash_password, generate_session_token


def cleanup(db: Session):
    try:
        db.rollback()
    except Exception:
        pass
    test_usernames = ["studio_tester_1", "studio_tester_2", "studio_admin"]
    users = db.query(User).filter(User.username.in_(test_usernames)).all()
    user_ids = [u.id for u in users]
    if user_ids:
        db.query(TestCaseAssignment).filter(
            (TestCaseAssignment.user_id.in_(user_ids)) | (TestCaseAssignment.assigned_by_id.in_(user_ids))
        ).delete(synchronize_session=False)
        db.query(UserSession).filter(UserSession.user_id.in_(user_ids)).delete(synchronize_session=False)
        for u in users:
            db.delete(u)
    runs = db.query(CognosGenerationRun).filter(CognosGenerationRun.report_id.like("TEST-STUDIO-%")).all()
    for r in runs:
        db.query(TestCaseAssignment).filter(TestCaseAssignment.run_id == r.id).delete(synchronize_session=False)
        db.query(CognosTestCaseModel).filter(CognosTestCaseModel.run_id == r.id).delete(synchronize_session=False)
        db.delete(r)
    db.commit()


@pytest.fixture
def clean_db(db: Session):
    cleanup(db)
    yield
    cleanup(db)


def create_user_and_token(db: Session, username: str, role: str):
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
    return user, token


def test_tester_studio_ownership_and_access(client: TestClient, db: Session, clean_db):
    tester1, token1 = create_user_and_token(db, "studio_tester_1", "tester")
    tester2, token2 = create_user_and_token(db, "studio_tester_2", "tester")
    admin, admin_token = create_user_and_token(db, "studio_admin", "admin")

    # 1. Tester 1 creates a run
    run = CognosGenerationRun(
        report_id="TEST-STUDIO-PRV027",
        report_title="Provider License Interface Test Run",
        source_document="PRV027_Spec.docx",
        source_document_path="runs/test/source.docx",
        requirements_extracted=5,
        test_cases_generated=2,
        coverage_percentage=100.0,
        status="completed",
        completed_at=datetime.now(timezone.utc),
        requested_by=tester1.username,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    tc1 = CognosTestCaseModel(
        run_id=run.id,
        test_case_id="TC-STUDIO-01",
        report_id=run.report_id,
        category="Functional",
        test_case_title="Verify Field 1",
        objective="Objective 1",
        preconditions="Database online",
        test_data="Record ID 100",
        test_steps="1. Open report\n2. Verify field",
        expected_result="Field matches specification",
        validation_sql="SELECT * FROM CLAIMS WHERE ID = 100",
        source_section="Report Specification",
        source_page="5",
        source_table="Table 1",
        source_column="Field 1",
        processing_rule="Rule 1",
        formatting_rule="Format 1",
        priority="High",
        status="Generated",
        origin="DSD_EXTRACTION",
        review_status="GENERATED",
        execution_method="Scheduled",
        execution_tool="IWA",
        version=1,
    )
    db.add(tc1)
    db.commit()

    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}
    headers_admin = {"Authorization": f"Bearer {admin_token}"}

    # 2. Tester 1 can access own run details (200 OK)
    res = client.get(f"/api/cognos/runs/{run.id}", headers=headers1)
    assert res.status_code == 200, f"Tester 1 should access own run, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["run_id"] == run.id
    assert len(data["test_cases"]) == 1
    assert data["test_cases"][0]["validation_sql"] == "SELECT * FROM CLAIMS WHERE ID = 100"

    # 3. Tester 1 gets own run on /runs-latest (200 OK)
    res = client.get("/api/cognos/runs-latest", headers=headers1)
    assert res.status_code == 200
    assert res.json()["run_id"] == run.id

    # 4. Tester 1 can review / edit scenario in own run (200 OK)
    res = client.patch(
        f"/api/cognos/runs/{run.id}/test-cases/TC-STUDIO-01/review",
        json={"action": "FLAG_ISSUE", "issue_type": "Data Discrepancy", "issue_comment": "Check field mapping"},
        headers=headers1,
    )
    assert res.status_code == 200

    # 5. Tester 2 CANNOT access Tester 1's unassigned run (403 Forbidden)
    res = client.get(f"/api/cognos/runs/{run.id}", headers=headers2)
    assert res.status_code == 403, f"Tester 2 should be forbidden from Tester 1's run, got {res.status_code}"

    # 6. Tester 1 CANNOT access Admin pages (403 Forbidden)
    res = client.get("/api/admin/users", headers=headers1)
    assert res.status_code == 403
    res = client.get("/api/admin/approvals", headers=headers1)
    assert res.status_code == 403

    # 7. Admin CAN access Tester 1's run (200 OK)
    res = client.get(f"/api/cognos/runs/{run.id}", headers=headers_admin)
    assert res.status_code == 200
