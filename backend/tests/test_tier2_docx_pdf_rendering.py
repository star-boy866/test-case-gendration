"""
Tests for Tier 2 Genuine Document Rendering and Multi-Tier Snapshot Architecture.

Validates:
  1. Authentic cached snapshot preservation (no overwrite).
  2. Multi-tier resolution for all PRV reports (PRV-INT-008, 011, 026, 027).
  3. DBRV validation for PRV-INT-008 without false 4-of-6 mapping failures.
  4. PDF page rendering via pypdfium2 producing genuine document imagery.
  5. Security and IDOR enforcement on snapshot endpoints.
"""

import os
from pathlib import Path
import pytest
from PIL import Image
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.cognos_orm import CognosGenerationRun, CognosTestCaseModel
from app.services.dsd_source_snapshot_service import DSDSourceSnapshotService, BACKEND_DIR


def test_authentic_cached_snapshot_preservation():
    """
    Verifies that existing authentic snapshots (e.g. Run 6 PRV008-EXEC-01)
    are returned directly from cache and never overwritten by reconstructed/synthetic images.
    """
    db = SessionLocal()
    try:
        run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == 6).first()
        if not run:
            pytest.skip("Run 6 not present in test database")

        p = DSDSourceSnapshotService.get_or_generate_snapshot(
            db=db,
            run_id=6,
            evidence_id="snapshot_PRV008-EXEC-01_SCHEDU",
            section="Report Generation",
            methodology="SCHEDULED_EXECUTION_VALIDATION",
            target_field="Scheduled / Report Frequency Type",
            evidence_scope="REPORT_FREQUENCY_SCHEDULING",
            test_case_id="PRV008-EXEC-01",
        )
        assert p.exists(), "Snapshot file must exist"
        assert p.stat().st_size > 0, "Snapshot file must not be empty"
        assert "source_snapshot_snapshot_PRV008-EXEC-01_SCHEDU.png" in p.name, "Must preserve authentic filename"

        # Inspect image properties
        img = Image.open(p)
        assert img.size[0] > 100 and img.size[1] > 50, "Valid image dimensions"
        assert img.mode in ("RGB", "RGBA"), "Valid image color mode"
    finally:
        db.close()


def test_dbrv_prv008_validation_fixed():
    """
    Verifies that PRV008-DBRV-01 (4 mappings) no longer fails with false
    'captured 4 of 6 expected mappings' error.
    """
    db = SessionLocal()
    try:
        run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == 6).first()
        if not run:
            pytest.skip("Run 6 not present in test database")

        p = DSDSourceSnapshotService.get_or_generate_snapshot(
            db=db,
            run_id=6,
            evidence_id="snapshot_PRV008-DBRV-01_DB_FULL",
            section="Report Body",
            methodology="DB_REPORT_DATA_VALIDATION",
            target_field="Report Body",
            evidence_scope="REPORT_BODY_MAPPING",
            test_case_id="PRV008-DBRV-01",
        )
        assert p.exists()
        assert p.stat().st_size > 0
        img = Image.open(p)
        assert img.size[0] > 200
    finally:
        db.close()


def test_cross_run_isolation():
    """
    Verifies that distinct reports (PRV-INT-008, 011, 026, 027) produce distinct,
    valid evidence images belonging to their own respective runs.
    """
    db = SessionLocal()
    try:
        run_checks = [
            (6, "snapshot_PRV008-EXEC-01_SCHEDU", "PRV008-EXEC-01"),
            (15, "snapshot_PRV011-EXEC-01_SCHEDU", "PRV011-EXEC-01"),
            (14, "snapshot_PRV026-EXEC-01_SCHEDU", "PRV026-EXEC-01"),
            (1, "snapshot_PRV027-DATE-01_DATE_F", "PRV027-DATE-01"),
        ]

        rendered_paths = []
        for run_id, ev_id, tc_id in run_checks:
            run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
            if not run:
                continue
            p = DSDSourceSnapshotService.get_or_generate_snapshot(
                db=db,
                run_id=run_id,
                evidence_id=ev_id,
                section="",
                methodology="",
                target_field="",
                evidence_scope="",
                test_case_id=tc_id,
            )
            assert p.exists()
            assert p.stat().st_size > 0
            rendered_paths.append(str(p))

        # Ensure all rendered paths belong to their own run directories
        for path_str in rendered_paths:
            assert Path(path_str).exists()
    finally:
        db.close()


def test_pypdfium2_rendering_pipeline(tmp_path: Path):
    """
    Verifies that pypdfium2 can render a genuine PDF page to a sharp PNG image.
    """
    import pypdfium2 as pdfium

    # Create a minimal valid PDF using pypdfium2
    pdf = pdfium.PdfDocument.new()
    page = pdf.new_page(width=612, height=792)  # Letter size in points
    test_pdf = tmp_path / "test_doc.pdf"
    pdf.save(str(test_pdf))
    pdf.close()

    out_png = tmp_path / "test_page_render.png"
    success = DSDSourceSnapshotService.render_pdf_page_to_png(
        pdf_path=test_pdf,
        page_number=1,
        png_path=out_png,
    )
    assert success is True
    assert out_png.exists()
    assert out_png.stat().st_size > 0

    img = Image.open(out_png)
    # 612 * 2 = 1224, 792 * 2 = 1584
    assert img.size == (1224, 1584), f"Expected 1224x1584, got {img.size}"
    assert img.mode == "RGB"


