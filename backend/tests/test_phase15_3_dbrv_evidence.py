import pytest
from pathlib import Path
from app.cognos.pipeline import run_cognos_pipeline
from app.services.dsd_snapshot_resolver import DSDSnapshotResolver

def test_phase15_3_dbrv_evidence_resolution():
    source_path = Path("runs/210/source/source.docx")
    if not source_path.exists():
        source_path = Path("tests/fixtures/golden_sources/PRV-INT-027_DSD.docx")

    res = run_cognos_pipeline(source_path)
    test_cases = res.test_suite.test_cases

    dbrv = next(tc for tc in test_cases if tc.test_case_id == "PRV027-DBRV-01")
    assert dbrv is not None
    assert dbrv.category == "DB Report Data Validation"

    # Find SOURCE_DSD_SNAPSHOT evidence reference
    snap_ref = next((ev for ev in dbrv.evidence_references if ev.evidence_type == "SOURCE_DSD_SNAPSHOT"), None)
    assert snap_ref is not None, "Missing SOURCE_DSD_SNAPSHOT evidence on DBRV-01"

    # Verify metadata
    assert snap_ref.section == "Report Body"
    assert snap_ref.evidence_scope == "REPORT_BODY_MAPPING"
    assert snap_ref.target_field == "Full Mapping"
    assert "Full Mapping" in snap_ref.description
    assert "Report Body" in snap_ref.description
    assert "prov id" not in snap_ref.description.lower()
    assert snap_ref.page_number == 9 or snap_ref.page_number == "9"
