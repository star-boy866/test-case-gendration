"""
Test Suite: Real Application Persistence Lifecycle and Admin Database Explorer Visibility.

Verifies end-to-end data lifecycle:
1. Create/login test user
2. Upload/register test source document
3. Create generation run
4. Generate scenario
5. Edit scenario
6. Create scenario version record
7. Approve scenario & record feedback
8. Create audit event
9. Create evidence/source snapshot record
10. Query those records from Admin Database Explorer and verify consistency
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.cognos_orm import CognosGenerationRun, CognosTestCaseModel
from app.models.knowledge_base import SourceDocument
from app.models.governance import (
    AuditEvent, GeneratedScenario, ScenarioVersion, ScenarioFeedback, SourceSnapshot
)
from app.core.security import hash_password, create_access_token


def test_complete_persistence_and_explorer_lifecycle(client: TestClient, db: Session):
    # 1. Create/login test admin
    admin_uname = "lifecycle_admin_user"
    u_admin = db.query(User).filter(User.username == admin_uname).first()
    if not u_admin:
        u_admin = User(
            username=admin_uname,
            hashed_password=hash_password("LifecycleAdminPass2026!"),
            role="admin",
            status="ACTIVE",
            is_active=True,
            must_change_password=False,
        )
        db.add(u_admin)
        db.commit()
        db.refresh(u_admin)
    token = create_access_token(subject=admin_uname, role="admin", expires_seconds=3600)
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Register test source document
    doc = SourceDocument(
        report_id="PRV-INT-009",
        filename="PRV009_Lifecycle_Test_DSD.docx",
        file_sha256="sha256_mock_hash_lifecycle_123456",
        file_type="docx",
        uploaded_by=admin_uname,
    )

    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 3. Create generation run
    run = CognosGenerationRun(
        report_id="PRV-INT-009",
        source_document="PRV009_Lifecycle_Test_DSD.docx",
        requested_by=admin_uname,
        status="completed",
        test_cases_generated=1,
    )
    db.add(run)
    db.commit()
    db.refresh(run)



    # 4. Generate scenario in both Studio test cases and Governance generated_scenarios
    tc = CognosTestCaseModel(
        run_id=run.id,
        test_case_id="PRV009-LIFECYCLE-01",
        report_id="PRV-INT-009",
        category="SELECTION_CRITERIA_VALIDATION",
        test_case_title="Provider License Selection Lifecycle Scenario",
        objective="Validate provider license criteria",
        test_steps="1. Query licenses 2. Compare criteria",
        expected_result="Passes criteria",
        source_section="Selection Criteria",
        priority="High",
        origin="GENERATED",
        review_status="GENERATED",
    )
    db.add(tc)

    gen_scen = GeneratedScenario(
        run_id=run.id,
        test_case_id="PRV009-LIFECYCLE-01",
        scenario_name="Provider License Selection Lifecycle Scenario",
        methodology="SELECTION_CRITERIA_VALIDATION",
        section="Selection Criteria",
        target_field="Provider License",
        status="GENERATED",
        created_by="system_pipeline",
    )
    db.add(gen_scen)
    db.commit()
    db.refresh(tc)
    db.refresh(gen_scen)

    # 5. Edit scenario & 6. Create scenario versions
    v1 = ScenarioVersion(
        scenario_id=gen_scen.id,
        test_case_id="PRV009-LIFECYCLE-01",
        version_number=1,
        source="AI_GENERATED",
        changed_by="system_pipeline",
        change_reason="Initial automated synthesis",
        content_json={"title": tc.test_case_title, "category": tc.category, "status": "GENERATED"},
    )
    db.add(v1)

    tc.test_case_title = "Provider License Selection Lifecycle Scenario - Corrected"
    tc.review_status = "CORRECTED"
    gen_scen.scenario_name = tc.test_case_title
    gen_scen.status = "CORRECTED"
    db.commit()

    v2 = ScenarioVersion(
        scenario_id=gen_scen.id,
        test_case_id="PRV009-LIFECYCLE-01",
        version_number=2,
        source="TESTER_CORRECTION",
        changed_by="qa_tester",
        change_reason="Refined selection criteria rule bounds",
        content_json={"title": tc.test_case_title, "category": tc.category, "status": "CORRECTED"},
    )
    db.add(v2)
    db.commit()

    # 7. Approve scenario & record feedback
    tc.review_status = "APPROVED"
    gen_scen.status = "APPROVED"
    db.commit()

    fb = ScenarioFeedback(
        scenario_id=gen_scen.id,
        username="qa_lead",
        feedback_type="APPROVED",
        comment="Verified against DSD Section 34.3.79.1.1",
        changed_fields={"review_status": "APPROVED"},
    )
    db.add(fb)
    db.commit()


    # 8. Create audit event
    ev = AuditEvent(
        actor_username=admin_uname,
        actor_role="admin",
        action="ADMIN_DATABASE_TABLE_VIEWED",
        resource_type="DATABASE_TABLE",
        resource_id="cognos_test_cases",
        details={"table": "cognos_test_cases", "scenario": "PRV009-LIFECYCLE-01", "rows_returned": 1},
        success=True,
    )
    db.add(ev)
    db.commit()

    # 9. Create evidence source snapshot
    snap = SourceSnapshot(
        source_document_id=doc.id,
        run_id=run.id,
        scenario_id="PRV009-LIFECYCLE-01",
        evidence_id="snapshot_PRV009-LIFECYCLE-01_SELC",
        page_number=3,
        semantic_target="Provider License Selection Criteria",
        crop_box=[72, 140, 540, 320],
        renderer="v8_pypdfium2_semantic_crop",
        crop_version="v8_exact_semantic_region",
        snapshot_hash="hash_lifecycle_snap_123",
        is_semantic_crop=True,
        file_path="/mock/snapshots/snapshot_PRV009-LIFECYCLE-01_SELC.png",
    )
    db.add(snap)
    db.commit()

    # 10. Query all those records through Admin Database Explorer
    # A. Query scenario row
    resp_rows = client.get("/api/admin/database/cognos_test_cases/rows?search=PRV009-LIFECYCLE-01", headers=headers)
    assert resp_rows.status_code == 200
    rows_data = resp_rows.json()
    assert rows_data["total_rows"] >= 1
    found_tc = next((r for r in rows_data["rows"] if r.get("test_case_id") == "PRV009-LIFECYCLE-01"), None)
    assert found_tc is not None
    assert found_tc["review_status"] == "APPROVED"

    # B. Query scenario versions
    resp_versions = client.get("/api/admin/database/scenario-versions/PRV009-LIFECYCLE-01", headers=headers)
    assert resp_versions.status_code == 200
    ver_data = resp_versions.json()
    assert ver_data["total_versions"] == 2
    sources = [v["source"] for v in ver_data["versions"]]
    assert "AI_GENERATED" in sources
    assert "TESTER_CORRECTION" in sources

    # C. Query source snapshots
    resp_snaps = client.get("/api/admin/database/source-snapshots?scenario_id=PRV009-LIFECYCLE-01", headers=headers)
    assert resp_snaps.status_code == 200
    snaps_data = resp_snaps.json()
    assert snaps_data["total"] >= 1
    found_snap = next((s for s in snaps_data["snapshots"] if s.get("evidence_id") == "snapshot_PRV009-LIFECYCLE-01_SELC"), None)
    assert found_snap is not None
    assert found_snap["page"] == 3
    assert found_snap["renderer"] == "v8_pypdfium2_semantic_crop"

    # D. Query database activity
    resp_act = client.get("/api/admin/database/activity", headers=headers)
    assert resp_act.status_code == 200
    act_data = resp_act.json()
    assert act_data["total"] >= 1

    # Cleanup lifecycle test records
    db.delete(snap)
    db.delete(ev)
    db.delete(fb)
    db.delete(v2)
    db.delete(v1)
    db.delete(gen_scen)
    db.delete(tc)
    db.delete(run)
    db.delete(doc)
    db.delete(u_admin)
    db.commit()
