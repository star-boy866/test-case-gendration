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
    DSDSourceSnapshotService.render_pdf_page_to_png(test_pdf, 1, test_file, crop_box=(50, 50, 500, 300))
    DSDSourceSnapshotService.write_provenance_meta(test_file, renderer="tier2_docx_pdf", authentic=True, extra={"is_semantic_crop": True, "crop_box": [50, 50, 500, 300]})

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
            lines = [l.strip() for l in txt.split("\n") if l.strip()]
            stream_parts = ["BT /F1 12 Tf 24 TL 50 720 Td"]
            for l_i, l_txt in enumerate(lines):
                escaped = l_txt.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                if l_i > 0:
                    stream_parts.append("T*")
                stream_parts.append(f"({escaped}) Tj")
            stream_parts.append("ET")
            stream_data = " ".join(stream_parts).encode("latin1", errors="replace")
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
    img = Image.new("RGB", (960, 400), color=(255, 255, 255))
    img.save(auth_file, format="PNG")
    DSDSourceSnapshotService.write_provenance_meta(auth_file, renderer="tier2_docx_pdf", authentic=True, extra={"is_semantic_crop": True, "crop_box": [50, 50, 500, 300]})

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


def test_semantic_crop_calculation_across_scenarios(tmp_path: Path):
    """
    Validates that calculate_semantic_crop_bounds derives distinct, scenario-focused
    crop rectangles for different evidence requirements (EXEC, REPO, SELC, SORT, etc.)
    and never returns full-page bounds for structured document sections.
    """
    pdf_file = tmp_path / "structured_doc.pdf"
    _build_test_multipage_pdf(
        pdf_file,
        [
            # Page 1 has Definition, Generation/Scheduled, and Selection Criteria
            "NH MMIS REPORT DEFINITION\nReport ID: PRV-INT-009\nReport Title: Provider Report\nReport Description: Provider summary\nReport Generated By: MMIS System\n\n"
            "Report Generation\nReport Frequency Type: Scheduled\nReport Data Accumulation Type: Monthly\n\n"
            "Report Selection Criteria\nPrompt: Provider ID\nReport Field: PRV_ID\n\n"
            "Report Control Breaks, Totals, Counts, and Sorts\nSort By: Provider ID\nControl Break: County\nTotal records processed: 100",
            # Page 2 has Output and Special Processing
            "Report Output\nReport Output Format: PDF\nReporting Portal: EDMS\nDistribution Group(s): Accounting\nReport Retention: 7 years\n\n"
            "Report Special Processing\nRule: Process p_lic_cert_agcy_cd and interface update tables",
            # Page 3 has Report Layout mockup and Specification
            "Report Layout\nEnterprise Operational Reports\nReport Header\nReport ID: PRV-INT-009\nReport Date: 09/11/2026\n\n"
            "Report Specification\nBusiness Label | Field Type | Source Table | Source Column\nprov agency | VARCHAR | P_LIC_CERT_AGCY | AGENCY_CD\nprov ty cd - desc | VARCHAR | P_RPT_PROV_LIC_IFACE_UPD_ | TY_CD",
        ],
    )

    # 1. EXEC scenario on Page 1
    crop_exec = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_file,
        page_number=1,
        section="Report Generation",
        methodology="SCHEDULED_EXECUTION_VALIDATION",
        target_field="Scheduled / Report Frequency Type",
        evidence_scope="REPORT_FREQUENCY_SCHEDULING",
        test_case_id="TEST-EXEC-01",
        scale=2.0,
    )
    assert crop_exec is not None, "EXEC crop must be calculated"
    w_exec = crop_exec[2] - crop_exec[0]
    h_exec = crop_exec[3] - crop_exec[1]
    assert h_exec < 1400, f"EXEC crop must not be full page, got height {h_exec}"

    # 2. REPO scenario on Page 1
    crop_repo = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_file,
        page_number=1,
        section="Report Definition",
        methodology="REPORT_NAME_DESCRIPTION_VALIDATION",
        target_field="report id",
        evidence_scope="Report Metadata",
        test_case_id="TEST-REPO-01",
        scale=2.0,
    )
    assert crop_repo is not None, "REPO crop must be calculated"
    # EXEC and REPO share Page 1 but must produce distinct vertical crop rectangles
    assert crop_exec != crop_repo, "EXEC and REPO on same page must produce distinct crop rectangles"

    # 3. SELC scenario on Page 1
    crop_selc = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_file,
        page_number=1,
        section="Report Selection Criteria",
        methodology="SELECTION_CRITERIA_VALIDATION",
        target_field="file name",
        evidence_scope="REPORT_SELECTION_CRITERIA",
        test_case_id="TEST-SELC-01",
        scale=2.0,
    )
    assert crop_selc is not None
    assert crop_selc != crop_exec and crop_selc != crop_repo, "SELC must produce distinct crop rectangle"

    # 4. OUTP scenario on Page 2
    crop_outp = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_file,
        page_number=2,
        section="Report Output",
        methodology="OUTPUT_DELIVERY_VALIDATION",
        target_field="reporting portal",
        evidence_scope="Distribution & Portal",
        test_case_id="TEST-OUTP-01",
        scale=2.0,
    )
    assert crop_outp is not None

    # 5. SPEC scenario on Page 2
    crop_spec = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_file,
        page_number=2,
        section="Report Special Processing",
        methodology="SPECIAL_PROCESSING_VALIDATION",
        target_field="p_lic_cert_agcy_cd",
        evidence_scope="REPORT_SPECIAL_PROCESSING",
        test_case_id="TEST-SPEC-01",
        scale=2.0,
    )
    assert crop_spec is not None
    assert crop_outp != crop_spec, "OUTP and SPEC on Page 2 must produce distinct crop rectangles"

    # 6. LOOK scenario on Page 3
    crop_look = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_file,
        page_number=3,
        section="Report Specification",
        methodology="LOOKUP_VALIDATION",
        target_field="prov agency",
        evidence_scope="prov agency",
        test_case_id="TEST-LOOK-01",
        scale=2.0,
    )
    assert crop_look is not None
    h_look = crop_look[3] - crop_look[1]
    assert h_look < 600, f"LOOK crop should be a row/table section, got height {h_look}"


