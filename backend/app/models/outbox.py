from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text
from app.db.session import Base

class OutboxEvent(Base):
    """Transactional outbox for durable queue publication."""
    __tablename__ = "outbox_events"

    id = Column(Integer, primary_key=True, index=True)
    outbox_id = Column(String, index=True, unique=True, nullable=False)
    event_type = Column(String, index=True, nullable=False)
    aggregate_type = Column(String, index=True, nullable=False)
    aggregate_id = Column(String, index=True, nullable=False)
    
    payload_reference = Column(Text, nullable=False)
    
    status = Column(String, index=True, default="PENDING")  # PENDING, PUBLISHED, FAILED
    attempt_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime(timezone=True), nullable=True)
