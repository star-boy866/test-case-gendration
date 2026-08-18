from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.rbac import require_role, CurrentUser
from app.models.job import BackgroundJob

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

@router.get("/{job_id}")
def get_job_status(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    job = db.query(BackgroundJob).filter(BackgroundJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Authorization logic (Tenant/User Isolation as required by the prompt)
    if job.requested_by != current_user.username:
        # A user must not be able to query another user's job unless they are admins.
        # Here we enforce strict isolation.
        raise HTTPException(status_code=403, detail="Unauthorized to view this job")

    return {
        "job_id": job.job_id,
        "job_type": job.job_type,
        "status": job.status,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "updated_at": job.updated_at,
        "completed_at": job.completed_at,
        "attempt_count": job.attempt_count,
        "progress": job.progress,
        "correlation_id": job.correlation_id,
    }