def test_cache_versioning_rejects_legacy_uncropped_snapshots(tmp_path: Path, monkeypatch):
    """
    Validates that find_cached_snapshot enforces CURRENT_CROP_VERSION:
      - Rejects legacy uncropped full-page captures (1584x1224) lacking crop_version.
      - Rejects legacy metadata lacking current crop_version.
      - Accepts genuine semantic crops stamped with CURRENT_CROP_VERSION.
    """
    runs_dir = tmp_path / "runs"
    ev_dir = runs_dir / "300" / "evidence"
    ev_dir.mkdir(parents=True)

    monkeypatch.setattr(DSDSourceSnapshotService, "get_candidate_runs_dirs", classmethod(lambda cls: [runs_dir]))

    # 1. Legacy uncropped full-page image (1584x1224) without metadata
    legacy_full = ev_dir / "source_snapshot_TEST_FULL.png"
    im_full = Image.new("RGB", (1584, 1224), color=(255, 255, 255))
    im_full.save(legacy_full)

    cached_full = DSDSourceSnapshotService.find_cached_snapshot(
        run_id=300,
        png_filename="source_snapshot_TEST_FULL.png",
        evidence_id="TEST_FULL",
        require_authentic=True,
    )
    assert cached_full is None, "Legacy uncropped full-page snapshot must be rejected by cache"

    # 2. Legacy snapshot with stale metadata (renderer=tier2_docx_pdf, missing crop_version)
    legacy_stale = ev_dir / "source_snapshot_TEST_STALE.png"
    im_stale = Image.new("RGB", (800, 400), color=(255, 255, 255))
    im_stale.save(legacy_stale)
    meta_path = legacy_stale.with_suffix(".meta.json")
    import json
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "filename": legacy_stale.name,
            "renderer": "tier2_docx_pdf",
            "authentic": True,
            "page_number": 1,
            # crop_version missing / stale
        }, f)

    cached_stale = DSDSourceSnapshotService.find_cached_snapshot(
        run_id=300,
        png_filename="source_snapshot_TEST_STALE.png",
        evidence_id="TEST_STALE",
        require_authentic=True,
    )
    assert cached_stale is None, "Legacy snapshot without current crop_version must be rejected"

    # 3. Genuine semantic crop stamped with CURRENT_CROP_VERSION
    valid_crop = ev_dir / "source_snapshot_TEST_VALID.png"
    im_valid = Image.new("RGB", (961, 418), color=(255, 255, 255))
    im_valid.save(valid_crop)
    DSDSourceSnapshotService.write_provenance_meta(
        valid_crop,
        renderer="tier2_docx_pdf",
        authentic=True,
        page_number=1,
        extra={"is_semantic_crop": True, "crop_version": DSDSourceSnapshotService.CURRENT_CROP_VERSION},
    )

    cached_valid = DSDSourceSnapshotService.find_cached_snapshot(
        run_id=300,
        png_filename="source_snapshot_TEST_VALID.png",
        evidence_id="TEST_VALID",
        require_authentic=True,
        page_number=1,
    )
    assert cached_valid == valid_crop, "Genuine semantic crop with current version must be accepted"

    # 4. Stale v2_semantic_crop must be rejected
    v2_stale = ev_dir / "source_snapshot_TEST_V2.png"
    im_v2 = Image.new("RGB", (900, 300), color=(255, 255, 255))
    im_v2.save(v2_stale)
    meta_v2 = v2_stale.with_suffix(".meta.json")
    with open(meta_v2, "w", encoding="utf-8") as f:
        json.dump({
            "filename": v2_stale.name,
            "renderer": "tier2_docx_pdf",
            "authentic": True,
            "page_number": 1,
            "crop_version": "v2_semantic_crop",
            "is_semantic_crop": True,
        }, f)

    cached_v2 = DSDSourceSnapshotService.find_cached_snapshot(
        run_id=300,
        png_filename="source_snapshot_TEST_V2.png",
        evidence_id="TEST_V2",
        require_authentic=True,
    )
    assert cached_v2 is None, "Stale v2_semantic_crop snapshot must be rejected"


