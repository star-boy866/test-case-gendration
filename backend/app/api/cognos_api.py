"""
API Endpoints for Cognos Report Definition → Test Case Generation workflow.
"""

import tempfile
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import subprocess
import logging

logger = logging.getLogger(__name__)

from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Body
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
from app.cognos.rules.scenario_patterns import discover_applicable_patterns
from app.services.cognos_hitl_service import (
    generate_suggested_correction,
    generate_missing_scenario,
    compute_field_diffs,
    record_history_entry,
    evaluate_execution_path_rules
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


from app.cognos.detection.dsd_format_detector import (
    DSDFormatDetector,
    DSDProfile,
    DSDDetectionResult,
)


@router.post("/detect-dsd-format", response_model=DSDDetectionResult)
async def detect_dsd_format(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    Inspects an uploaded DOCX to detect the DSD format profile (NH, ND, AK).
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext != ".docx":
        raise HTTPException(
            status_code=400,
            detail=f"Only .docx files are supported for format detection (got '{ext}')."
        )

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    contents = await file.read()
    with tempfile.NamedTemporaryFile(dir=upload_dir, suffix=ext, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        result = DSDFormatDetector.detect_format(tmp_path, file.filename)
        return result
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


@router.post("/upload-and-generate")
async def upload_and_generate(
    file: UploadFile = File(...),
    dsd_profile: str = Form("AUTO"),
    work_type: Optional[str] = Form(None),
    work_item_id: Optional[str] = Form(None),
    work_item_title: Optional[str] = Form(None),
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

    # Validate / Route DSD Profile
    effective_profile = dsd_profile.upper() if dsd_profile else "AUTO"
    if effective_profile == "AUTO":
        detection = DSDFormatDetector.detect_format(tmp_path, file.filename)
        effective_profile = detection.detected_format
        if effective_profile == DSDProfile.UNKNOWN.value:
            raise HTTPException(
                status_code=400,
                detail="Unable to determine DSD format. Please select NH / ND / AK manually."
            )

    if effective_profile == DSDProfile.AK.value or effective_profile == "AK":
        raise HTTPException(
            status_code=400,
            detail="AK format detected. AK processing is not enabled yet."
        )
    elif effective_profile not in (DSDProfile.NH.value, DSDProfile.ND.value, "NH", "ND"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported DSD profile '{effective_profile}'."
        )

    try:
        # Run the full pipeline via profile dispatcher (supports NH & ND)
        pipeline_result = run_cognos_pipeline(
            tmp_path, 
            source_document_name=file.filename,
            use_llm_assist=False,  # Disabled until deterministic path is proven correct
            dsd_profile=effective_profile,
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
            job_id=pipeline_result.job_id,
            work_type=work_type,
            work_item_id=work_item_id,
            work_item_title=work_item_title,
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
            
        # Persist test cases with HITL defaults
        for tc in pipeline_result.test_suite.test_cases:
            is_prv = "PRV" in (tc.report_id or "") or "PRV" in tc.test_case_id
            is_nd = "ND" in (tc.report_id or "") or "OPR" in (tc.report_id or "")
            exec_method = "Scheduled" if (is_prv or is_nd) else "On Request"
            exec_tool = "IWA" if is_prv else ("UC4" if is_nd else "Cognos Portal")

            init_history = [{
                "version": 1,
                "action": "AI_GENERATED",
                "status": "GENERATED",
                "author": "AI Pipeline",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": "Initial scenario generated by AI pipeline",
            }]

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
                scenario_order=tc.scenario_order,
                notes=tc.notes,
                open_questions=tc.open_questions,
                evidence_references=[er.model_dump() for er in tc.evidence_references] if getattr(tc, "evidence_references", None) else None,
                review_status="GENERATED",
                execution_method=exec_method,
                execution_tool=exec_tool,
                edit_history=init_history,
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
        if hasattr(pipeline_result.test_suite, 'coverage'):
            total_cov_reqs = (
                pipeline_result.test_suite.coverage.total_requirements +
                getattr(pipeline_result.test_suite.coverage, 'requirements_duplicate', 0)
            )
            assert total_cov_reqs == requirement_count, f"Coverage requirement count mismatch ({total_cov_reqs} vs {requirement_count})"
        
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
            is_prv = "PRV" in (tc.report_id or "") or "PRV" in tc.test_case_id
            is_nd = "ND" in (tc.report_id or "") or "OPR" in (tc.report_id or "")
            tc_dict["review_status"] = "GENERATED"
            tc_dict["execution_method"] = "Scheduled" if (is_prv or is_nd) else "On Request"
            tc_dict["execution_tool"] = "IWA" if is_prv else ("UC4" if is_nd else "Cognos Portal")
            tc_dict["edit_history"] = [{
                "version": 1,
                "action": "AI_GENERATED",
                "status": "GENERATED",
                "author": "AI Pipeline",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": "Initial scenario generated by AI pipeline",
            }]
            if tc_dict.get("evidence_references"):
                for ev in tc_dict["evidence_references"]:
                    if ev.get("evidence_type") == "SOURCE_DSD_SNAPSHOT":
                        ev["source_document_url"] = f"/api/cognos/runs/{run.id}/source-document"
                    if ev.get("snapshot_path"):
                        ev_id = Path(ev["snapshot_path"]).name
                        ev["evidence_id"] = ev_id
                        ev["snapshot_url"] = f"/api/cognos/runs/{run.id}/evidence/{ev_id}"
            test_cases_out.append(tc_dict)

        # Retrieve methodology applicability (already computed during test generation, but we re-fetch the report here for the UI)
        methodology_report = discover_applicable_patterns(
            pipeline_result.requirement_set.requirements, 
            pipeline_result.report_definition
        )
        
        # We need to manually convert the MethodologyApplicabilityReport and its nested enums to JSON-serializable dicts
        import dataclasses
        def _serialize_methodology_report(report):
            from app.domain.cognos_requirement import RequirementConfidence
            from enum import Enum
            import typing
            def _clean(obj: typing.Any) -> typing.Any:
                if isinstance(obj, Enum):
                    return obj.value
                elif isinstance(obj, dict):
                    return {k: _clean(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [_clean(i) for i in obj]
                elif dataclasses.is_dataclass(obj):
                    return _clean(dataclasses.asdict(obj))
                elif hasattr(obj, 'model_dump'):
                    return obj.model_dump()
                return obj
            return _clean(report)

        return {
            "run_id": run.id,
            "report_id": run.report_id,
            "status": "success",
            "work_type": run.work_type,
            "work_item_id": run.work_item_id,
            "work_item_title": run.work_item_title,
            "report_definition": pipeline_result.report_definition.model_dump(),
            "summary": pipeline_result.test_suite.summary.model_dump(),
            "coverage": pipeline_result.test_suite.coverage.model_dump(),
            "methodology_applicability": _serialize_methodology_report(methodology_report),
            "requirements": [r.model_dump() for r in pipeline_result.requirement_set.requirements],
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
    methodology: str = "",
    target_field: str = "",
    evidence_scope: str = "",
    test_case_id: str = "",
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    Serve the PNG rasterization of the canonical source document's target region using Playwright.
    """
    logger.info(
        f"[SOURCE_SNAPSHOT REQUEST] run_id={run_id}, evidence_id='{evidence_id}', "
        f"test_case_id='{test_case_id}', methodology='{methodology}', "
        f"section='{section}', target_field='{target_field}', evidence_scope='{evidence_scope}'"
    )

    run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
    if not run:
        logger.warning(f"[SOURCE_SNAPSHOT 404] Run {run_id} not found in DB.")
        raise HTTPException(status_code=404, detail="Run not found.")
        
    if not run.source_document_path:
        logger.warning(f"[SOURCE_SNAPSHOT 404] Run {run_id} has no source_document_path.")
        raise HTTPException(status_code=404, detail="Run does not have an associated source document path.")
        
    source_path = Path(run.source_document_path)
    if not source_path.exists():
        logger.warning(f"[SOURCE_SNAPSHOT 404] Source document not found at {source_path}.")
        raise HTTPException(status_code=404, detail="Source document not found on disk.")

    evidence_dir = source_path.parent.parent / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    # Phase 12O.1: Layout Validation snapshot cache key is page-level
    if methodology == "LAYOUT_VALIDATION" or evidence_scope == "FULL_REPORT_LAYOUT":
        png_path = evidence_dir / f"source_snapshot_{run_id}_REPORT_LAYOUT_FULL.png"
        target_field = ""
        evidence_scope = "FULL_REPORT_LAYOUT"
        section = "Report Layout"
    elif methodology == "DB_REPORT_DATA_VALIDATION" or evidence_scope == "REPORT_BODY_MAPPING":
        png_path = evidence_dir / f"source_snapshot_{run_id}_DBRV_FULL_REPORT_BODY.png"
        target_field = "Full Mapping"
        evidence_scope = "REPORT_BODY_MAPPING"
        section = "Report Body"
    else:
        # Safe fallback if evidence_id isn't provided
        safe_evidence_id = evidence_id or (f"snap_{test_case_id}_{methodology[:6]}" if (test_case_id or methodology) else "default")
        png_path = evidence_dir / f"source_snapshot_{safe_evidence_id}.png"

    render_script = Path(__file__).parent.parent.parent / "render" / "render_snapshot.js"

    # Cache check: return cached PNG if file exists, has size > 0, and is not older than render_snapshot.js
    if png_path.exists() and png_path.stat().st_size > 0:
        if render_script.exists() and png_path.stat().st_mtime >= render_script.stat().st_mtime:
            logger.info(f"[SOURCE_SNAPSHOT CACHE HIT] {png_path} ({png_path.stat().st_size} bytes)")
            return FileResponse(path=png_path, media_type="image/png")
        else:
            logger.info(f"[SOURCE_SNAPSHOT CACHE INVALIDATED] {png_path} is older than render_snapshot.js. Regenerating...")
    
    # Try to find node executable path (fallback if 'node' not in PATH)
    node_cmd = "node"
    args = [
        str(render_script),
        str(source_path),
        str(png_path),
        section or "",
        run.report_id or "",
        methodology or "",
        target_field or "",
        evidence_scope or "",
        test_case_id or ""
    ]
    
    logger.info(f"[SOURCE_SNAPSHOT RENDER] Starting render_snapshot.js for {png_path.name}...")
    try:
        res = subprocess.run(
            [node_cmd] + args,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        logger.info(f"[SOURCE_SNAPSHOT RENDER STDOUT] {res.stdout.strip()}")
    except FileNotFoundError:
        # If 'node' is not in path, try hardcoded paths for this specific environment
        try:
            node_cmd = r"D:\Tools\node-v26.5.0-win-x64\node-v26.5.0-win-x64\node.exe"
            res = subprocess.run(
                [node_cmd] + args,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            logger.info(f"[SOURCE_SNAPSHOT RENDER STDOUT] {res.stdout.strip()}")
        except Exception as fallback_e:
            logger.error(f"[SOURCE_SNAPSHOT NODE ERROR] Node execution failed: {fallback_e}")
            raise HTTPException(status_code=404, detail=f"Visual source preview unavailable (Node not found: {str(fallback_e)})")
    except subprocess.CalledProcessError as e:
        logger.error(f"[SOURCE_SNAPSHOT PROCESS ERROR] Return code {e.returncode}. Stderr: {e.stderr}")
        raise HTTPException(status_code=404, detail=f"Visual source preview unavailable: {e.stderr or e.stdout}")
    except Exception as e:
        logger.error(f"[SOURCE_SNAPSHOT ERROR] {str(e)}")
        raise HTTPException(status_code=404, detail=f"Visual source preview unavailable ({str(e)})")

    if not png_path.exists() or png_path.stat().st_size == 0:
        logger.error(f"[SOURCE_SNAPSHOT MISSING] Output file {png_path} was not created or empty.")
        raise HTTPException(status_code=404, detail="Visual source preview unavailable (image not saved)")
        
    logger.info(f"[SOURCE_SNAPSHOT CREATED] {png_path} ({png_path.stat().st_size} bytes)")
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
    
    candidate_paths = [
        Path("jobs") / (run.job_id or "") / "evidence" / evidence_id,
        Path("jobs") / (run.job_id or "") / "evidence" / f"{evidence_id}.png",
        Path("runs") / str(run.id) / "evidence" / evidence_id,
        Path("runs") / str(run.id) / "evidence" / f"{evidence_id}.png",
    ]
    
    img_path = None
    for p in candidate_paths:
        if p.exists() and p.is_file() and p.stat().st_size > 0:
            img_path = p
            break
            
    if img_path is None:
        raise HTTPException(status_code=404, detail="Evidence image not found.")
        
    ext = img_path.suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(status_code=400, detail="Requested file is not a supported image type.")
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


# ═══════════════════════════════════════════════════════════════════════════════
# HITL (Human-in-the-Loop) Review API Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

class TestCaseReviewRequest(BaseModel):
    action: str  # FLAG_ISSUE, APPROVE, REJECT, CREATE_REVISION, UPDATE_SCENARIO
    issue_type: Optional[str] = None
    issue_comment: Optional[str] = None
    review_comments: Optional[str] = None
    duplicate_of_id: Optional[str] = None
    scenario_data: Optional[Dict[str, Any]] = None


class SuggestCorrectionRequest(BaseModel):
    issue_type: Optional[str] = ""
    issue_comment: Optional[str] = ""


class MissingScenarioRequest(BaseModel):
    what_to_test: str
    dsd_reference: str


class AddScenarioRequest(BaseModel):
    scenario: Dict[str, Any]


def _serialize_test_case_model(tc: CognosTestCaseModel, run_id: int) -> Dict[str, Any]:
    return {
        "id": tc.id,
        "run_id": tc.run_id,
        "test_case_id": tc.test_case_id,
        "report_id": tc.report_id,
        "category": tc.category,
        "test_case_title": tc.test_case_title,
        "requirement_id": tc.requirement_id,
        "objective": tc.objective,
        "preconditions": tc.preconditions,
        "test_data": tc.test_data,
        "test_steps": tc.test_steps,
        "expected_result": tc.expected_result,
        "validation_logic": tc.validation_logic,
        "source_section": tc.source_section,
        "source_page": tc.source_page,
        "source_table": tc.source_table,
        "source_column": tc.source_column,
        "processing_rule": tc.processing_rule,
        "formatting_rule": tc.formatting_rule,
        "priority": tc.priority,
        "status": tc.status,
        "origin": tc.origin,
        "version": tc.version or 1,
        "scenario_order": tc.scenario_order or 0,
        "notes": tc.notes,
        "open_questions": tc.open_questions,
        "evidence_references": tc.evidence_references,
        "review_status": tc.review_status or "GENERATED",
        "review_comments": tc.review_comments or "",
        "reviewer": tc.reviewer or "",
        "reviewed_at": tc.reviewed_at.isoformat() if tc.reviewed_at else None,
        "issue_type": tc.issue_type or "",
        "issue_comment": tc.issue_comment or "",
        "duplicate_of_id": tc.duplicate_of_id or "",
        "execution_method": tc.execution_method or "Scheduled",
        "execution_tool": tc.execution_tool or "IWA",
        "edit_history": tc.edit_history or [],
    }


@router.get("/runs/{run_id}/test-cases")
def get_run_test_cases(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """Retrieve all test cases for a run with up-to-date HITL review status."""
    run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    test_cases = (
        db.query(CognosTestCaseModel)
        .filter(CognosTestCaseModel.run_id == run_id)
        .order_by(CognosTestCaseModel.scenario_order.asc(), CognosTestCaseModel.id.asc())
        .all()
    )
    return {
        "run_id": run_id,
        "work_type": run.work_type,
        "work_item_id": run.work_item_id,
        "work_item_title": run.work_item_title,
        "test_cases": [_serialize_test_case_model(tc, run_id) for tc in test_cases],
    }


@router.patch("/runs/{run_id}/test-cases/{test_case_id}/review")
def review_test_case(
    run_id: int,
    test_case_id: str,
    payload: TestCaseReviewRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    Production-grade Human-in-the-Loop review transition:
    - FLAG_ISSUE: marks NEEDS_REVIEW, saves issue type & comment
    - APPROVE: marks APPROVED, locks scenario against silent modifications
    - REJECT: marks REJECTED (with optional duplicate reference)
    - CREATE_REVISION: unlocks approved scenario for new revision
    - UPDATE_SCENARIO: saves edits, creates version bump and diffs
    """
    tc = (
        db.query(CognosTestCaseModel)
        .filter(CognosTestCaseModel.run_id == run_id, CognosTestCaseModel.test_case_id == test_case_id)
        .first()
    )
    if not tc:
        raise HTTPException(status_code=404, detail=f"Test case '{test_case_id}' not found for run {run_id}.")

    action = (payload.action or "").upper().strip()
    history = list(tc.edit_history or [])
    now = datetime.now(timezone.utc)
    current_version = tc.version or 1

    if action == "APPROVE":
        # Validate required content before approval
        if not tc.test_case_title or not tc.objective or not tc.test_steps or not tc.expected_result:
            raise HTTPException(
                status_code=400,
                detail="Scenario cannot be approved: Scenario Name, Objective, Test Steps, and Expected Result are required."
            )
        tc.review_status = "APPROVED"
        tc.reviewer = current_user.username
        tc.reviewed_at = now
        if payload.review_comments:
            tc.review_comments = payload.review_comments

        history = record_history_entry(
            history,
            version=current_version,
            action_type="APPROVED",
            status="APPROVED",
            author=current_user.username,
            summary="Scenario approved and locked as authoritative specification.",
        )
        tc.edit_history = history

    elif action == "FLAG_ISSUE":
        tc.review_status = "NEEDS_REVIEW"
        tc.issue_type = payload.issue_type or "Other"
        tc.issue_comment = payload.issue_comment or ""
        if payload.review_comments:
            tc.review_comments = payload.review_comments

        history = record_history_entry(
            history,
            version=current_version,
            action_type="FLAG_ISSUE",
            status="NEEDS_REVIEW",
            author=current_user.username,
            summary=f"Flagged for review: {tc.issue_type}",
            issue_details={"issue_type": tc.issue_type, "comment": tc.issue_comment},
        )
        tc.edit_history = history

    elif action == "REJECT":
        tc.review_status = "REJECTED"
        if payload.duplicate_of_id:
            tc.duplicate_of_id = payload.duplicate_of_id
            summary = f"Marked as duplicate of {payload.duplicate_of_id}"
        else:
            summary = f"Rejected: {payload.issue_comment or 'Not needed'}"
        if payload.issue_comment:
            tc.issue_comment = payload.issue_comment

        history = record_history_entry(
            history,
            version=current_version,
            action_type="REJECT",
            status="REJECTED",
            author=current_user.username,
            summary=summary,
        )
        tc.edit_history = history

    elif action == "CREATE_REVISION":
        if tc.review_status != "APPROVED":
            raise HTTPException(
                status_code=400,
                detail="Revisions can only be created from Approved scenarios."
            )
        new_version = current_version + 1
        tc.version = new_version
        tc.review_status = "CORRECTED"
        history = record_history_entry(
            history,
            version=new_version,
            action_type="CREATE_REVISION",
            status="CORRECTED",
            author=current_user.username,
            summary=f"Created editable revision v{new_version} from approved v{current_version}.",
        )
        tc.edit_history = history

    elif action == "UPDATE_SCENARIO":
        if tc.review_status == "APPROVED":
            raise HTTPException(
                status_code=400,
                detail="Scenario is Approved and locked. Click 'Create Revision' to make modifications."
            )
        data = payload.scenario_data or {}
        old_data = _serialize_test_case_model(tc, run_id)
        diffs = compute_field_diffs(old_data, data)

        if "test_case_title" in data and data["test_case_title"]:
            tc.test_case_title = data["test_case_title"]
        if "objective" in data and data["objective"]:
            tc.objective = data["objective"]
        if "execution_method" in data:
            tc.execution_method = data["execution_method"]
        if "execution_tool" in data:
            tc.execution_tool = data["execution_tool"]
        if "report_id" in data and data["report_id"]:
            tc.report_id = data["report_id"]
        if "test_steps" in data and data["test_steps"]:
            steps = data["test_steps"]
            tc.test_steps = "\n".join(steps) if isinstance(steps, list) else str(steps)
        if "expected_result" in data and data["expected_result"]:
            tc.expected_result = data["expected_result"]
        if "review_comments" in data:
            tc.review_comments = data["review_comments"]

        new_version = current_version + 1
        tc.version = new_version
        tc.review_status = "CORRECTED"

        summary = f"Human edits saved (v{new_version})." if not diffs else f"Updated {len(diffs)} field(s)."
        history = record_history_entry(
            history,
            version=new_version,
            action_type="HUMAN_CORRECTED",
            status="CORRECTED",
            author=current_user.username,
            summary=summary,
            diffs=diffs,
        )
        tc.edit_history = history

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported review action '{action}'.")

    db.commit()
    db.refresh(tc)
    return {
        "status": "success",
        "action": action,
        "test_case": _serialize_test_case_model(tc, run_id),
    }


@router.post("/runs/{run_id}/test-cases/{test_case_id}/suggest-correction")
def suggest_correction(
    run_id: int,
    test_case_id: str,
    payload: SuggestCorrectionRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    AI Suggests a targeted correction without automatically applying it.
    Analyzes execution method rules (NH IWA vs ND UC4), DSD references, and user issues.
    """
    tc = (
        db.query(CognosTestCaseModel)
        .filter(CognosTestCaseModel.run_id == run_id, CognosTestCaseModel.test_case_id == test_case_id)
        .first()
    )
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found.")

    run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
    report_metadata = {
        "report_id": run.report_id if run else tc.report_id,
        "report_title": run.report_title if run else "",
        "frequency_type": "Scheduled",
    }
    if run and run.report_definition_json:
        meta_dict = run.report_definition_json.get("metadata", {})
        report_metadata["frequency_type"] = meta_dict.get("frequency_type", "Scheduled")
        report_metadata["dsd_profile"] = meta_dict.get("source_state_code", "NH")

    tc_dict = _serialize_test_case_model(tc, run_id)
    suggestion = generate_suggested_correction(
        tc_dict,
        issue_type=payload.issue_type or tc.issue_type or "",
        issue_comment=payload.issue_comment or tc.issue_comment or "",
        report_metadata=report_metadata,
    )
    return {
        "status": "success",
        "test_case_id": test_case_id,
        "suggestion": suggestion,
    }


@router.post("/runs/{run_id}/suggest-missing-scenario")
def suggest_missing_scenario(
    run_id: int,
    payload: MissingScenarioRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    AI proposes a missing scenario given 'what to test' and 'DSD reference'.
    Does NOT automatically add it to the suite until user accepts.
    """
    run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    existing_count = db.query(CognosTestCaseModel).filter(CognosTestCaseModel.run_id == run_id).count()

    proposed = generate_missing_scenario(
        what_to_test=payload.what_to_test,
        dsd_reference=payload.dsd_reference,
        report_id=run.report_id or "PRV-INT-027",
        report_title=run.report_title or "Cognos Report",
        existing_count=existing_count,
    )
    return {
        "status": "success",
        "proposed_scenario": proposed,
    }


@router.post("/runs/{run_id}/add-scenario")
def add_missing_scenario(
    run_id: int,
    payload: AddScenarioRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    Persists an accepted missing scenario into the run's test suite.
    """
    run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")

    sc = payload.scenario or {}
    existing_count = db.query(CognosTestCaseModel).filter(CognosTestCaseModel.run_id == run_id).count()

    tc_id = sc.get("test_case_id") or f"TC-NEW-{existing_count + 1:02d}"
    init_history = [{
        "version": 1,
        "action": "HUMAN_ADDED",
        "status": "GENERATED",
        "author": current_user.username,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": "Added via Missing Scenario creation",
    }]

    tc_model = CognosTestCaseModel(
        run_id=run.id,
        test_case_id=tc_id,
        report_id=sc.get("report_id") or run.report_id or "PRV-INT-027",
        category=sc.get("category") or "Custom Validation",
        test_case_title=sc.get("test_case_title") or f"Verify {sc.get('category', 'Custom')}",
        requirement_id=sc.get("requirement_id") or "",
        objective=sc.get("objective") or "",
        preconditions=sc.get("preconditions") or "",
        test_data=sc.get("test_data") or "",
        test_steps=sc.get("test_steps") or "",
        expected_result=sc.get("expected_result") or "",
        validation_logic=sc.get("validation_logic") or "",
        source_section=sc.get("source_section") or "Report Specification",
        source_page=sc.get("source_page"),
        source_table=sc.get("source_table") or "",
        source_column=sc.get("source_column") or "",
        priority=sc.get("priority") or "Medium",
        status="Generated",
        origin="USER_ADDED",
        version=1,
        scenario_order=(existing_count + 1) * 10,
        review_status="GENERATED",
        execution_method=sc.get("execution_method") or "Scheduled",
        execution_tool=sc.get("execution_tool") or "IWA",
        edit_history=init_history,
    )
    db.add(tc_model)
    db.commit()
    db.refresh(tc_model)

    return {
        "status": "success",
        "test_case": _serialize_test_case_model(tc_model, run_id),
    }
