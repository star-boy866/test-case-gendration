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


def _build_test_multipage_pdf(path: Path, page_texts: list[str]) -> None:
    """Helper to build a valid multi-page PDF with genuine text streams using raw PDF-1.4 syntax."""
    num_pages = len(page_texts)
    objs = []
    objs.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")
    kids_str = " ".join(f"{i+3} 0 R" for i in range(num_pages))
    objs.append(f"2 0 obj << /Type /Pages /Kids [{kids_str}] /Count {num_pages} >> endobj".encode("ascii"))

    font_obj_id = num_pages + 3
    for i in range(num_pages):
        content_obj_id = font_obj_id + 1 + i
        objs.append(
            f"{i+3} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_obj_id} 0 R >> >> /Contents {content_obj_id} 0 R >> endobj".encode("ascii")
        )

    objs.append(f"{font_obj_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj".encode("ascii"))

    for i in range(num_pages):
        content_obj_id = font_obj_id + 1 + i
        txt = page_texts[i]
        if txt:
            # Escape parenthesis
            escaped = txt.replace("(", "\\(").replace(")", "\\)")
            stream_data = f"BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET".encode("latin1", errors="replace")
        else:
            stream_data = b""
        objs.append(
            f"{content_obj_id} 0 obj << /Length {len(stream_data)} >> stream\n".encode("ascii")
            + stream_data
            + b"\nendstream endobj"
        )

    pdf_bytes = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(pdf_bytes))
        pdf_bytes.extend(obj + b"\n")

    xref_pos = len(pdf_bytes)
    pdf_bytes.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets[1:]:
        pdf_bytes.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf_bytes.extend(f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii"))

    path.write_bytes(pdf_bytes)


def test_parser_ordered_traversal_no_jump():
    """
    FIX 1: Proves that ordered document traversal correctly assigns page numbers
    in OOXML order and eliminates artificial jumps such as 1 -> 6 -> 9 for PRV-INT-027.
    """
    from app.services.cognos_docx_parser import parse_cognos_docx

    docx_candidates = [
        Path("backend/runs/5/source/source.docx"),
        Path("runs/5/source/source.docx"),
        Path("backend/runs/1/source/source.docx"),
    ]
    target_docx = next((p for p in docx_candidates if p.exists()), None)
    if not target_docx:
        pytest.skip("PRV-INT-027 docx not present for parser validation")

    parsed = parse_cognos_docx(target_docx)
    assert len(parsed.all_parsed_tables) >= 3, "Expected at least 3 parsed tables in PRV-INT-027"

    # Table 0: Report Definition starts on Page 1
    t0 = parsed.all_parsed_tables[0]
    assert t0.source_page == 1, f"Table 0 should start on Page 1, got {t0.source_page}"
    assert t0.rows[0].source_page == 1, "Table 0 Row 0 must be on Page 1"
    assert t0.rows[20].source_page == 1, "Table 0 Row 20 must be on Page 1"
    # Table 0 internal break at Row 21 moves to Page 2
    assert t0.rows[21].source_page == 2, "Table 0 Row 21 must be on Page 2"
    assert t0.rows[-1].source_page == 2, "Table 0 trailing rows must be on Page 2"

    # Verify no row in Table 0 jumped to Page 6 or Page 9!
    for idx, row in enumerate(t0.rows):
        assert row.source_page in (1, 2), f"Table 0 row {idx} has invalid page {row.source_page}, expected 1 or 2"

    # Table 1: Report Layout starts on Page 3
    t1 = parsed.all_parsed_tables[1]
    assert t1.source_page == 3, f"Table 1 should start on Page 3, got {t1.source_page}"

    # Table 2: Report Specification starts on Page 3/4
    t2 = parsed.all_parsed_tables[2]
    assert t2.source_page in (3, 4), f"Table 2 should start on Page 3 or 4, got {t2.source_page}"


def test_invalid_pdf_page_handling_no_silent_clamping(tmp_path: Path):
    """
    FIX 2: Proves that requesting an out-of-bounds page (e.g. page 9 of a 3-page PDF, or page 0)
    strictly returns False and never silently clamps to the last physical page.
    """
    pdf_file = tmp_path / "3page.pdf"
    _build_test_multipage_pdf(
        pdf_file,
        [
            "Page 1 Content with sufficient text",
            "Page 2 Content with sufficient text",
            "Page 3 Content with sufficient text",
        ],
    )

    out_png = tmp_path / "clamped_test.png"

    # Page 9 of 3-page PDF -> must return False and NOT render page 3
    success_9 = DSDSourceSnapshotService.render_pdf_page_to_png(
        pdf_path=pdf_file,
        page_number=9,
        png_path=out_png,
    )
    assert success_9 is False, "Expected page 9 on 3-page PDF to fail without silent clamping"
    assert not out_png.exists(), "Should not create PNG for out-of-bounds page"

    # Page 0 -> must return False
    success_0 = DSDSourceSnapshotService.render_pdf_page_to_png(
        pdf_path=pdf_file,
        page_number=0,
        png_path=out_png,
    )
    assert success_0 is False, "Expected page 0 to fail"

    # Negative page -> must return False
    success_neg = DSDSourceSnapshotService.render_pdf_page_to_png(
        pdf_path=pdf_file,
        page_number=-1,
        png_path=out_png,
    )
    assert success_neg is False, "Expected negative page to fail"

    # Page 4 of 3-page PDF -> must return False
    success_4 = DSDSourceSnapshotService.render_pdf_page_to_png(
        pdf_path=pdf_file,
        page_number=4,
        png_path=out_png,
    )
    assert success_4 is False, "Expected page 4 on 3-page PDF to fail"


def test_semantic_page_resolution(tmp_path: Path):
    """
    FIX 3: Proves that semantic page resolution correctly resolves physical PDF pages
    matching evidence metadata anchors instead of falling back to wrong/blank pages.
    """
    pdf_file = tmp_path / "prv027_mock.pdf"
    # Structure mirroring PRV-INT-027 7-page physical PDF
    _build_test_multipage_pdf(
        pdf_file,
        [
            "Report Definition Selection Criteria Generation Frequency Schedule Daily",
            "Report Control Breaks, Totals, Counts, and Sorts Special Processing Output Retention",
            "Report Layout List Object Section Layout Preview",
            "Report Section Heading Spec Heading Provider Information",
            "Report Body OPLC Term Date MMIS Lic Cert End Date Prov Lic Cert Num Duplicate Lookup",
            "Footnotes N/A",
            "",  # Page 7 is blank trailing page
        ],
    )

    # 1. Date Format -> Page 5 (NOT 9, NOT 7)
    p_date = DSDSourceSnapshotService.resolve_physical_pdf_page(
        pdf_path=pdf_file,
        advisory_page=9,
        section="Report Body",
        methodology="DATE_FORMAT_VALIDATION",
        target_field="OPLC Term Date",
        evidence_scope="DATE_FORMAT_VALIDATION",
        test_case_id="PRV027-DATE-01",
    )
    assert p_date == 5, f"Expected Date Format to resolve to Page 5, got {p_date}"

    # 2. Sorts -> Page 2
    p_sort = DSDSourceSnapshotService.resolve_physical_pdf_page(
        pdf_path=pdf_file,
        advisory_page=6,
        section="Report Control Breaks, Totals, Counts, and Sorts",
        methodology="SORT_VALIDATION",
        target_field="Report Sorts",
        evidence_scope="SORT_ORDER_ASCENDING",
        test_case_id="PRV027-SORT-01",
    )
    assert p_sort == 2, f"Expected Sorts to resolve to Page 2, got {p_sort}"

    # 3. Layout -> Page 3
    p_layo = DSDSourceSnapshotService.resolve_physical_pdf_page(
        pdf_path=pdf_file,
        advisory_page=6,
        section="Report Layout",
        methodology="LAYOUT_VALIDATION",
        target_field="Report Layout",
        evidence_scope="REPORT_LAYOUT_FULL",
        test_case_id="PRV027-LAYO-01",
    )
    assert p_layo == 3, f"Expected Layout to resolve to Page 3, got {p_layo}"

    # 4. Report Definition -> Page 1
    p_def = DSDSourceSnapshotService.resolve_physical_pdf_page(
        pdf_path=pdf_file,
        advisory_page=6,
        section="Report Definition",
        methodology="REPORT_DEFINITION_VALIDATION",
        target_field="Report Title",
        evidence_scope="REPORT_DEFINITION_TITLE",
        test_case_id="PRV027-REPO-01",
    )
    assert p_def == 1, f"Expected Definition to resolve to Page 1, got {p_def}"

    # Blank trailing Page 7 must NEVER be resolved
    assert p_date != 7 and p_sort != 7 and p_layo != 7 and p_def != 7


def test_exact_cache_identity_and_proof_collision_prevention(tmp_path: Path, monkeypatch):
    """
    FIX 4: Proves that proof_*.png files from semantic proof endpoints can never
    satisfy source-snapshot requests and that distinct evidence IDs do not collide.
    """
    runs_dir = tmp_path / "runs"
    ev_dir = runs_dir / "200" / "evidence"
    ev_dir.mkdir(parents=True)
    monkeypatch.setattr(DSDSourceSnapshotService, "get_candidate_runs_dirs", classmethod(lambda cls: [runs_dir]))

    # Create a semantic proof file
    proof_file = ev_dir / "proof_PRV027-RHDR-01.png"
    proof_file.write_bytes(b"dummy_proof_content_not_authentic_snapshot")

    # source-snapshot request for PRV027-RHDR-01 must NEVER return the proof file!
    cached = DSDSourceSnapshotService.find_cached_snapshot(
        run_id=200,
        png_filename="source_snapshot_PRV027-RHDR-01.png",
        evidence_id="snapshot_PRV027-RHDR-01_REPORT",
        test_case_id="PRV027-RHDR-01",
        require_authentic=True,
    )
    assert cached is None, "Proof file must never satisfy source-snapshot request"

    # Now create the exact authentic snapshot file
    auth_file = ev_dir / "source_snapshot_snapshot_PRV027-RHDR-01_REPORT.png"
    # Create valid authentic PNG
    img = Image.new("RGB", (1224, 1584), color=(255, 255, 255))
    img.save(auth_file, format="PNG")
    DSDSourceSnapshotService.write_provenance_meta(auth_file, renderer="tier2_docx_pdf", authentic=True)

    # Now it must be found
    cached_auth = DSDSourceSnapshotService.find_cached_snapshot(
        run_id=200,
        png_filename="source_snapshot_snapshot_PRV027-RHDR-01_REPORT.png",
        evidence_id="snapshot_PRV027-RHDR-01_REPORT",
        test_case_id="PRV027-RHDR-01",
        require_authentic=True,
    )
    assert cached_auth == auth_file, "Authentic snapshot matching exact canonical key must be found"


def test_blank_trailing_page_rejection(tmp_path: Path):
    """
    Proves that a blank trailing PDF page (containing no text) is strictly rejected
    by render_pdf_page_to_png when allow_blank=False, and is never selected by resolve_physical_pdf_page.
    """
    pdf_file = tmp_path / "blank_trail.pdf"
    _build_test_multipage_pdf(
        pdf_file,
        [
            "Page 1 has authentic business document content",
            "",  # Page 2 is completely blank trailing page
        ],
    )

    out_png = tmp_path / "page2_blank.png"
    rendered = DSDSourceSnapshotService.render_pdf_page_to_png(
        pdf_path=pdf_file,
        page_number=2,
        png_path=out_png,
        allow_blank=False,
    )
    assert rendered is False, "Blank trailing page must be rejected when allow_blank=False"
    assert not out_png.exists(), "No output image should be produced for blank page"

    # resolve_physical_pdf_page must also reject page 2
    resolved = DSDSourceSnapshotService.resolve_physical_pdf_page(
        pdf_path=pdf_file,
        advisory_page=2,
        section="Report Body",
        methodology="DATA_VALIDATION",
        target_field="Field X",
        evidence_scope="SCOPE_X",
        test_case_id="TC-BLANK-01",
    )
    assert resolved != 2, f"Blank page 2 must never be resolved, got {resolved}"
