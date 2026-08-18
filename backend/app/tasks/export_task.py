import json
import hashlib
from datetime import datetime, timezone
from app.worker import celery_app
from app.db.session import SessionLocal
from app.models.job import BackgroundJob
from app.models.delivery import ExternalDeliveryRecord
from app.services.job_service import JobService
from app.services.outbox_service import OutboxService
from app.services.export_service import sync_and_notify, SharePointSyncError, EmailSendError
from app.core.telemetry import get_logger

_logger = get_logger(__name__)

@celery_app.task(bind=True, max_retries=3)
def execute_export(self, outbox_id: str, job_id: str):
    db = SessionLocal()
    try:
        # 1. ACK Outbox
        OutboxService.mark_published(db, outbox_id)
        
        job = db.query(BackgroundJob).filter(BackgroundJob.job_id == job_id).first()
        if not job:
            return

        # 2. Transition
        JobService.transition_to(db, job, "RUNNING", worker_id=self.request.hostname)
        db.commit()

        # 3. Parse Payload
        payload = json.loads(job.payload_reference)
        session_id = payload["session_id"]
        report_id = payload["report_id"]
        sharepoint_site = payload.get("sharepoint_site")
        email_to = payload.get("email_to")

        # Basic hash of inputs for idempotency
        artifact_id = f"{session_id}_{report_id}"
        artifact_hash = hashlib.sha256(artifact_id.encode()).hexdigest()

        # 4. Check Idempotency before executing Business Logic
        # (This is a simplistic check; a more robust one would integrate tightly inside the sync_and_notify logic,
        # but the prompt allows application-level wrapper idempotency.)
        
        sp_delivered = False
        if sharepoint_site:
            record = db.query(ExternalDeliveryRecord).filter_by(
                target_system="SHAREPOINT",
                target_address=sharepoint_site,
                artifact_hash=artifact_hash,
                status="DELIVERED"
            ).first()
            if record:
                sp_delivered = True

        email_delivered = False
        if email_to:
            record = db.query(ExternalDeliveryRecord).filter_by(
                target_system="SMTP",
                target_address=email_to,
                artifact_hash=artifact_hash,
                status="DELIVERED"
            ).first()
            if record:
                email_delivered = True

        # Call service, potentially telling it what to skip
        # Note: sync_and_notify might need to be refactored to accept skip_sp and skip_email flags.
        # Assuming we just execute if either is NOT delivered, and the service handles it or we wrap it.
        # If both are requested and already delivered, skip entirely.
        if (sharepoint_site and not sp_delivered) or (email_to and not email_delivered):
            try:
                sync_and_notify(
                    db=db,
                    session_id=session_id,
                    report_id=report_id,
                    sharepoint_site=sharepoint_site if not sp_delivered else None,
                    email_to=email_to if not email_delivered else None
                )
                
                # Record successful delivery
                if sharepoint_site and not sp_delivered:
                    db.add(ExternalDeliveryRecord(
                        delivery_id=f"SP-{job.job_id}",
                        job_id=job.job_id,
                        target_system="SHAREPOINT",
                        target_address=sharepoint_site,
                        artifact_hash=artifact_hash,
                        status="DELIVERED",
                        delivered_at=datetime.now(timezone.utc)
                    ))
                if email_to and not email_delivered:
                    db.add(ExternalDeliveryRecord(
                        delivery_id=f"SMTP-{job.job_id}",
                        job_id=job.job_id,
                        target_system="SMTP",
                        target_address=email_to,
                        artifact_hash=artifact_hash,
                        status="DELIVERED",
                        delivered_at=datetime.now(timezone.utc)
                    ))
            except (SharePointSyncError, EmailSendError) as service_exc:
                raise service_exc # Transient
        
        JobService.transition_to(db, job, "SUCCEEDED")
        db.commit()

    except Exception as exc:
        db.rollback()
        is_transient = isinstance(exc, (SharePointSyncError, EmailSendError))
        try:
            job = db.query(BackgroundJob).filter(BackgroundJob.job_id == job_id).first()
            if job:
                JobService.mark_failed_or_retry(db, job, str(exc), is_transient=is_transient)
                db.commit()
                
            if job and job.status == "RETRYING":
                self.retry(exc=exc, countdown=2 ** self.request.retries)
        except Exception as retry_exc:
            raise retry_exc
        raise exc
    finally:
        db.close()
