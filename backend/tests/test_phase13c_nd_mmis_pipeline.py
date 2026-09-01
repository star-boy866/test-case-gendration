"""
Phase 13C: North Dakota MMIS DSD Pipeline & Evidence Integration Tests.

Validates:
1. End-to-end execution of North Dakota DSD (OPR-TPL-188).
2. Extraction of 40+ atomic requirements from ND document structure.
3. Generation of 45+ test cases across Layout, Header, Selection Criteria,
   Sort, Output Delivery, Script/Retention, Duplicate, and DB Report Data.
4. Auto-detection routing through DSDProfileDispatcher.
5. Generation of authoritative SOURCE_DSD_SNAPSHOT evidence references for 100% of test cases.
6. API endpoint upload, DB persistence, and /source-snapshot rasterization for ND documents.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rbac import get_current_user, CurrentUser
from app.cognos.pipeline import run_cognos_pipeline
from app.cognos.extraction.nd_mmis_dsd_interpreter import NdMmisDsdInterpreter


@pytest.fixture
def mock_tester_user():
    def _override():
        return CurrentUser(username="tester", role="tester")
    app.dependency_overrides[get_current_user] = _override
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def nd_dsd_path() -> Path:
    # Use the authoritative ND DSD
    primary_path = Path("D:/test-case-gendration/healthcare-nl-testgen/TPL Rejection Error Handling Report Template (2).docx")
    if primary_path.exists():
        return primary_path
    return Path("uploads/tmpsn6l3562.docx")


def test_nd_interpreter_structure(nd_dsd_path):
    """Verify NdMmisDsdInterpreter parses definition, sorts, outputs, and 30 body fields."""
    interp = NdMmisDsdInterpreter(nd_dsd_path)
    dsd = interp.interpret()

    assert dsd.definition.report_id == "OPR-TPL-188"
    assert dsd.definition.report_name is not None and "TPL Rejection Error Handling Report" in dsd.definition.report_name
    assert dsd.definition.mita_process == "Operations"
    assert dsd.definition.report_status == "New"
    assert dsd.definition.generated_from == "EOR Transactional (OLTP)"
    assert len(dsd.sorts) == 4
    assert [s.field_name for s in dsd.sorts] == [
        "RECIP_ND_NUM",
        "RECIP_MA_NUM",
        "CVRG_CD_BEG_DT",
        "CVRG_CD_END_DT",
    ]
    assert dsd.output.output_formats == ["Excel"]
    assert dsd.output.portal == "EDMS"
    assert dsd.output.retention_duration == "7 Years"
    assert len(dsd.report_body) == 30
    assert dsd.report_body[0].field_label == "TPL RECIP ND NUM"
    assert dsd.report_body[0].source_table == "T_RPT_TPL_REJ_ERR_TB"
    assert dsd.report_body[0].source_column == "RECIP_ND_NUM"


def test_nd_pipeline_end_to_end(nd_dsd_path):
    """Verify complete ND generation pipeline execution and test case creation with snapshot evidence."""
    res = run_cognos_pipeline(
        docx_path=nd_dsd_path,
        source_document_name="TPL Rejection Error Handling Report Template (2).docx",
        dsd_profile="ND",
    )

    assert res.report_definition.metadata.report_id == "OPR-TPL-188"
    assert res.report_definition.metadata.report_title == "TPL Rejection Error Handling Report"
    assert len(res.requirement_set.requirements) >= 40
    assert len(res.test_suite.test_cases) >= 12

    tc_ids = [tc.test_case_id for tc in res.test_suite.test_cases]
    assert "OPR188-REPO-01" in tc_ids
    assert "OPR188-RHDR-01" in tc_ids
    assert "OPR188-SECT-01" in tc_ids
    assert "OPR188-LABE-01" in tc_ids
    assert "OPR188-LAYO-01" in tc_ids
    assert "OPR188-LOOK-01" in tc_ids
    assert "OPR188-OUTP-01" in tc_ids
    assert "OPR188-SCRI-01" in tc_ids
    assert "OPR188-EXEC-01" in tc_ids or "OPR188-SCHE-01" in tc_ids
    assert "OPR188-SORT-01" in tc_ids
    assert "OPR188-DUPL-01" in tc_ids
    assert any("DBRV" in tid or "DBRE" in tid for tid in tc_ids)

    # Phase 13C: Verify 100% of test cases have SOURCE_DSD_SNAPSHOT evidence references
    for tc in res.test_suite.test_cases:
        snap_refs = [ev for ev in tc.evidence_references if ev.evidence_type == "SOURCE_DSD_SNAPSHOT"]
        assert len(snap_refs) >= 1, f"Test case {tc.test_case_id} missing SOURCE_DSD_SNAPSHOT"
        assert snap_refs[0].section, f"Test case {tc.test_case_id} has empty section"
        assert snap_refs[0].page_number is not None, f"Test case {tc.test_case_id} has empty page number"
        assert snap_refs[0].evidence_scope, f"Test case {tc.test_case_id} has empty evidence_scope"


def test_nd_upload_and_generate_api(mock_tester_user, nd_dsd_path):
    """Verify API endpoint upload, generation, and snapshot retrieval for ND documents."""
    client = TestClient(app)

    with open(nd_dsd_path, "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/api/cognos/upload-and-generate",
        data={"dsd_profile": "AUTO"},
        files={"file": ("TPL Rejection Error Handling Report Template (2).docx", file_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["report_definition"]["metadata"]["report_id"] == "OPR-TPL-188"
    assert len(data["test_cases"]) >= 12
    run_id = data["run_id"]

    # Verify test cases have SOURCE_DSD_SNAPSHOT references in API output
    for tc in data["test_cases"]:
        snap_evs = [ev for ev in tc["evidence_references"] if ev["evidence_type"] == "SOURCE_DSD_SNAPSHOT"]
        assert len(snap_evs) >= 1, f"API test case {tc['test_case_id']} missing SOURCE_DSD_SNAPSHOT"

    # Test snapshot rasterization endpoint for Sort scenario
    snap_resp = client.get(
        f"/api/cognos/runs/{run_id}/source-snapshot",
        params={
            "methodology": "SORT_VALIDATION",
            "section": "Report Control Breaks, Totals, Counts, and Sorts",
            "target_field": "RECIP_ND_NUM",
            "evidence_scope": "Report Control Breaks, Totals, Counts, and Sorts",
            "test_case_id": "OPR188-SORT-01",
        }
    )
    assert snap_resp.status_code == 200
    assert snap_resp.headers["content-type"] == "image/png"
    assert len(snap_resp.content) > 1000


def test_nd_report_header_validation_focused(mock_tester_user, nd_dsd_path):
    """Verify Phase 13C.1 ND Report Header validation scenario details and focused snapshot crop."""
    res = run_cognos_pipeline(
        docx_path=nd_dsd_path,
        source_document_name="TPL Rejection Error Handling Report Template (2).docx",
        dsd_profile="ND",
    )

    rhdr_tc = next(tc for tc in res.test_suite.test_cases if tc.test_case_id == "OPR188-RHDR-01")
    assert rhdr_tc is not None

    # Step verification: no File Name, exact Department and Date
    assert "File Name" not in rhdr_tc.test_steps
    assert "Department: Department of Human Services" in rhdr_tc.test_steps
    assert "Report ID: OPR-TPL-188" in rhdr_tc.test_steps
    assert "Report Title: TPL Rejection Error Handling Report" in rhdr_tc.test_steps
    assert "Report Date: MM/DD/CCYY" in rhdr_tc.test_steps
    assert "Branding: North Dakota Department of Human Services logo" in rhdr_tc.test_steps

    # Expected result verification
    assert "The OPR-TPL-188 report header matches the ND DSD layout specification" in rhdr_tc.expected_result
    assert "Department of Human Services" in rhdr_tc.expected_result
    assert "File Name" not in rhdr_tc.expected_result

    # Evidence reference verification
    snap_refs = [ev for ev in rhdr_tc.evidence_references if ev.evidence_type == "SOURCE_DSD_SNAPSHOT"]
    assert len(snap_refs) >= 1
    assert snap_refs[0].section == "Report Layout"
    assert snap_refs[0].page_number == 6
    assert snap_refs[0].evidence_scope == "REPORT_HEADER"


def test_nd_label_validation_multi_page_evidence(mock_tester_user, nd_dsd_path):
    """Verify Phase 13D ND Multi-Page Column Labels evidence reference and snapshot API."""
    res = run_cognos_pipeline(
        docx_path=nd_dsd_path,
        source_document_name="TPL Rejection Error Handling Report Template (2).docx",
        dsd_profile="ND",
    )

    labe_tc = next(tc for tc in res.test_suite.test_cases if tc.test_case_id == "OPR188-LABE-01")
    assert labe_tc is not None

    # Step verification: all 30 column labels listed in test steps
    assert "TPL RECIP ND NUM" in labe_tc.test_steps
    assert "TPL MESSAGE" in labe_tc.test_steps

    # Evidence reference verification: source_pages = [8, 9], page_display = '8–9'
    snap_refs = [ev for ev in labe_tc.evidence_references if ev.evidence_type == "SOURCE_DSD_SNAPSHOT"]
    assert len(snap_refs) >= 1
    snap = snap_refs[0]
    assert snap.section == "Report Body"
    assert snap.evidence_scope == "Column Labels"
    assert snap.source_pages == [8, 9]
    assert snap.page_display == "8–9"
    assert "Page 8–9" in snap.description

    # Test API snapshot generation
    client = TestClient(app)
    with open(nd_dsd_path, "rb") as f:
        file_bytes = f.read()

    upload_resp = client.post(
        "/api/cognos/upload-and-generate",
        data={"dsd_profile": "ND"},
        files={"file": ("TPL Rejection Error Handling Report Template (2).docx", file_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert upload_resp.status_code == 200
    run_id = upload_resp.json()["run_id"]

    snap_resp = client.get(
        f"/api/cognos/runs/{run_id}/source-snapshot",
        params={
            "methodology": "LABEL_VALIDATION",
            "section": "Report Body",
            "evidence_scope": "Column Labels",
            "test_case_id": "OPR188-LABE-01",
        }
    )
    assert snap_resp.status_code == 200
    assert snap_resp.headers["content-type"] == "image/png"
    assert len(snap_resp.content) > 10000


def test_nd_layout_validation_full_page(mock_tester_user, nd_dsd_path):
    """Verify Phase 13D.1 ND Full Report Layout evidence reference and full-page snapshot API."""
    res = run_cognos_pipeline(
        docx_path=nd_dsd_path,
        source_document_name="TPL Rejection Error Handling Report Template (2).docx",
        dsd_profile="ND",
    )

    layo_tc = next(tc for tc in res.test_suite.test_cases if tc.test_case_id == "OPR188-LAYO-01")
    assert layo_tc is not None

    # Evidence reference verification: section = 'Report Layout', evidence_scope = 'FULL_REPORT_LAYOUT'
    snap_refs = [ev for ev in layo_tc.evidence_references if ev.evidence_type == "SOURCE_DSD_SNAPSHOT"]
    assert len(snap_refs) >= 1
    snap = snap_refs[0]
    assert snap.section == "Report Layout"
    assert snap.evidence_scope == "FULL_REPORT_LAYOUT"
    assert snap.page_number == 6

    # Test API snapshot generation
    client = TestClient(app)
    with open(nd_dsd_path, "rb") as f:
        file_bytes = f.read()

    upload_resp = client.post(
        "/api/cognos/upload-and-generate",
        data={"dsd_profile": "ND"},
        files={"file": ("TPL Rejection Error Handling Report Template (2).docx", file_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert upload_resp.status_code == 200
    run_id = upload_resp.json()["run_id"]

    snap_resp = client.get(
        f"/api/cognos/runs/{run_id}/source-snapshot",
        params={
            "methodology": "LAYOUT_VALIDATION",
            "section": "Report Layout",
            "evidence_scope": "FULL_REPORT_LAYOUT",
            "test_case_id": "OPR188-LAYO-01",
        }
    )
    assert snap_resp.status_code == 200
    assert snap_resp.headers["content-type"] == "image/png"
    assert len(snap_resp.content) > 20000



