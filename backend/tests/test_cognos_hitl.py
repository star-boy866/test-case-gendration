"""
Unit and integration tests for Cognos Human-in-the-Loop (HITL) review workflow.
"""

import pytest
from app.services.cognos_hitl_service import (
    evaluate_execution_path_rules,
    generate_suggested_correction,
    generate_missing_scenario,
    compute_field_diffs,
    record_history_entry,
)


def test_evaluate_execution_path_rules_nh_scheduled():
    tc_data = {
        "report_id": "PRV-INT-027",
        "execution_method": "Scheduled",
        "test_steps": "1. Login to Cognos portal.\n2. Run report PRV-INT-027.\n3. Download PDF.",
    }
    eval_result = evaluate_execution_path_rules(
        tc_data,
        report_id="PRV-INT-027",
        dsd_profile="NH",
        frequency_type="Scheduled",
    )

    assert eval_result["is_scheduled"] is True
    assert eval_result["state_code"] == "NH"
    assert eval_result["expected_tool"] == "IWA"
    assert eval_result["expected_report_id"] == "RPT-PRV-INT-027"
    assert eval_result["mismatch_detected"] is True
    assert "IWA" in eval_result["suggested_steps"]
    assert "20 minutes" in eval_result["suggested_steps"]
    assert "SDR" in eval_result["suggested_steps"]


def test_evaluate_execution_path_rules_nd_scheduled():
    tc_data = {
        "report_id": "ND-OPR-001",
        "execution_method": "Scheduled",
        "test_steps": "1. Login to Cognos portal.\n2. Run report ND-OPR-001.",
    }
    eval_result = evaluate_execution_path_rules(
        tc_data,
        report_id="ND-OPR-001",
        dsd_profile="ND",
        frequency_type="Scheduled",
    )

    assert eval_result["is_scheduled"] is True
    assert eval_result["state_code"] == "ND"
    assert eval_result["expected_tool"] == "UC4"
    assert eval_result["expected_report_id"] == "RPT-ND-OPR-001"
    assert eval_result["mismatch_detected"] is True


def test_evaluate_execution_path_rules_on_request():
    tc_data = {
        "report_id": "PRV-INT-027",
        "execution_method": "On Request",
        "test_steps": "1. Login to Cognos portal.\n2. Search PRV-INT-027.\n3. Download format.",
    }
    eval_result = evaluate_execution_path_rules(
        tc_data,
        report_id="PRV-INT-027",
        dsd_profile="NH",
        frequency_type="On Request",
    )

    assert eval_result["is_scheduled"] is False
    assert eval_result["mismatch_detected"] is False
    assert "Cognos portal" in eval_result["suggested_steps"]
    assert "Info Analysis" in eval_result["suggested_steps_alt"]


def test_generate_suggested_correction_execution_mismatch():
    tc_data = {
        "report_id": "PRV-INT-027",
        "execution_method": "Scheduled",
        "execution_tool": "Cognos Portal",
        "test_steps": "1. Login to Cognos portal.\n2. Run report PRV-INT-027.",
        "expected_result": "Report output downloaded.",
    }
    correction = generate_suggested_correction(
        tc_data,
        issue_type="Incorrect execution method",
        issue_comment="Scheduled execution uses IWA and delivers to SDR",
        report_metadata={"report_id": "PRV-INT-027", "dsd_profile": "NH", "frequency_type": "Scheduled"}
    )

    assert correction["correction_type"] == "EXECUTION_METHOD_CORRECTION"
    assert correction["suggested"]["execution_tool"] == "IWA"
    assert correction["suggested"]["report_id"] == "RPT-PRV-INT-027"
    assert "SDR" in correction["suggested"]["test_steps"]


def test_generate_missing_scenario():
    proposed = generate_missing_scenario(
        what_to_test="Report retention and 90-day archive purge",
        dsd_reference="Report Retention • Page 12",
        report_id="PRV-INT-027",
        existing_count=5,
    )

    assert "PRV" in proposed["test_case_id"]
    assert proposed["category"] == "Report Retention Validation"
    assert "Report Retention • Page 12" in proposed["objective"]
    assert "IWA" in proposed["execution_tool"]
    assert proposed["version"] == 1
    assert proposed["review_status"] == "GENERATED"


def test_compute_field_diffs_and_history():
    old_data = {
        "test_case_title": "Old Name",
        "execution_tool": "Cognos Portal",
        "test_steps": "Step 1",
    }
    new_data = {
        "test_case_title": "New Name",
        "execution_tool": "IWA",
        "test_steps": "Step 1",
    }
    diffs = compute_field_diffs(old_data, new_data)

    assert len(diffs) == 2
    diff_fields = [d["field"] for d in diffs]
    assert "Scenario Name" in diff_fields
    assert "Execution Tool" in diff_fields

    history = record_history_entry(
        history_list=[],
        version=2,
        action_type="HUMAN_CORRECTED",
        status="CORRECTED",
        author="qa_lead",
        summary="Updated execution tool to IWA",
        diffs=diffs,
    )

    assert len(history) == 1
    assert history[0]["version"] == 2
    assert history[0]["action"] == "HUMAN_CORRECTED"
    assert history[0]["status"] == "CORRECTED"
    assert history[0]["author"] == "qa_lead"
    assert len(history[0]["diffs"]) == 2


