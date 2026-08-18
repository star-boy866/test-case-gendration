import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.job import BackgroundJob
from app.models.outbox import OutboxEvent

class JobStateError(Exception):
    pass

class JobService:
    @staticmethod
    def create_job(
        db: Session,
        job_type: str,
        requested_by: str,
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        payload_reference: Optional[str] = None,
        max_attempts: int = 3,
        priority: int = 0
    ) -> BackgroundJob:
        if idempotency_key:
            existing = db.query(BackgroundJob).filter(BackgroundJob.idempotency_key == idempotency_key).first()
            if existing:
                return existing

        job = BackgroundJob(
            job_id=str(uuid.uuid4()),
            job_type=job_type,
            status="QUEUED",
            requested_by=requested_by,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            payload_reference=payload_reference,
            attempt_count=0,
            max_attempts=max_attempts,
            priority=priority,
        )
        db.add(job)
        return job

    @staticmethod
    def transition_to(db: Session, job: BackgroundJob, new_status: str, worker_id: Optional[str] = None, error_message: Optional[str] = None, result_reference: Optional[str] = None):
        valid_transitions = {
            "QUEUED": ["RUNNING", "CANCEL_REQUESTED", "EXPIRED"],
            "RUNNING": ["SUCCEEDED", "RETRYING", "FAILED", "CANCEL_REQUESTED"],
            "CANCEL_REQUESTED": ["CANCELLED", "FAILED"],
            "RETRYING": ["QUEUED", "RUNNING", "FAILED"],
        }
        
        # Self transitions are okay (e.g. RUNNING -> RUNNING for heartbeats)
        if job.status != new_status and new_status not in valid_transitions.get(job.status, []):
            raise JobStateError(f"Invalid transition from {job.status} to {new_status}")

        job.status = new_status
        job.updated_at = datetime.now(timezone.utc)
        
        if new_status == "RUNNING":
            if not job.started_at:
                job.started_at = datetime.now(timezone.utc)
            if worker_id:
                job.worker_id = worker_id
            job.heartbeat_at = datetime.now(timezone.utc)
        elif new_status in ["SUCCEEDED", "FAILED", "CANCELLED", "EXPIRED"]:
            job.completed_at = datetime.now(timezone.utc)
            if result_reference:
                job.result_reference = result_reference
            if error_message:
                job.error_message = error_message
        elif new_status == "RETRYING":
            job.attempt_count += 1
            if error_message:
                job.error_message = error_message

    @staticmethod
    def heartbeat(db: Session, job: BackgroundJob):
        if job.status == "RUNNING":
            job.heartbeat_at = datetime.now(timezone.utc)

    @staticmethod
    def mark_failed_or_retry(db: Session, job: BackgroundJob, error_message: str, is_transient: bool):
        if is_transient and job.attempt_count < job.max_attempts:
            JobService.transition_to(db, job, "RETRYING", error_message=error_message)
        else:
            JobService.transition_to(db, job, "FAILED", error_message=error_message)