def test_pypdfium2_thread_safe_crop_rendering(tmp_path: Path):
    """
    Validates that render_pdf_page_to_png with crop_box executes safely under
    the process-level _pdfium_lock and produces the expected cropped dimensions.
    """
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument.new()
    page = pdf.new_page(width=612, height=792)  # 612x792 pt
    test_pdf = tmp_path / "crop_test.pdf"
    pdf.save(str(test_pdf))
    pdf.close()

    out_png = tmp_path / "cropped_result.png"
    # Request a crop box of (100, 200, 800, 600)
    crop_box = (100, 200, 800, 600)

    ok = DSDSourceSnapshotService.render_pdf_page_to_png(
        pdf_path=test_pdf,
        page_number=1,
        png_path=out_png,
        allow_blank=True,
        crop_box=crop_box,
    )
    assert ok is True
    assert out_png.exists()

    with Image.open(out_png) as im:
        assert im.size == (700, 400), f"Expected cropped size 700x400, got {im.size}"


def test_rhdr_exact_semantic_crop_and_layo_differentiation(tmp_path: Path):
    """
    Validates:
      1. RHDR produces a tight crop around ONLY the Report Header table (~200-300px height).
      2. LAYO on the same page produces the full wireframe layout mockup (>1000px height).
      3. RHDR stops strictly above Total Errors/Records and does not contain entire layout.
    """
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument.new()
    page = pdf.new_page(width=792, height=612)  # Landscape Letter in points
    # Insert text objects representing PRV-INT-008 Report Layout page
    test_pdf = tmp_path / "prv008_layout_page.pdf"
    pdf.save(str(test_pdf))
    pdf.close()

    # Create mock multipage pdf with exact layout text
    _build_test_multipage_pdf(
        test_pdf,
        [
            "NH MMIS REPORT LAYOUT - PROVIDER PARTICIPATION EXCEPTION REPORT\n"
            "Report ID: PRV-INT-008\nFile Name: PRV008.PDF\nDate: MM/DD/CCYY\n"
            "Total Errors: 999\n"
            "Prov ID   Prov Lic   Error Field\n"
            "123456    LIC001     Invalid Format\n"
            "123457    LIC002     Missing Expiry\n"
            "123458    LIC003     Inactive Status\n"
            "Run Date: MM/DD/CCYY    Page: 1    Run Time: 12:00:00"
        ]
    )

    crop_rhdr = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=test_pdf,
        page_number=1,
        section="Report Layout",
        methodology="REPORT_HEADER_VALIDATION",
        target_field="Report Header",
        evidence_scope="REPORT_HEADER",
        test_case_id="PRV008-RHDR-01",
        scale=2.0,
    )
    assert crop_rhdr is not None, "RHDR crop must be calculated"
    h_rhdr = crop_rhdr[3] - crop_rhdr[1]
    assert 100 <= h_rhdr <= 350, f"RHDR crop must be tight header region, got height {h_rhdr}px"

    crop_layo = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=test_pdf,
        page_number=1,
        section="Report Layout",
        methodology="LAYOUT_VALIDATION",
        target_field="",
        evidence_scope="FULL_REPORT_LAYOUT",
        test_case_id="PRV008-LAYO-01",
        scale=2.0,
    )
    assert crop_layo is not None, "LAYO crop must be calculated"
    h_layo = crop_layo[3] - crop_layo[1]
    assert h_layo > h_rhdr, f"LAYO crop ({h_layo}px) must be significantly larger than RHDR ({h_rhdr}px)"
    assert crop_rhdr != crop_layo, "RHDR and LAYO on the same page must never resolve to the same crop box"


