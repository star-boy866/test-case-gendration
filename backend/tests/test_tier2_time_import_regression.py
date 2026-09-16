"""
Focused regression test suite: Tier 2 authentic source DSD rendering.

Validates:
1. `time` module is properly imported and accessible in `dsd_source_snapshot_service`.
2. DOCX -> PDF conversion via LibreOffice succeeds without NameError even when no cached PDF exists.
3. PRV027-RHDR-01 produces an authentic Tier 2 snapshot (renderer=tier2_docx_pdf, authentic=True, is_synthetic=False).
4. Tier 3 synthetic fallback is NOT selected when Tier 2 succeeds.
5. Old/synthetic cache entries are strictly rejected when authentic evidence is requested.
"""
import json
import shutil
import tempfile
from pathlib import Path
import pytest
from PIL import Image

from app.db.session import SessionLocal
from app.models.cognos_orm import CognosGenerationRun
from app.services.dsd_source_snapshot_service import DSDSourceSnapshotService


def test_time_module_availability_in_dsd_service():
    """Confirms `time` module is imported at module scope in dsd_source_snapshot_service."""
    import app.services.dsd_source_snapshot_service as mod
    assert hasattr(mod, "time"), "Module dsd_source_snapshot_service is missing 'time' import!"
    assert callable(mod.time.perf_counter), "time.perf_counter is not callable!"


def test_convert_docx_to_pdf_without_cached_pdf():
    """
    Verifies that converting a DOCX where no pre-existing .pdf exists
    executes LibreOffice and returns a valid PDF without raising NameError ('time').
    """
    sample_docx = Path("runs/1/source/source.docx")
    assert sample_docx.exists(), f"Sample docx not found at {sample_docx}"

    soffice = DSDSourceSnapshotService._find_soffice_binary()
    if not soffice:
        pytest.skip("LibreOffice binary not found in environment")

    with tempfile.TemporaryDirectory() as td:
        temp_src = Path(td) / "uncached_sample.docx"
        shutil.copy(sample_docx, temp_src)

        pdf_path = DSDSourceSnapshotService.convert_docx_to_pdf(temp_src)
        assert pdf_path is not None, "DOCX -> PDF conversion returned None!"
        assert pdf_path.exists(), f"Converted PDF does not exist at {pdf_path}"
        assert pdf_path.stat().st_size > 10000, f"PDF file size too small: {pdf_path.stat().st_size} bytes"


def test_tier2_authentic_rhdr_rendering_and_synthetic_rejection():
    """
    Verifies that PRV027-RHDR-01 renders via Tier 2 (pypdfium2 crop)
    with authentic=True, correct dimensions, and NOT tier3_synthetic.
    """
    db = SessionLocal()
    try:
        run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == 1).first()
        if not run:
            pytest.skip("Run 1 not present in application database")

        snap_path = DSDSourceSnapshotService.get_or_generate_snapshot(
            db=db,
            run_id=1,
            evidence_id="snapshot_PRV027-RHDR-01_RHDR",
            section="Report Layout",
            methodology="REPORT_HEADER_VALIDATION",
            target_field="Report Header",
            evidence_scope="RHDR",
            test_case_id="PRV027-RHDR-01",
        )

        assert snap_path.exists(), f"Snapshot does not exist at {snap_path}"
        assert snap_path.stat().st_size > 0, "Snapshot is empty"

        # Verify dimensions
        with Image.open(snap_path) as img:
            w, h = img.size
            assert w > 500 and h > 100, f"Unexpectedly small dimensions: ({w}, {h})"
            # Verify it is not a full-page uncrop or synthetic card
            assert (w, h) != (1200, 800), "Synthetic card dimensions (1200, 800) detected!"

        # Verify not synthetic
        assert not DSDSourceSnapshotService.is_synthetic_card(snap_path), "Snapshot was flagged as synthetic card!"

        # Verify sidecar provenance metadata
        meta_p = snap_path.with_suffix(".meta.json")
        assert meta_p.exists(), f"Sidecar metadata missing at {meta_p}"
        with open(meta_p) as f:
            meta = json.load(f)

        assert meta.get("renderer") in ("tier2_docx_pdf", "cached_authentic"), f"Unexpected renderer: {meta.get('renderer')}"
        assert meta.get("authentic") is True, f"Expected authentic=True, got {meta.get('authentic')}"
        assert meta.get("is_semantic_crop") is True, "Expected is_semantic_crop=True"
        assert meta.get("test_case_id") == "PRV027-RHDR-01"
    finally:
        db.close()


def test_old_synthetic_cache_is_rejected():
    """
    Verifies that find_cached_snapshot and is_synthetic_card strictly reject
    synthetic cache artifacts when authentic evidence is required.
    """
    # 1. Test is_synthetic_card detection on a synthesized metadata card
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        fake_png = temp_dir / "source_snapshot_test_synthetic.png"
        fake_meta = temp_dir / "source_snapshot_test_synthetic.meta.json"

        img = Image.new("RGB", (1280, 800), color=(15, 23, 42))
        img.save(fake_png)

        with open(fake_meta, "w") as f:
            json.dump({
                "filename": fake_png.name,
                "renderer": "tier3_synthetic",
                "authentic": False,
                "page_number": 1,
                "crop_version": DSDSourceSnapshotService.CURRENT_CROP_VERSION,
                "renderer_version": DSDSourceSnapshotService.CURRENT_RENDERER_VERSION,
                "is_semantic_crop": False,
            }, f)

        assert DSDSourceSnapshotService.is_synthetic_card(fake_png) is True

    # 2. Test rejection via find_cached_snapshot using a synthetic metadata tag
    candidate_dirs = DSDSourceSnapshotService.get_candidate_runs_dirs()
    if candidate_dirs:
        target_dir = candidate_dirs[0] / "99999" / "evidence"
        target_dir.mkdir(parents=True, exist_ok=True)
        test_png = target_dir / "source_snapshot_test_synthetic_rejection.png"
        test_meta = target_dir / "source_snapshot_test_synthetic_rejection.meta.json"
        try:
            img = Image.new("RGB", (1584, 400), color=(255, 255, 255))
            img.save(test_png)
            with open(test_meta, "w") as f:
                json.dump({
                    "filename": test_png.name,
                    "renderer": "tier3_synthetic",
                    "authentic": False,
                    "page_number": 1,
                    "crop_version": DSDSourceSnapshotService.CURRENT_CROP_VERSION,
                    "renderer_version": DSDSourceSnapshotService.CURRENT_RENDERER_VERSION,
                    "is_semantic_crop": True,
                }, f)

            cached = DSDSourceSnapshotService.find_cached_snapshot(
                run_id=99999,
                png_filename=test_png.name,
                require_authentic=True,
            )
            assert cached is None, f"Expected synthetic cache to be rejected, but got {cached}"
        finally:
            shutil.rmtree(candidate_dirs[0] / "99999", ignore_errors=True)
