from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "healthcare_testgen_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_BROKER_URL,  # Optional: using Redis for result backend as well
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Configure Celery to acknowledge task completion only after successful execution
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Explicitly import modules containing tasks so Celery registers them
celery_app.conf.imports = [
    "app.tasks.judge_task",
    "app.tasks.export_task"
]