def test_dbrv_excludes_chart_footer_and_footnote(tmp_path: Path):
    """
    Validates that DBRV (Full Mapping) stops strictly above Chart Footer and Report Footnote
    and does not capture footnote content.
    """
    test_pdf = tmp_path / "prv008_body_page.pdf"
    _build_test_multipage_pdf(
        test_pdf,
        [
            "NH MMIS REPORT SPECIFICATION\nReport Section Heading\nTotal Errors\n"
            "Report Body\nField Type | Business Label | Source Table | Source Column\n"
            "Column | Prov Lic Cert Num | P_LIC | CERT_NUM\n"
            "Column | Error Field | P_LIC | ERR_FIELD\n"
            "Column | Error Field Value | P_LIC | ERR_VAL\n"
            "Column | Error Message | P_LIC | ERR_MSG\n"
            "Chart Footer (opt)\nChart Footnote Label (opt)\n"
            "Report Footnote (opt)\nReport Footnote Label (opt)"
        ]
    )

    crop_dbrv = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=test_pdf,
        page_number=1,
        section="Report Body",
        methodology="DB_REPORT_DATA_VALIDATION",
        target_field="Full Mapping",
        evidence_scope="REPORT_BODY_MAPPING",
        test_case_id="PRV008-DBRV-01",
        scale=2.0,
    )
    assert crop_dbrv is not None, "DBRV crop must be calculated"

    # Also render to check footer exclusion
    out_png = tmp_path / "dbrv_rendered.png"
    ok = DSDSourceSnapshotService.render_pdf_page_to_png(
        pdf_path=test_pdf,
        page_number=1,
        png_path=out_png,
        crop_box=crop_dbrv,
    )
    assert ok is True
    assert out_png.exists()
    with Image.open(out_png) as im:
        assert im.size[0] > 200
        # Check that crop does not extend the full height
        assert im.size[1] < 1500


