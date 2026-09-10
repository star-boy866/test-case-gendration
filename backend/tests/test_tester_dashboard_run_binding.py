import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User
from app.models.rbac import UserSession, TestCaseAssignment
from app.models.cognos_orm import CognosGenerationRun, CognosTestCaseModel
from app.core.security import hash_password, generate_session_token


def cleanup(db: Session):
    try:
        db.rollback()
    except Exception:
        pass
    test_usernames = ["reg_tester_bind_1", "reg_admin_bind_1"]
    users = db.query(User).filter(User.username.in_(test_usernames)).all()
    user_ids = [u.id for u in users]
    if user_ids:
        db.query(TestCaseAssignment).filter(
            (TestCaseAssignment.user_id.in_(user_ids)) | (TestCaseAssignment.assigned_by_id.in_(user_ids))
        ).delete(synchronize_session=False)
        db.query(UserSession).filter(UserSession.user_id.in_(user_ids)).delete(synchronize_session=False)
        for u in users:
            db.delete(u)
    runs = db.query(CognosGenerationRun).filter(CognosGenerationRun.report_id.like("REG-BIND-%")).all()
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


def test_tester_dashboard_exact_run_binding(clean_db, db: Session):
    """
    Validates that:
    1. Tester with multiple assigned files receives exact canonical run IDs.
    2. Requesting Run A returns Report A without fallback to the newer Run B.
    3. Requesting Run B returns Report B without fallback to Run A.
    4. Top-level report_title is always included in the response.
    """
    client = TestClient(app)

    tester, tester_token = create_user_and_token(db, "reg_tester_bind_1", "tester")
    admin, _ = create_user_and_token(db, "reg_admin_bind_1", "admin")

    # Create Run A (PRV-INT-011 equivalent)
    run_a = CognosGenerationRun(
        report_id="REG-BIND-011",
        report_title="Common License Data Interface Error Report",
        source_document="DSD_PRV_INT_011.docx",
        status="completed",
        test_cases_generated=18,
        requested_by="admin",
        work_type="CR",
        work_item_id="CR-011",
        work_item_title="Common License Data Interface Error Report",
    )
    db.add(run_a)
    db.commit()
    db.refresh(run_a)

    # Add scenario to Run A
    tc_a = CognosTestCaseModel(
        run_id=run_a.id,
        report_id="REG-BIND-011",
        test_case_id="REG011-EXEC-01",
        test_case_title="Execute PRV-INT-011 via IWA",
        category="Execution",
        scenario_order=1,
        objective="Verify execution",
        test_steps="Step 1: Execute",
        expected_result="Delivers to SDR",
        source_section="Report Body",
        priority="High",
        origin="LLM",
    )
    db.add(tc_a)

    # Assign Run A to tester
    assign_a = TestCaseAssignment(
        run_id=run_a.id,
        user_id=tester.id,
        assigned_by_id=admin.id,
        file_id="TCF-REG-011-AAAA",
        status="ASSIGNED",
    )
    db.add(assign_a)

    # Create Run B (PRV-INT-026 equivalent, created later = newer / latest)
    run_b = CognosGenerationRun(
        report_id="REG-BIND-026",
        report_title="Provider License Interface - Non-Active Status Report",
        source_document="DSD_PRV_INT_026.docx",
        status="completed",
        test_cases_generated=15,
        requested_by="admin",
        work_type="CR",
        work_item_id="CR-026",
        work_item_title="Provider License Interface - Non-Active Status Report",
    )
    db.add(run_b)
    db.commit()
    db.refresh(run_b)

    # Add scenario to Run B
    tc_b = CognosTestCaseModel(
        run_id=run_b.id,
        report_id="REG-BIND-026",
        test_case_id="REG026-EXEC-01",
        test_case_title="Execute PRV-INT-026 via IWA",
        category="Execution",
        scenario_order=1,
        objective="Verify execution",
        test_steps="Step 1: Execute",
        expected_result="Delivers to SDR",
        source_section="Report Body",
        priority="High",
        origin="LLM",
    )
    db.add(tc_b)

    # Assign Run B to tester
    assign_b = TestCaseAssignment(
        run_id=run_b.id,
        user_id=tester.id,
        assigned_by_id=admin.id,
        file_id="TCF-REG-026-BBBB",
        status="ASSIGNED",
    )
    db.add(assign_b)
    db.commit()

    # Step 1: Tester fetches assigned files list
    headers = {"Authorization": f"Bearer {tester_token}"}
    resp = client.get("/api/cognos/tester/assigned-files", headers=headers)
    assert resp.status_code == 200, resp.text
    files = resp.json()
    assert len(files) >= 2

    # Map files by run_id
    file_map = {f["run_id"]: f for f in files}
    assert run_a.id in file_map
    assert run_b.id in file_map

    file_a = file_map[run_a.id]
    assert file_a["file_id"] == "TCF-REG-011-AAAA"
    assert file_a["report_id"] == "REG-BIND-011"
    assert file_a["test_case_count"] == 18

    file_b = file_map[run_b.id]
    assert file_b["file_id"] == "TCF-REG-026-BBBB"
    assert file_b["report_id"] == "REG-BIND-026"
    assert file_b["test_case_count"] == 15

    # Step 2: Navigate to clicked Run A (run_a.id)
    resp_a = client.get(f"/api/cognos/runs/{run_a.id}", headers=headers)
    assert resp_a.status_code == 200, resp_a.text
    data_a = resp_a.json()
    assert data_a["run_id"] == run_a.id
    assert data_a["report_id"] == "REG-BIND-011"
    assert data_a["report_title"] == "Common License Data Interface Error Report"
    assert len(data_a["test_cases"]) == 1
    assert data_a["test_cases"][0]["test_case_id"] == "REG011-EXEC-01"

    # Step 3: Navigate to clicked Run B (run_b.id)
    resp_b = client.get(f"/api/cognos/runs/{run_b.id}", headers=headers)
    assert resp_b.status_code == 200, resp_b.text
    data_b = resp_b.json()
    assert data_b["run_id"] == run_b.id
    assert data_b["report_id"] == "REG-BIND-026"
    assert data_b["report_title"] == "Provider License Interface - Non-Active Status Report"
    assert len(data_b["test_cases"]) == 1
    assert data_b["test_cases"][0]["test_case_id"] == "REG026-EXEC-01"

    # Step 4: Cross-Row return to Run A to ensure no residual state
    resp_a2 = client.get(f"/api/cognos/runs/{run_a.id}", headers=headers)
    assert resp_a2.status_code == 200
    data_a2 = resp_a2.json()
    assert data_a2["run_id"] == run_a.id
    assert data_a2["report_id"] == "REG-BIND-011"
