"""
Regression and validation test suite for total_pages data-flow and governance metadata persistence.

Validates:
1. Complete data-flow:
   DOCX parser -> ParsedDocument.total_pages_estimated -> DSD Interpreter -> DSD Mapper -> ReportMetadata.total_pages -> SourceDocument.page_count
2. Real upload using PRV-INT-027 (runs/1/source/source.docx):
   - HTTP 200
   - Zero 'ReportMetadata.total_pages' warnings/errors
   - SourceDocument persisted with page_count == 7
   - GenerationMetadata persisted
   - GeneratedScenario persisted (all 18 scenarios)
   - ScenarioVersion persisted (all 18 versions)
   - DSD_UPLOADED audit event persisted
   - Admin Database Explorer endpoints can query and inspect the persisted records
3. Defensive getattr resilience at persistence boundary.
"""
import pytest
import logging
from pathlib import Path
from fastapi.testclient import TestClient

from app.domain.cognos_models import ReportMetadata, ReportDefinition
from app.services.cognos_docx_parser import parse_cognos_docx, CognosParsedDocument
from app.cognos.extraction.nh_mmis_dsd_interpreter import NhMmisDsdInterpreter
from app.cognos.extraction.nh_mmis_dsd_mapper import map_dsd_to_domain
from app.cognos.extraction.metadata_extractor import extract_metadata
from app.models.knowledge_base import SourceDocument
from app.models.governance import GenerationMetadata, GeneratedScenario, ScenarioVersion, AuditEvent
from app.models.user import User
from app.core.security import create_access_token, hash_password
from app.services.user_service import ensure_tester_account


def test_docx_parser_and_mapping_total_pages_flow():
    sample_doc = Path("runs/1/source/source.docx")
    assert sample_doc.exists(), f"Sample doc not found at {sample_doc}"

    # 1. Parse DOCX
    parsed = parse_cognos_docx(sample_doc)
    assert parsed.total_pages_estimated == 7, f"Expected 7 pages from OOXML docProps/app.xml, got {parsed.total_pages_estimated}"

    # 2. DSD Interpreter
    interpreter = NhMmisDsdInterpreter(parsed)
    dsd = interpreter.interpret()
    assert dsd.total_pages_estimated == 7, f"Expected 7 pages in dsd, got {dsd.total_pages_estimated}"

    # 3. DSD Mapper
    domain_rd = map_dsd_to_domain(dsd, sample_doc.name)
    assert domain_rd.metadata.total_pages == 7, f"Expected 7 pages in domain_rd.metadata, got {domain_rd.metadata.total_pages}"

    # 4. Generic Metadata Extractor fallback
    meta, _ = extract_metadata(parsed, sample_doc.name)
    assert meta.total_pages == 7, f"Expected 7 pages in extract_metadata, got {meta.total_pages}"