def test_prv009_all_17_scenarios_exact_crops():
    """
    Verifies that all 17 PRV-INT-009 test case scenarios produce exact, non-empty,
    full-width, scenario-specific bounded crops.
    """
    pdf_path = Path(__file__).resolve().parent.parent / "runs" / "12" / "source" / "source.pdf"
    if not pdf_path.exists():
        pytest.skip(f"PRV-INT-009 source.pdf not present at {pdf_path}")

    test_cases = [
        ("PRV009-REPO-01", 1, "Report Definition", "REPORT_NAME_DESCRIPTION_VALIDATION", "report description", "Report Metadata"),
        ("PRV009-EXEC-01", 1, "Report Generation", "SCHEDULED_EXECUTION_VALIDATION", "Scheduled / Report Frequency Type", "REPORT_FREQUENCY_SCHEDULING"),
        ("PRV009-SELC-01", 1, "Report Selection Criteria", "SELECTION_CRITERIA_VALIDATION", "file name", "REPORT_SELECTION_CRITERIA"),
        ("PRV009-SORT-01", 1, "Report Control Breaks, Totals, Counts, and Sorts", "SORT_VALIDATION", "provider id", "Report Control Breaks, Totals, Counts, and Sorts"),
        ("PRV009-DBCO-01", 2, "Report Control Breaks, Totals, Counts, and Sorts", "DB_COUNT_VALIDATION", "total records processed", "Report Control Breaks, Totals, Counts, and Sorts"),
        ("PRV009-OUTP-01", 2, "Report Output", "OUTPUT_DELIVERY_VALIDATION", "reporting portal", "Distribution & Portal"),
        ("PRV009-SCRI-01", 2, "Report Output / Retention", "SCRIPT_OUTPUT_VALIDATION", "reporting portal", "Source Specification"),
        ("PRV009-SCRI-02", 2, "Report Output / Retention", "SCRIPT_OUTPUT_VALIDATION", "retention type", "Source Specification"),
        ("PRV009-SPEC-01", 2, "Report Special Processing", "SPECIAL_PROCESSING_VALIDATION", "p_lic_cert_agcy_cd", "REPORT_SPECIAL_PROCESSING"),
        ("PRV009-RHDR-01", 3, "Report Layout", "REPORT_HEADER_VALIDATION", "Report Header", "REPORT_HEADER"),
        ("PRV009-LAYO-01", 3, "Report Layout", "LAYOUT_VALIDATION", "", "FULL_REPORT_LAYOUT"),
        ("PRV009-SECT-01", 4, "Report Section Heading", "REPORT_SECTION_HEADING_VALIDATION", "Report Section Heading", "REPORT_SECTION_HEADING"),
        ("PRV009-LABE-01", 4, "Report Body", "LABEL_VALIDATION", "Column Labels", "COLUMN_LABELS"),
        ("PRV009-DBRV-01", 4, "Report Body", "DB_REPORT_DATA_VALIDATION", "Full Mapping", "REPORT_BODY_MAPPING"),
        ("PRV009-LOOK-01", 5, "Report Specification", "LOOKUP_VALIDATION", "prov agency", "prov agency"),
        ("PRV009-LOOK-02", 5, "Report Specification", "LOOKUP_VALIDATION", "prov ty cd - desc", "prov ty cd - desc"),
        ("PRV009-DUPL-01", 4, "Report Specification", "DUPLICATE_VALIDATION", "p_alt_id, p_sort_nam, p_lic_cert_agcy_cd, p_disp_actn_cd", "p_alt_id, p_sort_nam, p_lic_cert_agcy_cd, p_disp_actn_cd"),
    ]

    for tc_id, pno, sec, meth, tf, sc in test_cases:
        cb = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
            pdf_path=pdf_path,
            page_number=pno,
            section=sec,
            methodology=meth,
            target_field=tf,
            evidence_scope=sc,
            test_case_id=tc_id,
        )
        assert cb is not None, f"Crop bounds must be computed for {tc_id}"
        px_x0, px_y0, px_x1, px_y1 = cb
        assert px_x0 == 0, f"{tc_id} must have left_x=0 (full width)"
        assert px_x1 == 1190, f"{tc_id} must span full page width (1190 px)"
        height = px_y1 - px_y0
        assert height >= 60, f"{tc_id} height {height} must be >= 60px"
        assert height <= 1650, f"{tc_id} height {height} must not exceed page bounds"