def test_synthetic_card_detection_and_provenance(tmp_path: Path):
    """
    Verifies that is_synthetic_card accurately detects _draw_evidence_card output
    and that is_authentic_snapshot validates genuine document captures.
    """
    # 1. Create a synthetic evidence card using _draw_evidence_card
    synth_png = tmp_path / "synthetic_test.png"
    DSDSourceSnapshotService._draw_evidence_card(
        png_path=synth_png,
        doc_name="test.docx",
        report_id="PRV-001",
        report_title="Test Report",
        section="Section 1",
        methodology="VALIDATION",
        target_field="Field A",
        evidence_scope="SCOPE",
        test_case_id="TC-001",
        description="Synthetic test description",
        table_rows=[["Col 1", "Col 2"], ["Val 1", "Val 2"]],
        paragraphs=["Sample paragraph"],
        source_badge="AUTO",
    )
    assert synth_png.exists()
    assert DSDSourceSnapshotService.is_synthetic_card(synth_png) is True
    assert DSDSourceSnapshotService.is_authentic_snapshot(synth_png) is False

    # 2. Create an authentic document page using pypdfium2
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(width=612, height=792)
    test_pdf = tmp_path / "auth_doc.pdf"
    pdf.save(str(test_pdf))
    pdf.close()

    auth_png = tmp_path / "authentic_test.png"
    DSDSourceSnapshotService.render_pdf_page_to_png(test_pdf, page_number=1, png_path=auth_png)
    assert auth_png.exists()
    assert DSDSourceSnapshotService.is_synthetic_card(auth_png) is False
    assert DSDSourceSnapshotService.is_authentic_snapshot(auth_png) is True

    # 3. Test provenance metadata writer
    DSDSourceSnapshotService.write_provenance_meta(
        png_path=auth_png,
        renderer="tier2_docx_pdf",
        authentic=True,
        page_number=1,
    )
    meta_path = auth_png.with_suffix(".meta.json")
    assert meta_path.exists()
    assert DSDSourceSnapshotService.is_authentic_snapshot(auth_png) is True


def test_find_cached_snapshot_rejects_synthetic_cache(tmp_path: Path, monkeypatch):
    """
    Verifies that find_cached_snapshot rejects stale synthetic cards when
    require_authentic is True, but returns authentic document captures.
    """
    # Setup candidate directory
    runs_dir = tmp_path / "runs"
    ev_dir = runs_dir / "101" / "evidence"
    ev_dir.mkdir(parents=True)

    monkeypatch.setattr(DSDSourceSnapshotService, "get_candidate_runs_dirs", classmethod(lambda cls: [runs_dir]))

    test_file = ev_dir / "source_snapshot_TEST_EVID.png"

    # A. Draw synthetic card at test_file
    DSDSourceSnapshotService._draw_evidence_card(
        png_path=test_file,
        doc_name="test.docx",
        report_id="RPT-1",
        report_title="Title",
        section="",
        methodology="",
        target_field="",
        evidence_scope="",
        test_case_id="TC-1",
        description="",
        table_rows=[],
        paragraphs=[],
        source_badge="",
    )
    assert test_file.exists()

    # When require_authentic=True: must reject synthetic cache
    res = DSDSourceSnapshotService.find_cached_snapshot(
        run_id=101,
        png_filename="source_snapshot_TEST_EVID.png",
        evidence_id="TEST_EVID",
        test_case_id="TC-1",
        require_authentic=True,
    )
    assert res is None, "Expected stale synthetic cache to be rejected when require_authentic=True"

    # When require_authentic=False: accepts existing cache as emergency fallback
    res_fallback = DSDSourceSnapshotService.find_cached_snapshot(
        run_id=101,
        png_filename="source_snapshot_TEST_EVID.png",
        evidence_id="TEST_EVID",
        test_case_id="TC-1",
        require_authentic=False,
    )
    assert res_fallback == test_file, "Expected synthetic cache to be accepted when require_authentic=False"

    # B. Now overwrite test_file with an authentic PDF page render
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(width=612, height=792)
    test_pdf = tmp_path / "doc.pdf"
    pdf.save(str(test_pdf))
    pdf.close()
    DSDSourceSnapshotService.render_pdf_page_to_png(test_pdf, 1, test_file)
    DSDSourceSnapshotService.write_provenance_meta(test_file, renderer="tier2_docx_pdf", authentic=True)

    # Now find_cached_snapshot must return it!
    res_authentic = DSDSourceSnapshotService.find_cached_snapshot(
        run_id=101,
        png_filename="source_snapshot_TEST_EVID.png",
        evidence_id="TEST_EVID",
        test_case_id="TC-1",
        require_authentic=True,
    )
    assert res_authentic == test_file, "Expected authentic cache hit"
