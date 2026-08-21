"""
API Endpoints for Cognos Report Definition → Test Case Generation workflow.
"""

import tempfile
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import subprocess
import fitz

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.core.rbac import require_role, CurrentUser

from app.cognos.pipeline import run_cognos_pipeline
from app.domain.reporting_context import FinalReportContext
from app.services.cognos_excel_compiler import build_cognos_workbook
from app.models.cognos_orm import (
    CognosGenerationRun,
    CognosRequirementModel,
    CognosTestCaseModel
)

router = APIRouter(prefix="/api/cognos", tags=["cognos"])

# These values must NEVER appear as authoritative semantic output.
# If any appear, it means the extraction pipeline failed silently.
INVALID_FALLBACK_VALUES = {
    "UNKNOWN", "NOT_DEFINED", "COGNOS-RPT",
    "Client Report ID:", "Report Title:", "Report Description",
    "REVIEW_REQUIRED",
}


def _compute_sha256(path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


@router.post("/upload-and-generate")
async def upload_and_generate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    Combined endpoint to upload a Cognos Report Definition DOCX, parse it,
    extract requirements, generate tests, and save everything to DB.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext != ".docx":
        raise HTTPException(
            status_code=400,
            detail=f"Only .docx files are supported for Cognos extraction (got '{ext}')."
        )

    # Save to temp file
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    contents = await file.read()
    with tempfile.NamedTemporaryFile(dir=upload_dir, suffix=ext, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)
        
    file_hash = _compute_sha256(tmp_path)

    try:
        # Run the full pipeline
        pipeline_result = run_cognos_pipeline(
            tmp_path, 
            source_document_name=file.filename,
            use_llm_assist=False  # Disabled until deterministic path is proven correct
        )
        
        # --- FAIL-ON-INVALID GUARDRAIL ---
        rid = pipeline_result.report_definition.metadata.report_id or ""
        rtitle = pipeline_result.report_definition.metadata.report_title or ""
        if rid in INVALID_FALLBACK_VALUES or not rid:
            raise ValueError(
                f"The document is missing a valid Client Report ID. "
                f"Please ensure the 'Client Report ID:' field in the Report Definition table is filled out."
            )
        if rtitle in INVALID_FALLBACK_VALUES or not rtitle:
            raise ValueError(
                f"The document is missing a valid Report Title. "
                f"Please ensure the 'Report Title:' field in the Report Definition table is filled out."
            )
        for tc in pipeline_result.test_suite.test_cases:
            if tc.test_case_title and any(v in tc.test_case_title for v in INVALID_FALLBACK_VALUES):
                raise ValueError(
                    f"Pipeline integrity failure: test case '{tc.test_case_id}' "
                    f"contains invalid fallback value in title: '{tc.test_case_title}'"
                )
        
        # Save results to DB
        run = CognosGenerationRun(
            report_id=pipeline_result.report_definition.metadata.report_id,
            report_title=pipeline_result.report_definition.metadata.report_title,
            source_document=file.filename,
            source_document_sha256=file_hash,
            report_definition_json=pipeline_result.report_definition.model_dump(),
            llm_provider=getattr(settings, "LLM_PROVIDER", "None"),
            llm_model=getattr(settings, "GROK_MODEL", "None"),
            requirements_extracted=pipeline_result.requirement_set.total_extracted,
            test_cases_generated=len(pipeline_result.test_suite.test_cases),
            coverage_percentage=pipeline_result.test_suite.coverage.overall_coverage_percentage,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            requested_by=current_user.username,
            job_id=pipeline_result.job_id
        )
        db.add(run)
        db.flush()  # To get run.id
        
        # Persist canonical source document
        canonical_source_dir = Path("runs") / str(run.id) / "source"
        canonical_source_dir.mkdir(parents=True, exist_ok=True)
        canonical_source_path = canonical_source_dir / "source.docx"
        canonical_source_path.write_bytes(contents)
        run.source_document_path = str(canonical_source_path)  # type: ignore
        print(f"RUN SOURCE:\n{canonical_source_path}")
        
        # Persist requirements
        for req in pipeline_result.requirement_set.requirements:
            req_model = CognosRequirementModel(
                run_id=run.id,
                requirement_id=req.requirement_id,
                report_id=req.report_id,
                category=req.category.value,
                field_name=req.field,
                requirement_text=req.requirement_text,
                source_section=req.source_section,
                source_page=req.source_page,
                source_columns=req.source_columns,
                processing_rule=req.processing_rule,
                formatting_rule=req.formatting_rule,
                confidence=req.confidence.value,
                is_ambiguous=req.is_ambiguous,
                open_questions=req.open_questions,
                is_duplicate_of=req.is_duplicate_of
            )
            db.add(req_model)
            
        # We need requirement primary keys for foreign key mappings
        db.flush()
        req_mapping = {r.requirement_id: r.id for r in run.requirements}
            
        # Persist test cases
        for tc in pipeline_result.test_suite.test_cases:
            tc_model = CognosTestCaseModel(
                run_id=run.id,
                test_case_id=tc.test_case_id,
                report_id=tc.report_id,
                category=tc.category,
                test_case_title=tc.test_case_title,
                requirement_id=tc.requirement_id,
                objective=tc.objective,
                preconditions=tc.preconditions,
                test_data=tc.test_data,
                test_steps=tc.test_steps,
                expected_result=tc.expected_result,
                validation_logic=tc.validation_logic,
                source_section=tc.source_section,
                source_page=tc.source_page,
                source_table=tc.source_table,
                source_column=tc.source_column,
                processing_rule=tc.processing_rule,
                formatting_rule=tc.formatting_rule,
                priority=tc.priority.value if hasattr(tc.priority, 'value') else tc.priority,
                status=tc.status.value if hasattr(tc.status, 'value') else tc.status,
                origin=tc.origin.value if hasattr(tc.origin, 'value') else tc.origin,
                version=tc.version,
                notes=tc.notes,
                open_questions=tc.open_questions,
                evidence_references=[er.model_dump() for er in tc.evidence_references] if getattr(tc, "evidence_references", None) else None
            )
            
            # M2M relationship mapping
            req_ids = tc.requirement_ids if getattr(tc, "requirement_ids", None) else ([tc.requirement_id] if tc.requirement_id else [])
            for rid in req_ids:
                if rid in req_mapping:
                    db_req = db.query(CognosRequirementModel).get(req_mapping[rid])
                    if db_req:
                        tc_model.requirements.append(db_req)

            db.add(tc_model)
            
        db.commit()
        
        requirement_count = len(pipeline_result.requirement_set.requirements)
        test_case_count = len(pipeline_result.test_suite.test_cases)
        
        ctx = pipeline_result.final_report_context
        if ctx is None:
            raise ValueError("Pipeline did not produce a FinalReportContext.")
        
        assert ctx.report_definition.metadata.report_id == pipeline_result.report_definition.metadata.report_id, "Report ID mismatch"
        assert test_case_count == len(ctx.test_suite.test_cases), "Test case count mismatch"
        assert requirement_count == len(ctx.requirement_set.requirements), "Requirement count mismatch"
        if hasattr(pipeline_result.test_suite, 'coverage'):
            assert pipeline_result.test_suite.coverage.total_requirements == requirement_count, "Coverage requirement count mismatch"
        
        # Pre-generate Excel using the authoritative FinalReportContext
        export_dir = Path(settings.EXPORT_DIR)
        export_dir.mkdir(parents=True, exist_ok=True)
        filename = f"Cognos_UT_{run.id}.xlsx"
        from typing import cast
        export_path = export_dir / filename
        generated_at = datetime.now(timezone.utc) if run.completed_at is None else cast(datetime, run.completed_at)
        wb = build_cognos_workbook(ctx, generated_at=generated_at)
        wb.save(export_path)

        test_cases_out = []
        for tc in pipeline_result.test_suite.test_cases:
            tc_dict = tc.model_dump()
            if tc_dict.get("evidence_references"):
                for ev in tc_dict["evidence_references"]:
                    if ev.get("evidence_type") == "SOURCE_DSD_SNAPSHOT":
                        ev["source_document_url"] = f"/api/cognos/runs/{run.id}/source-document"
                    if ev.get("snapshot_path"):
                        ev_id = Path(ev["snapshot_path"]).name
                        ev["evidence_id"] = ev_id
                        ev["snapshot_url"] = f"/api/cognos/runs/{run.id}/evidence/{ev_id}"
            test_cases_out.append(tc_dict)

        return {
            "run_id": run.id,
            "report_id": run.report_id,
            "status": "success",
            "summary": pipeline_result.test_suite.summary.model_dump(),
            "coverage": pipeline_result.test_suite.coverage.model_dump(),
            "test_cases": test_cases_out,
            "requirement_count": requirement_count,
            "test_case_count": test_case_count
        }

    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Cognos DOCX: {str(e)}"
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.get("/runs/{run_id}/source-document")
def get_source_document(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    Serve the canonical source document for a given run.
    """
    run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
        
    if not run.source_document_path:
        raise HTTPException(status_code=404, detail="Run does not have an associated source document path.")
        
    source_path = Path(run.source_document_path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Source document not found on disk.")
        
    return FileResponse(
        path=source_path,
        filename=run.source_document,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@router.get("/runs/{run_id}/source-snapshot")
def get_source_snapshot(
    run_id: int,
    evidence_id: str = "",
    section: str = "",
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    Serve the PNG rasterization of the canonical source document's target page using Playwright.
    """
    run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
        
    if not run.source_document_path:
        raise HTTPException(status_code=404, detail="Run does not have an associated source document path.")
        
    source_path = Path(run.source_document_path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Source document not found on disk.")

    evidence_dir = source_path.parent.parent / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    # Safe fallback if evidence_id isn't provided
    safe_evidence_id = evidence_id or "default"
    png_path = evidence_dir / f"source_snapshot_{safe_evidence_id}.png"

    if png_path.exists():
        return FileResponse(path=png_path, media_type="image/png")

    render_script = Path(__file__).parent.parent.parent / "render" / "render_snapshot.js"
    
    # Try to find node executable path (fallback if 'node' not in PATH)
    node_cmd = "node"
    
    try:
        res = subprocess.run(
            [node_cmd, str(render_script), str(source_path), str(png_path), section, run.report_id or ""],
            check=True,
            capture_output=True,
            text=True
        )
    except FileNotFoundError:
        # If 'node' is not in path, try hardcoded paths for this specific environment
        try:
            node_cmd = r"D:\Tools\node-v26.5.0-win-x64\node-v26.5.0-win-x64\node.exe"
            res = subprocess.run(
                [node_cmd, str(render_script), str(source_path), str(png_path), section, run.report_id or ""],
                check=True,
                capture_output=True,
                text=True
            )
        except Exception as fallback_e:
            raise HTTPException(status_code=404, detail=f"Visual source preview unavailable (Node not found: {str(fallback_e)})")
    except subprocess.CalledProcessError as e:
        # Playwright rendering failed
        print(f"Snapshot render failed: {e.stderr}")
        raise HTTPException(status_code=404, detail="Visual source preview unavailable")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Visual source preview unavailable ({str(e)})")

    if not png_path.exists():
        raise HTTPException(status_code=404, detail="Visual source preview unavailable (image not saved)")
        
    return FileResponse(path=png_path, media_type="image/png")


@router.get("/runs/{run_id}/export/excel")
def export_run_to_excel(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    Serve the pre-generated authoritative Excel workbook for a given run.
    """
    run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
        
    export_dir = Path(settings.EXPORT_DIR)
    filename = f"Cognos_UT_{run.id}.xlsx"
    export_path = export_dir / filename
    
    if not export_path.exists():
        raise HTTPException(status_code=404, detail="Excel export not found on disk.")
        
    return FileResponse(
        path=export_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@router.get("/runs/{run_id}/evidence/{evidence_id}")
def get_evidence_image(
    run_id: int,
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    Serve a specific DSD rendered page image for a given test case run.
    """
    run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
        
    if not run.job_id:
        raise HTTPException(status_code=404, detail="Run does not have associated evidence data.")
        
    # Security: Ensure evidence_id is just a filename
    evidence_id = Path(evidence_id).name
    
    # Path is jobs/<job_id>/evidence/<evidence_id>
    img_path = Path("jobs") / run.job_id / "evidence" / evidence_id
    
    if not img_path.exists() or not img_path.is_file():
        raise HTTPException(status_code=404, detail="Evidence image not found.")
        
    ext = img_path.suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(status_code=400, detail="Requested file is not a supported image type.")
        
    if img_path.stat().st_size == 0:
        raise HTTPException(status_code=400, detail="Requested file has zero size.")
        
    # --- PHASE 10.8J FAIL-SAFE: REJECT OLD FALLBACK ERROR IMAGES ---
    try:
        from PIL import Image
        with Image.open(img_path) as img:
            # Check if this is an old fallback error image (800x600, red background)
            if img.size == (800, 600):
                # Sample the background color at (5, 5) which was guaranteed to be the background in the old renderer
                bg_color = img.getpixel((5, 5))
                if bg_color == (255, 200, 200) or bg_color == (255, 200, 200, 255):
                    raise ValueError("ENVIRONMENT BLOCKER image detected")
    except ValueError as ve:
        # Instead of returning HTTP 400 which causes a broken image in the UI,
        # return a 1x1 transparent PNG.
        import io
        from fastapi import Response
        transparent_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa74\x81\x00\x00\x00\x00IEND\xaeB`\x82'
        return Response(content=transparent_png, media_type="image/png")
    except Exception as e:
        # If PIL fails to open it, it's not a valid image
        raise HTTPException(status_code=400, detail="Requested file is not a valid image.")
        
    media_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    return FileResponse(
        path=img_path,
        media_type=media_type
    )