def test_hitl_api_review_lifecycle():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.session import get_db, SessionLocal
    from app.models.cognos_orm import CognosGenerationRun, CognosTestCaseModel
    from app.core.rbac import get_current_user, CurrentUser

    # Override auth for tests
    def mock_get_current_user():
        return CurrentUser(username="test_reviewer", role="tester")

    app.dependency_overrides[get_current_user] = mock_get_current_user

    client = TestClient(app)
    db = SessionLocal()

    try:
        # Create a test run
        run = CognosGenerationRun(
            report_id="PRV-INT-027",
            report_title="Provider License Interface Report",
            source_document="test.docx",
            requested_by="test_reviewer",
            status="completed",
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Create a test case
        tc = CognosTestCaseModel(
            run_id=run.id,
            test_case_id="PRV027-REPO-01",
            report_id="PRV-INT-027",
            category="Report Definition",
            test_case_title="Report Definition Validation",
            objective="Validate report metadata.",
            source_section="Report Specification",
            test_steps="1. Login to Cognos portal.\n2. Run report.",
            expected_result="Report executes successfully.",
            priority="Medium",
            status="Generated",
            origin="PIPELINE",
            version=1,
            review_status="GENERATED",
            execution_method="Scheduled",
            execution_tool="Cognos Portal",
            scenario_order=10,
        )
        db.add(tc)
        db.commit()

        # 1. FLAG_ISSUE
        res_flag = client.patch(
            f"/api/cognos/runs/{run.id}/test-cases/PRV027-REPO-01/review",
            json={
                "action": "FLAG_ISSUE",
                "issue_type": "Incorrect execution method",
                "issue_comment": "Scheduled report runs via IWA scheduler",
            }
        )
        assert res_flag.status_code == 200
        data_flag = res_flag.json()
        assert data_flag["test_case"]["review_status"] == "NEEDS_REVIEW"
        assert data_flag["test_case"]["issue_type"] == "Incorrect execution method"

        # 2. SUGGEST_CORRECTION
        res_sug = client.post(
            f"/api/cognos/runs/{run.id}/test-cases/PRV027-REPO-01/suggest-correction",
            json={"issue_type": "Incorrect execution method", "issue_comment": "Scheduled report runs via IWA"}
        )
        assert res_sug.status_code == 200
        assert res_sug.json()["suggestion"]["correction_type"] == "EXECUTION_METHOD_CORRECTION"

        # 3. UPDATE_SCENARIO
        res_upd = client.patch(
            f"/api/cognos/runs/{run.id}/test-cases/PRV027-REPO-01/review",
            json={
                "action": "UPDATE_SCENARIO",
                "scenario_data": {
                    "execution_tool": "IWA",
                    "report_id": "RPT-PRV-INT-027",
                    "test_steps": "1. Login to IWA.\n2. Search RPT-PRV-INT-027.\n3. Run report.",
                    "expected_result": "Output available in SDR (~20 min).",
                }
            }
        )
        assert res_upd.status_code == 200
        data_upd = res_upd.json()
        assert data_upd["test_case"]["review_status"] == "CORRECTED"
        assert data_upd["test_case"]["version"] == 2
        assert data_upd["test_case"]["execution_tool"] == "IWA"

        # 4. APPROVE
        res_app = client.patch(
            f"/api/cognos/runs/{run.id}/test-cases/PRV027-REPO-01/review",
            json={"action": "APPROVE", "review_comments": "Validated against IWA job definitions"}
        )
        assert res_app.status_code == 200
        data_app = res_app.json()
        assert data_app["test_case"]["review_status"] == "APPROVED"
        assert data_app["test_case"]["reviewer"] == "test_reviewer"

        # 5. ATTEMPT UPDATE WHILE APPROVED (Should fail with 400)
        res_lock = client.patch(
            f"/api/cognos/runs/{run.id}/test-cases/PRV027-REPO-01/review",
            json={"action": "UPDATE_SCENARIO", "scenario_data": {"test_case_title": "Illegal Edit"}}
        )
        assert res_lock.status_code == 400
        assert "locked" in res_lock.json()["detail"].lower()

        # 6. CREATE_REVISION (Unlocks scenario)
        res_rev = client.patch(
            f"/api/cognos/runs/{run.id}/test-cases/PRV027-REPO-01/review",
            json={"action": "CREATE_REVISION"}
        )
        assert res_rev.status_code == 200
        data_rev = res_rev.json()
        assert data_rev["test_case"]["review_status"] == "CORRECTED"
        assert data_rev["test_case"]["version"] == 3

        # 7. ADD_MISSING_SCENARIO
        res_add = client.post(
            f"/api/cognos/runs/{run.id}/add-scenario",
            json={
                "scenario": {
                    "test_case_id": "PRV027-RETN-01",
                    "test_case_title": "Verify Report Retention Configuration",
                    "category": "Report Retention Validation",
                    "objective": "Verify 90-day archive purge",
                    "execution_tool": "IWA",
                    "test_steps": "1. Check retention policy.",
                    "expected_result": "Purged after 90 days.",
                }
            }
        )
        assert res_add.status_code == 200
        assert res_add.json()["test_case"]["test_case_id"] == "PRV027-RETN-01"
        assert res_add.json()["test_case"]["review_status"] == "GENERATED"

    finally:
        app.dependency_overrides.clear()
        db.close()