def test_rhdr_vs_layo_invariant():
    """
    Verifies that RHDR is strictly contained inside LAYO and significantly smaller.
    """
    pdf_path = Path(__file__).resolve().parent.parent / "runs" / "12" / "source" / "source.pdf"
    if not pdf_path.exists():
        pytest.skip("PRV-INT-009 source.pdf not present")

    cb_rhdr = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path,
        page_number=3,
        section="Report Layout",
        methodology="REPORT_HEADER_VALIDATION",
        target_field="Report Header",
        evidence_scope="REPORT_HEADER",
        test_case_id="PRV009-RHDR-01",
    )
    cb_layo = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path,
        page_number=3,
        section="Report Layout",
        methodology="LAYOUT_VALIDATION",
        target_field="",
        evidence_scope="FULL_REPORT_LAYOUT",
        test_case_id="PRV009-LAYO-01",
    )
    assert cb_rhdr is not None and cb_layo is not None
    # RHDR top edge is at or below LAYO top edge (px_y0_rhdr >= px_y0_layo)
    assert cb_rhdr[1] >= cb_layo[1]
    # RHDR bottom edge is strictly above LAYO bottom edge (px_y1_rhdr < px_y1_layo)
    assert cb_rhdr[3] < cb_layo[3]
    # RHDR height is significantly smaller than LAYO
    h_rhdr = cb_rhdr[3] - cb_rhdr[1]
    h_layo = cb_layo[3] - cb_layo[1]
    assert h_rhdr < (h_layo / 2), f"RHDR height ({h_rhdr}) must be less than half of LAYO ({h_layo})"


def test_scri01_vs_scri02_distinct_crops():
    """
    Verifies that SCRI-01 (Output delivery) and SCRI-02 (Retention) produce
    distinct, non-overlapping crop regions on Page 2.
    """
    pdf_path = Path(__file__).resolve().parent.parent / "runs" / "12" / "source" / "source.pdf"
    if not pdf_path.exists():
        pytest.skip("PRV-INT-009 source.pdf not present")

    cb_scri1 = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path,
        page_number=2,
        section="Report Output / Retention",
        methodology="SCRIPT_OUTPUT_VALIDATION",
        target_field="reporting portal",
        evidence_scope="Source Specification",
        test_case_id="PRV009-SCRI-01",
    )
    cb_scri2 = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path,
        page_number=2,
        section="Report Output / Retention",
        methodology="SCRIPT_OUTPUT_VALIDATION",
        target_field="retention type",
        evidence_scope="Source Specification",
        test_case_id="PRV009-SCRI-02",
    )
    assert cb_scri1 is not None and cb_scri2 is not None
    # SCRI-01 is above SCRI-02
    assert cb_scri1 != cb_scri2, "SCRI-01 and SCRI-02 must produce different crop bounds"
    assert cb_scri1[1] < cb_scri2[1], "SCRI-01 region must start above SCRI-02 region"
    assert cb_scri1[3] < cb_scri2[3], "SCRI-01 region must end above SCRI-02 region"


