import json
from datetime import datetime, timezone
from app.worker import celery_app
from app.db.session import SessionLocal
from app.models.job import BackgroundJob
from app.services.job_service import JobService
from app.services.outbox_service import OutboxService
from app.services.judge_service import evaluate_and_store
from app.services.ollama_client import default_llm_call
from app.core.telemetry import get_logger

_logger = get_logger(__name__)

@celery_app.task(bind=True, max_retries=3)
def execute_judge(self, outbox_id: str, job_id: str):
    db = SessionLocal()
    try:
        # 1. ACK Outbox publication
        OutboxService.mark_published(db, outbox_id)
        
        job = db.query(BackgroundJob).filter(BackgroundJob.job_id == job_id).first()
        if not job:
            _logger.error("judge_task_no_job", job_id=job_id)
            return

        # 2. State transition QUEUED -> RUNNING
        JobService.transition_to(db, job, "RUNNING", worker_id=self.request.hostname)
        db.commit()

        # 3. Parse Payload
        payload = json.loads(job.payload_reference)
        session_id = payload["session_id"]
        report_id = payload["report_id"]
        scenarios = payload["scenarios"]
        context_slice = payload["context_slice"]
        requirement = payload["requirement"]

        # 4. Execute pure business logic
        evaluate_and_store(
            session_id=session_id,
            report_id=report_id,
            scenarios=scenarios,
            context_slice=context_slice,
            requirement=requirement,
            llm_call=default_llm_call
        )
        
        # 5. State transition RUNNING -> SUCCEEDED
        JobService.transition_to(db, job, "SUCCEEDED")
        db.commit()

    except Exception as exc:
        db.rollback()
        # Non-transient failure vs transient could be separated here
        # For LLM, we consider it transient and retry
        try:
            job = db.query(BackgroundJob).filter(BackgroundJob.job_id == job_id).first()
            if job:
                JobService.mark_failed_or_retry(db, job, str(exc), is_transient=True)
                db.commit()
                
            if job and job.status == "RETRYING":
                self.retry(exc=exc, countdown=2 ** self.request.retries)
        except Exception as retry_exc:
            _logger.error("judge_task_retry_failed", error=str(retry_exc))
            raise retry_exc
        raise exc
    finally:
        db.close()
