"""
Export endpoints — Phase 7 (Excel Compiler) + Phase 8 (SharePoint sync,
email distribution), reusing ExportRecord rather than a new table.
"""

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.rbac import require_role, CurrentUser
from app.services.export_service import (
    export_session_to_excel,
    get_latest_export,
    sync_and_notify,
    ExportError,
)
from app.core.config import settings
from app.core.telemetry import get_logger

_logger = get_logger(__name__)

router = APIRouter(prefix="/api/export", tags=["export"])


class ExportRequest(BaseModel):
    session_id: int
    sync_to_sharepoint: bool = False
    email_distribution_list: Optional[List[str]] = None
    # Optional: the frontend's most-recently-seen Critic score for this
    # session, if it has one handy, purely for display in the email — see
    # email_service.build_export_email's docstring for why this isn't
    # computed server-side.
    quality_score: Optional[float] = None


class ExportResponse(BaseModel):
    session_id: int
    filename: str
    file_sha256: str
    row_count: int
    excel_download_url: str
    sharepoint_url: Optional[str] = None
    sharepoint_error: Optional[str] = None
    email_sent: bool = False
    email_error: Optional[str] = None
    message: str


@router.post("/finalize", response_model=ExportResponse)
def finalize_export(
    payload: ExportRequest,
    db: Session = Depends(get_db),
    # Exporting (and optionally pushing to SharePoint / emailing a
    # distribution list) is a release-worthy action, same trust tier as
    # confirming Gatekeeper scope — per core/rbac.py's design, 'approver'
    # or higher. `exported_by` used to be client-supplied free text with
    # no authentication behind it; now it's always the real authenticated
    # identity.
    current_user: CurrentUser = Depends(require_role("approver")),
):
    try:
        record = export_session_to_excel(
            db, session_id=payload.session_id, exported_by=current_user.username,
        )
    except ExportError as e:
        raise HTTPException(status_code=400, detail=str(e))

    job_id = None
    if payload.sync_to_sharepoint or payload.email_distribution_list:
        from app.services.job_service import JobService
        from app.services.outbox_service import OutboxService
        from app.tasks.export_task import execute_export
        import json

        job_payload = json.dumps({
            "session_id": record.session_id,
            "report_id": record.report_id,
            "sharepoint_site": settings.SHAREPOINT_SITE_URL if payload.sync_to_sharepoint else None,
            "email_distribution_list": payload.email_distribution_list
        })

        job = JobService.create_job(
            db=db,
            job_type="EXPORT_SYNC",
            requested_by=current_user.username,
            correlation_id=str(record.report_id),
            idempotency_key=f"export_{record.session_id}_{record.file_sha256}",
            payload_reference=job_payload
        )
        
        outbox_event = OutboxService.create_event(
            db=db,
            event_type="CELERY_TASK_ENQUEUE",
            aggregate_type="BackgroundJob",
            aggregate_id=str(job.job_id),
            payload_reference=json.dumps({"task": "execute_export", "job_id": str(job.job_id)})
        )
        
        db.commit()
        job_id = job.job_id
        
        try:
            execute_export.delay(outbox_id=str(outbox_event.outbox_id), job_id=str(job.job_id))
        except Exception as e:
            _logger.error("redis_unavailable_during_enqueue", error=str(e))

    message = f"Excel workbook generated with {record.row_count} scenario(s)."
    if job_id:
        message += " External syncing queued in background."

    return ExportResponse(
        session_id=int(str(record.session_id)),
        filename=str(record.filename),
        file_sha256=str(record.file_sha256),
        row_count=int(str(record.row_count)),
        excel_download_url=f"/api/export/{record.session_id}/download",
        sharepoint_url=None,
        sharepoint_error=None,
        email_sent=False,
        email_error=None,
        message=message,
        # In a real API we might return job_id here or HTTP 202, 
        # but to keep existing clients somewhat compatible we just append the message
    )


@router.get("/{session_id}/download")
def download_latest_export(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    record = get_latest_export(db, session_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"No export has been generated yet for session {session_id}. "
                    f"Call POST /api/export/finalize first.",
        )

    path = Path(str(record.file_path))
    if not path.exists():
        raise HTTPException(
            status_code=410,
            detail=f"Export record exists but the file is no longer on disk "
                    f"({record.file_path}). Re-run POST /api/export/finalize.",
        )

    return FileResponse(
        path,
        filename=str(record.filename),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