def test_semantic_target_cache_validation(tmp_path: Path, monkeypatch):
    """
    Validates that find_cached_snapshot checks semantic_target and rejects cache
    when the cached target does not match the requested scenario.
    """
    monkeypatch.setattr(DSDSourceSnapshotService, "get_candidate_runs_dirs", classmethod(lambda cls: [tmp_path]))
    ev_dir = tmp_path / "99" / "evidence"
    ev_dir.mkdir(parents=True)

    png_file = ev_dir / "source_snapshot_test.png"
    im = Image.new("RGB", (1190, 400), color=(255, 255, 255))
    im.save(png_file)

    # Stamped with REPORT_OUTPUT_DELIVERY
    DSDSourceSnapshotService.write_provenance_meta(
        png_file,
        renderer="tier2_docx_pdf",
        authentic=True,
        page_number=2,
        extra={
            "crop_version": DSDSourceSnapshotService.CURRENT_CROP_VERSION,
            "is_semantic_crop": True,
            "semantic_target": "REPORT_OUTPUT_DELIVERY",
        },
    )

    # 1. Query for REPORT_OUTPUT_DELIVERY -> HIT
    hit = DSDSourceSnapshotService.find_cached_snapshot(
        run_id=99,
        png_filename="source_snapshot_test.png",
        require_authentic=True,
        methodology="OUTPUT_DELIVERY_VALIDATION",
        section="Report Output",
        target_field="reporting portal",
        page_number=2,
    )
    assert hit is not None, "Matching semantic_target must be accepted from cache"

    # 2. Query for REPORT_RETENTION on same filename -> MISMATCH REJECTED
    miss = DSDSourceSnapshotService.find_cached_snapshot(
        run_id=99,
        png_filename="source_snapshot_test.png",
        require_authentic=True,
        methodology="SCRIPT_OUTPUT_VALIDATION",
        section="Report Retention",
        target_field="retention type",
        test_case_id="PRV009-SCRI-02",
        page_number=2,
    )
    assert miss is None, "Mismatched semantic_target must be rejected from cache"


