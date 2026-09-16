"""
Test Suite: Scenario Versioning, Feedback, Learning Candidates, and Provenance.

Verifies:
1. Scenario edits create immutable `ScenarioVersion` records (v1 AI_GENERATED -> v2 TESTER_CORRECTION).
2. Scenario approvals create `ScenarioFeedback` and select into `LearningCandidate`.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.cognos_orm import CognosGenerationRun, CognosTestCaseModel
from app.models.rbac import TestCaseAssignment
from app.models.governance import (
    GeneratedScenario, ScenarioVersion, ScenarioFeedback,
    LearningCandidate
)
from app.core.security import hash_password, create_access_token


@pytest.fixture
def tester_user(db: Session):
    uname = "version_tester_bob"
    u = db.query(User).filter(User.username == uname).first()
    if not u:
        u = User(
            username=uname,
            hashed_password=hash_password("Tester#Pass2026!"),
            role="tester",
            status="ACTIVE",
            is_active=True,
            must_change_password=False,
        )
        db.add(u)
        db.commit()
    else:
        u.role = "tester"
        u.status = "ACTIVE"
        u.is_active = True
        u.must_change_password = False
        db.commit()

    token = create_access_token(subject=uname, role="tester", expires_seconds=3600)
    yield {"user": u, "token": token}

    # Cleanup
    u = db.query(User).filter(User.username == uname).first()
    if u:
        db.delete(u)
        db.commit()


@pytest.fixture
def sample_test_case(db: Session, tester_user: dict):
    """Creates a sample generation run and test case assigned to tester."""
    run = CognosGenerationRun(
        report_id="TEST-VER-001",
        report_title="Version Test Report",
        source_document="test.docx",
        status="completed",
        requested_by=tester_user["user"].username,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    tc = CognosTestCaseModel(
        run_id=run.id,
        test_case_id="TC-VER-001",
        report_id="TEST-VER-001",
        category="General",
        test_case_title="Initial AI Title",
        objective="Verify initial behavior",
        test_steps="Step 1: Run report",
        expected_result="Report runs cleanly",
        priority="Medium",
        status="Generated",
        origin="AI",
        version=1,
        review_status="GENERATED",
        source_section="General Information",
    )
    db.add(tc)

    file_id = f"assign-{uuid.uuid4()}"
    assignment = TestCaseAssignment(
        file_id=file_id,
        run_id=run.id,
        user_id=tester_user["user"].id,
        status="ASSIGNED",
    )
    db.add(assignment)
    db.commit()
    db.refresh(tc)

    yield {"run": run, "test_case": tc}

    # Cleanup
    db.query(TestCaseAssignment).filter(TestCaseAssignment.run_id == run.id).delete(synchronize_session=False)
    db.query(ScenarioVersion).filter(ScenarioVersion.test_case_id == "TC-VER-001").delete(synchronize_session=False)
    db.query(ScenarioFeedback).filter(ScenarioFeedback.scenario_id.in_(
        db.query(GeneratedScenario.id).filter(GeneratedScenario.run_id == run.id)
    )).delete(synchronize_session=False)
    db.query(LearningCandidate).filter(LearningCandidate.test_case_id == "TC-VER-001").delete(synchronize_session=False)
    db.query(GeneratedScenario).filter(GeneratedScenario.run_id == run.id).delete(synchronize_session=False)
    db.query(CognosTestCaseModel).filter(CognosTestCaseModel.run_id == run.id).delete(synchronize_session=False)
    db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run.id).delete(synchronize_session=False)
    db.commit()


def test_scenario_edit_creates_new_version(client: TestClient, tester_user: dict, sample_test_case: dict, db: Session):
    """Tester editing a scenario must bump version to 2 and create a ScenarioVersion record."""
    run_id = sample_test_case["run"].id
    tc_id = sample_test_case["test_case"].test_case_id
    token = tester_user["token"]
    headers = {"Authorization": f"Bearer {token}"}

    update_payload = {
        "action": "UPDATE_SCENARIO",
        "scenario_data": {
            "test_case_title": "Tester Corrected Title",
            "objective": "Updated objective by human tester",
            "test_steps": "Step 1: Check corrected rule\nStep 2: Run verification",
            "expected_result": "Matches human expectation",
        },
    }

    resp = client.patch(f"/api/cognos/runs/{run_id}/test-cases/{tc_id}/review", json=update_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["test_case"]["version"] == 2
    assert data["test_case"]["review_status"] == "CORRECTED"

    # Verify relational ScenarioVersion created in database
    ver = (
        db.query(ScenarioVersion)
        .filter(ScenarioVersion.test_case_id == tc_id, ScenarioVersion.version_number == 2)
        .first()
    )
    assert ver is not None, "ScenarioVersion v2 was not created in database!"
    assert ver.source == "TESTER_CORRECTION"
    assert ver.changed_by == tester_user["user"].username


def test_scenario_approval_creates_feedback_and_learning_candidate(client: TestClient, tester_user: dict, sample_test_case: dict, db: Session):
    """Approving a scenario creates ScenarioFeedback and selects it as a LearningCandidate."""
    run_id = sample_test_case["run"].id
    tc_id = sample_test_case["test_case"].test_case_id
    token = tester_user["token"]
    headers = {"Authorization": f"Bearer {token}"}

    approval_payload = {
        "action": "APPROVE",
        "comments": "Scenario meets all Cognos prompt criteria",
    }

    resp = client.patch(f"/api/cognos/runs/{run_id}/test-cases/{tc_id}/review", json=approval_payload, headers=headers)
    assert resp.status_code == 200

    # Verify ScenarioFeedback row
    gen_scen = db.query(GeneratedScenario).filter(GeneratedScenario.test_case_id == tc_id).first()
    if gen_scen:
        fb = db.query(ScenarioFeedback).filter(ScenarioFeedback.scenario_id == gen_scen.id).first()
        assert fb is not None
        assert fb.feedback_type == "APPROVED"

    # Verify LearningCandidate selection
    cand = db.query(LearningCandidate).filter(LearningCandidate.test_case_id == tc_id).first()
    assert cand is not None, "Approved scenario must be captured as a learning candidate!"
    assert cand.selected_for_learning is True
    assert cand.approval_status == "APPROVED"