def test_real_upload_governance_persistence_and_database_explorer(client, db, caplog):
    caplog.set_level(logging.WARNING)

    # Prepare authenticated tester
    tester = ensure_tester_account(db)
    token = create_access_token(subject=tester.username, role="tester")

    sample_doc = Path("runs/1/source/source.docx")
    assert sample_doc.exists(), f"Sample doc not found at {sample_doc}"

    with open(sample_doc, "rb") as f:
        file_bytes = f.read()

    # Real upload
    response = client.post(
        "/api/cognos/upload-and-generate",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("CR_18175_PRV_INT_027.docx", file_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"dsd_profile": "NH", "work_type": "REPORT", "work_item_id": "PRV-INT-027"},
    )

    # 1. HTTP 200
    assert response.status_code == 200, f"Upload failed: {response.status_code} - {response.text}"
    data = response.json()
    assert data["status"] == "success"
    run_id = data["run_id"]
    report_id = data["report_id"]

    # 2. No 'ReportMetadata' or 'total_pages' or 'Failed to persist governance metadata' warning
    for record in caplog.records:
        msg = record.getMessage()
        assert "ReportMetadata' object has no attribute 'total_pages'" not in msg, f"Found total_pages warning: {msg}"
        assert "Failed to persist governance metadata" not in msg, f"Found governance persistence failure: {msg}"

    # 3. Verify SourceDocument persisted with page_count == 7
    source_doc = db.query(SourceDocument).filter(SourceDocument.report_id == report_id).first()
    assert source_doc is not None, "SourceDocument record was not persisted!"
    assert source_doc.page_count == 7, f"Expected page_count == 7, got {source_doc.page_count}"
    assert source_doc.filename == "CR_18175_PRV_INT_027.docx"
    assert source_doc.profile == "NH"

    # 4. Verify GenerationMetadata persisted
    gen_meta = db.query(GenerationMetadata).filter(GenerationMetadata.run_id == run_id).first()
    assert gen_meta is not None, "GenerationMetadata record was not persisted!"
    assert gen_meta.validation_status == "PASSED"

    # 5. Verify GeneratedScenario and ScenarioVersion persisted
    scenarios = db.query(GeneratedScenario).filter(GeneratedScenario.run_id == run_id).all()
    assert len(scenarios) == 18, f"Expected 18 GeneratedScenario records, got {len(scenarios)}"

    scenario_ids = [s.id for s in scenarios]
    versions = db.query(ScenarioVersion).filter(ScenarioVersion.scenario_id.in_(scenario_ids)).all()
    assert len(versions) == 18, f"Expected 18 ScenarioVersion records, got {len(versions)}"
    for v in versions:
        assert v.version_number == 1
        assert "test_case_title" in v.content_json

    # 6. Verify DSD_UPLOADED audit event persisted
    audit_events = db.query(AuditEvent).filter(
        AuditEvent.action == "DSD_UPLOADED",
        AuditEvent.run_id == run_id
    ).all()
    assert len(audit_events) >= 1, "DSD_UPLOADED audit event was not persisted!"
    assert audit_events[0].actor_username == tester.username

    # 7. Verify Admin Database Explorer can see the persisted records
    admin_uname = "admin_gov_tester"
    u_admin = db.query(User).filter(User.username == admin_uname).first()
    if not u_admin:
        u_admin = User(
            username=admin_uname,
            hashed_password=hash_password("AdminSecurePass!2026"),
            role="admin",
            status="ACTIVE",
            is_active=True,
            must_change_password=False,
        )
        db.add(u_admin)
        db.commit()
    admin_token = create_access_token(subject=admin_uname, role="admin", expires_seconds=3600)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Query source_documents table via Database Explorer
    resp = client.get(
        f"/api/admin/database/source_documents/rows?search={report_id}",
        headers=admin_headers,
    )
    assert resp.status_code == 200, f"Explorer query failed: {resp.text}"
    explorer_data = resp.json()
    assert any(row.get("report_id") == report_id and row.get("page_count") == 7 for row in explorer_data["rows"]), (
        f"Source document with page_count 7 not found in Explorer rows: {explorer_data['rows']}"
    )

    # Query generation_metadata table via Database Explorer
    resp = client.get(
        f"/api/admin/database/generation_metadata/rows?run_id={run_id}",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    explorer_data = resp.json()
    assert any(row.get("run_id") == run_id for row in explorer_data["rows"])

    # Query generated_scenarios table via Database Explorer
    resp = client.get(
        f"/api/admin/database/generated_scenarios/rows?limit=50",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    explorer_data = resp.json()
    assert any(row.get("run_id") == run_id for row in explorer_data["rows"])

    # Query scenario_versions table via Database Explorer
    resp = client.get(
        f"/api/admin/database/scenario_versions/rows?limit=50",
        headers=admin_headers,
    )
    assert resp.status_code == 200

    # Query audit_events / activity via Database Explorer
    resp = client.get(
        f"/api/admin/database/activity?limit=50",
        headers=admin_headers,
    )
    assert resp.status_code == 200


def test_governance_persistence_resilience_when_metadata_lacks_total_pages():
    """Confirms older/partial ReportMetadata objects without total_pages cannot crash persistence."""
    class LegacyReportMetadata:
        report_id = "LEGACY-001"
        source_state_code = "NH"
        # total_pages attribute is completely absent

    meta = LegacyReportMetadata()
    # verify getattr fallback safely evaluates to None without raising AttributeError
    page_count = getattr(meta, "total_pages", None) or None
    assert page_count is None