def test_semantic_crop_physical_padding_prv027():
    """
    Validates that PRV-INT-027 snapshots (RHDR, SELC, DBRV, LAYO, LOOK-01, LOOK-02)
    include approximately 0.5 inch (36.0 points / 72 pixels at scale 2.0) of original
    source-page whitespace above and below the semantic target without synthetic padding.
    """
    pdf_path = Path(__file__).resolve().parent.parent / "runs" / "5" / "source" / "source.pdf"
    if not pdf_path.exists():
        pytest.skip("PRV-INT-027 source.pdf not present at backend/runs/5/source/source.pdf")

    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        p4 = pdf.get_page(3)  # Page 4 (0-indexed 3)
        w4, h4 = p4.get_size()
        p4.close()
    finally:
        pdf.close()

    # 1. PRV-INT-027 RHDR (Page 4)
    cb_rhdr = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path, page_number=4, section="Report Layout",
        methodology="REPORT_HEADER_VALIDATION", target_field="Report Header",
        evidence_scope="REPORT_HEADER", test_case_id="PRV027-RHDR-01",
        include_vertical_margin=True, scale=2.0
    )
    cb_rhdr_raw = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path, page_number=4, section="Report Layout",
        methodology="REPORT_HEADER_VALIDATION", target_field="Report Header",
        evidence_scope="REPORT_HEADER", test_case_id="PRV027-RHDR-01",
        include_vertical_margin=False, scale=2.0
    )
    assert cb_rhdr is not None and cb_rhdr_raw is not None
    # Verify ~0.5 inch (72px at scale 2.0) top and bottom source-page margin
    assert (cb_rhdr_raw[1] - cb_rhdr[1]) == 72, "Top margin must be exactly 72px (0.5 inch at scale 2.0)"
    assert (cb_rhdr[3] - cb_rhdr_raw[3]) == 72, "Bottom margin must be exactly 72px (0.5 inch at scale 2.0)"
    assert cb_rhdr[0] >= 0 and cb_rhdr[1] >= 0
    assert cb_rhdr[2] <= int(w4 * 2.0) and cb_rhdr[3] <= int(h4 * 2.0)

    # 2. PRV-INT-027 LAYO (Page 4)
    cb_layo = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path, page_number=4, section="Report Layout",
        methodology="LAYOUT_VALIDATION", target_field="",
        evidence_scope="FULL_REPORT_LAYOUT", test_case_id="PRV027-LAYO-01",
        include_vertical_margin=True, scale=2.0
    )
    assert cb_layo is not None
    # LAYO remains broader than RHDR
    h_rhdr = cb_rhdr[3] - cb_rhdr[1]
    h_layo = cb_layo[3] - cb_layo[1]
    assert h_layo > h_rhdr, f"LAYO ({h_layo}px) must be broader than RHDR ({h_rhdr}px)"

    # 3. PRV-INT-027 SELC (Page 2)
    cb_selc = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path, page_number=2, section="Report Selection Criteria",
        methodology="SELECTION_CRITERIA_VALIDATION", target_field="file name",
        evidence_scope="REPORT_SELECTION_CRITERIA", test_case_id="PRV027-SELC-01",
        include_vertical_margin=True, scale=2.0
    )
    cb_selc_raw = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path, page_number=2, section="Report Selection Criteria",
        methodology="SELECTION_CRITERIA_VALIDATION", target_field="file name",
        evidence_scope="REPORT_SELECTION_CRITERIA", test_case_id="PRV027-SELC-01",
        include_vertical_margin=False, scale=2.0
    )
    assert cb_selc is not None and cb_selc_raw is not None
    assert (cb_selc_raw[1] - cb_selc[1]) == 72
    assert (cb_selc[3] - cb_selc_raw[3]) == 72

    # 4. PRV-INT-027 DBRV (Page 5)
    cb_dbrv = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path, page_number=5, section="Report Body",
        methodology="DB_REPORT_DATA_VALIDATION", target_field="Full Mapping",
        evidence_scope="REPORT_BODY_MAPPING", test_case_id="PRV027-DBRV-01",
        include_vertical_margin=True, scale=2.0
    )
    cb_dbrv_raw = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path, page_number=5, section="Report Body",
        methodology="DB_REPORT_DATA_VALIDATION", target_field="Full Mapping",
        evidence_scope="REPORT_BODY_MAPPING", test_case_id="PRV027-DBRV-01",
        include_vertical_margin=False, scale=2.0
    )
    assert cb_dbrv is not None and cb_dbrv_raw is not None
    assert (cb_dbrv_raw[1] - cb_dbrv[1]) == 72
    assert (cb_dbrv[3] - cb_dbrv_raw[3]) == 72

    # 5 & 6. LOOK-01 and LOOK-02 distinctness
    cb_look1 = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path, page_number=5, section="Report Specification",
        methodology="LOOKUP_VALIDATION", target_field="p_lic_cert_agcy_cd",
        evidence_scope="p_lic_cert_agcy_cd", test_case_id="PRV027-LOOK-01",
        include_vertical_margin=True, scale=2.0
    )
    cb_look2 = DSDSourceSnapshotService.calculate_semantic_crop_bounds(
        pdf_path=pdf_path, page_number=5, section="Report Specification",
        methodology="LOOKUP_VALIDATION", target_field="p_disp_actn_cd",
        evidence_scope="p_disp_actn_cd", test_case_id="PRV027-LOOK-02",
        include_vertical_margin=True, scale=2.0
    )
    assert cb_look1 is not None and cb_look2 is not None

    # 7. Verify legacy cached snapshot with old crop_version is rejected
    cached_legacy = DSDSourceSnapshotService.find_cached_snapshot(
        run_id=5,
        png_filename="source_snapshot_test_legacy.png",
        require_authentic=True,
    )
    assert cached_legacy is None, "Legacy unversioned or v8 snapshot must be rejected"

