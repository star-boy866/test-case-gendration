from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, Float

from app.db.session import Base

class BackgroundJob(Base):
    """Enterprise job tracking model."""
    __tablename__ = "background_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, index=True, unique=True, nullable=False)
    job_type = Column(String, index=True, nullable=False)
    status = Column(String, index=True, default="QUEUED")  # QUEUED, RUNNING, RETRYING, SUCCEEDED, FAILED, CANCEL_REQUESTED, CANCELLED, EXPIRED
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    requested_by = Column(String, index=True, nullable=False)
    correlation_id = Column(String, index=True, nullable=True)
    idempotency_key = Column(String, index=True, unique=True, nullable=True)

    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    priority = Column(Integer, default=0)

    worker_id = Column(String, index=True, nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)

    progress = Column(Float, nullable=True)
    progress_message = Column(String, nullable=True)

    payload_reference = Column(Text, nullable=True) # Not full payload, usually just JSON kwargs referencing DB IDs
    result_reference = Column(Text, nullable=True)

    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    version = Column(Integer, default=1)
