import json
import hashlib
from datetime import datetime, timezone
from app.worker import celery_app
from app.db.session import SessionLocal
from app.models.job import BackgroundJob
from app.models.delivery import ExternalDeliveryRecord
from app.services.job_service import JobService
from app.services.outbox_service import OutboxService
from app.services.export_service import sync_and_notify, get_latest_export, SharePointSyncError, EmailSendError
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
        email_distribution_list = payload.get("email_distribution_list") or []

        # Basic hash of inputs for idempotency
        artifact_id = f"{session_id}_{report_id}"
        artifact_hash = hashlib.sha256(artifact_id.encode()).hexdigest()

        # 4. Check Idempotency before executing Business Logic
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

        undelivered_emails = []
        for email in email_distribution_list:
            record = db.query(ExternalDeliveryRecord).filter_by(
                target_system="SMTP",
                target_address=email,
                artifact_hash=artifact_hash,
                status="DELIVERED"
            ).first()
            if not record:
                undelivered_emails.append(email)

        if (sharepoint_site and not sp_delivered) or undelivered_emails:
            export_record = get_latest_export(db, session_id)
            if not export_record:
                raise ValueError(f"No export record found for session {session_id}")
                
            result = sync_and_notify(
                db=db,
                record=export_record,
                sync_to_sharepoint=bool(sharepoint_site and not sp_delivered),
                email_distribution_list=undelivered_emails if undelivered_emails else None
            )
            
            # Record successful delivery
            if sharepoint_site and not sp_delivered:
                if result.get("sharepoint_error"):
                    raise SharePointSyncError(result["sharepoint_error"])
                db.add(ExternalDeliveryRecord(
                    delivery_id=f"SP-{job.job_id}",
                    job_id=job.job_id,
                    target_system="SHAREPOINT",
                    target_address=sharepoint_site,
                    artifact_hash=artifact_hash,
                    status="DELIVERED",
                    delivered_at=datetime.now(timezone.utc)
                ))
            
            if undelivered_emails:
                if result.get("email_error"):
                    raise EmailSendError(result["email_error"])
                for idx, email in enumerate(undelivered_emails):
                    db.add(ExternalDeliveryRecord(
                        delivery_id=f"SMTP-{job.job_id}-{idx}",
                        job_id=job.job_id,
                        target_system="SMTP",
                        target_address=email,
                        artifact_hash=artifact_hash,
                        status="DELIVERED",
                        delivered_at=datetime.now(timezone.utc)
                    ))
        
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
