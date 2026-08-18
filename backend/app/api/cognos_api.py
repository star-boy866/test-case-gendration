"""
API Endpoints for Cognos Report Definition → Test Case Generation workflow.
"""

import tempfile
from pathlib import Path
from datetime import datetime, timezone
import hashlib

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
    ext = Path(file.filename).suffix.lower()
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
        pipeline_result = run_cognos_pipeline(tmp_path, file.filename)
        
        # Save results to DB
        run = CognosGenerationRun(
            report_id=pipeline_result.report_definition.metadata.report_id or "UNKNOWN",
            report_title=pipeline_result.report_definition.metadata.report_title,
            source_document=file.filename,
            source_document_sha256=file_hash,
            llm_provider=getattr(settings, "LLM_PROVIDER", "None"),
            llm_model=getattr(settings, "GROK_MODEL", "None"),
            requirements_extracted=pipeline_result.requirement_set.total_extracted,
            test_cases_generated=len(pipeline_result.test_suite.test_cases),
            coverage_percentage=pipeline_result.test_suite.coverage.overall_coverage_percentage,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            requested_by=current_user.username
        )
        db.add(run)
        db.flush()  # To get run.id
        
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
            req_internal_id = req_mapping.get(tc.requirement_id)
            
            tc_model = CognosTestCaseModel(
                run_id=run.id,
                requirement_internal_id=req_internal_id,
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
                open_questions=tc.open_questions
            )
            db.add(tc_model)
            
        db.commit()
        
        return {
            "run_id": run.id,
            "report_id": run.report_id,
            "status": "success",
            "summary": pipeline_result.test_suite.summary.model_dump(),
            "coverage": pipeline_result.test_suite.coverage.model_dump(),
            "test_cases": [tc.model_dump() for tc in pipeline_result.test_suite.test_cases]
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Cognos DOCX: {str(e)}"
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.get("/runs/{run_id}/export/excel")
def export_run_to_excel(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    Generate and download the 20+ column Excel workbook for a given run.
    """
    run = db.query(CognosGenerationRun).filter(CognosGenerationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
        
    from app.domain.cognos_test_case import TestSuite, CognosTestCase, CoverageReport, SpecificationQualityReport
    
    # Rehydrate test cases
    test_cases = []
    for tc_model in run.test_cases:
        tc = CognosTestCase(
            test_case_id=tc_model.test_case_id,
            report_id=tc_model.report_id,
            category=tc_model.category,
            test_case_title=tc_model.test_case_title,
            requirement_id=tc_model.requirement_id,
            objective=tc_model.objective,
            preconditions=tc_model.preconditions,
            test_data=tc_model.test_data,
            test_steps=tc_model.test_steps,
            expected_result=tc_model.expected_result,
            validation_logic=tc_model.validation_logic,
            source_section=tc_model.source_section,
            source_page=tc_model.source_page,
            source_table=tc_model.source_table,
            source_column=tc_model.source_column,
            processing_rule=tc_model.processing_rule,
            formatting_rule=tc_model.formatting_rule,
            priority=tc_model.priority,
            status=tc_model.status,
            origin=tc_model.origin,
            version=tc_model.version,
            notes=tc_model.notes,
            open_questions=tc_model.open_questions,
        )
        test_cases.append(tc)
        
    # Build dummy coverage and quality reports for export (in full implementation, we persist these too)
    coverage = CoverageReport(
        report_id=run.report_id,
        total_requirements=run.requirements_extracted,
        requirements_covered=len(test_cases), # Approximation
        overall_coverage_percentage=run.coverage_percentage,
    )
    
    from app.domain.cognos_models import ReportDefinition, ReportMetadata
    from app.domain.cognos_requirement import RequirementSet
    from app.domain.reporting_context import FinalReportContext
    
    ts = TestSuite(
        report_id=run.report_id,
        report_title=run.report_title,
        test_cases=test_cases,
        coverage=coverage,
        quality_report=SpecificationQualityReport(report_id=run.report_id, requirements_found=run.requirements_extracted),
    )
    ts.compute_summary()
    
    ctx = FinalReportContext(
        report_definition=ReportDefinition(metadata=ReportMetadata(report_id=run.report_id, report_title=run.report_title)),
        requirement_set=RequirementSet(report_id=run.report_id),
        test_suite=ts,
    )
    
    wb = build_cognos_workbook(ctx, generated_at=run.completed_at)
    
    # Save to temp file and return
    export_dir = Path(settings.EXPORT_DIR)
    export_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"Cognos_UT_{run.report_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    export_path = export_dir / filename
    
    wb.save(export_path)
    
    return FileResponse(
        path=export_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
