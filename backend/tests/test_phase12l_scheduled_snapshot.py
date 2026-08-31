import pytest
import subprocess
from pathlib import Path
from app.cognos.pipeline import run_cognos_pipeline
from app.cognos.schema.nh_mmis_dsd_models import NhMmisDsd, ReportGeneration, ReportDefinition
from app.services.dsd_snapshot_resolver import DSDSnapshotResolver


def test_dsd_snapshot_resolver_scheduled_metadata():
    resolver = DSDSnapshotResolver(Path("dummy_evidence"))
    dsd = NhMmisDsd(
        report_definition=ReportDefinition(
            client_report_id="PRV-INT-027",
            report_title="Term Date Report",
            source_document="source.docx"
        ),
        report_generation=ReportGeneration(
            report_frequency_type="Scheduled",
            other_explain="Triggered by error execution",
            source_page=1
        )
    )

    snap_ref = resolver.resolve(
        dsd=dsd,
        methodology="SCHEDULED_EXECUTION_VALIDATION",
        test_case_id="PRV027-SCHE-01"
    )

    assert snap_ref is not None
    assert snap_ref.evidence_type == "SOURCE_DSD_SNAPSHOT"
    assert snap_ref.section == "Report Generation"
    assert snap_ref.page_number == 1
    assert snap_ref.evidence_scope == "REPORT_FREQUENCY_SCHEDULING"
    assert snap_ref.target_field == "Scheduled / Report Frequency Type"
    assert "Report Generation • Frequency & Scheduling" in snap_ref.description


def test_pipeline_scheduled_execution_evidence_reference():
    result = run_cognos_pipeline("runs/94/source/source.docx")
    
    sched_cases = [tc for tc in result.test_suite.test_cases if tc.methodology_pattern == "SCHEDULED_EXECUTION_VALIDATION"]
    assert len(sched_cases) == 1
    tc_sched = sched_cases[0]

    # Verify SOURCE_DSD_SNAPSHOT exists (Phase 15.6: standalone source snapshot without semantic proof)
    types = [ev.evidence_type for ev in tc_sched.evidence_references]
    assert "SOURCE_DSD_SNAPSHOT" in types

    # Inspect SOURCE_DSD_SNAPSHOT metadata
    snap_ref = [ev for ev in tc_sched.evidence_references if ev.evidence_type == "SOURCE_DSD_SNAPSHOT"][0]
    assert snap_ref.section == "Report Generation"
    assert snap_ref.evidence_scope == "REPORT_FREQUENCY_SCHEDULING"
    assert snap_ref.target_field == "Scheduled / Report Frequency Type"
    assert "Report Generation • Frequency & Scheduling" in snap_ref.description


def test_render_snapshot_scheduled_crop_execution(tmp_path):
    docx_path = Path("runs/94/source/source.docx")
    if not docx_path.exists():
        pytest.skip("runs/94/source/source.docx not available for render test")

    node_cmd = r"D:\Tools\node-v26.5.0-win-x64\node-v26.5.0-win-x64\node.exe"
    render_script = Path(__file__).parent.parent / "render" / "render_snapshot.js"
    out_png = tmp_path / "test_sched_crop.png"

    args = [
        str(render_script),
        str(docx_path),
        str(out_png),
        "Report Generation",
        "PRV-INT-027",
        "SCHEDULED_EXECUTION_VALIDATION",
        "Scheduled / Report Frequency Type",
        "REPORT_FREQUENCY_SCHEDULING",
    ]

    res = subprocess.run([node_cmd] + args, capture_output=True, text=True, check=True)
    
    stdout = res.stdout
    assert "METHODOLOGY:\nSCHEDULED_EXECUTION_VALIDATION" in stdout
    assert "SOURCE SECTION:\nReport Generation" in stdout
    assert "EVIDENCE SCOPE:\nREPORT_FREQUENCY_SCHEDULING" in stdout
    assert "TARGET:\nScheduled / Report Frequency Type" in stdout
    assert "Report Generation = YES" in stdout
    assert "Report Frequency Type = YES" in stdout
    assert "Scheduled = YES" in stdout
    assert "SNAPSHOT CREATED" in stdout
    assert "clip:" in stdout

    assert out_png.exists()
    assert out_png.stat().st_size > 0
    # Targeted crop is small (~15-30KB) compared to full page (~80-120KB)
    assert out_png.stat().st_size < 50000
