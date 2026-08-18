from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, UniqueConstraint
from app.db.session import Base

class ExternalDeliveryRecord(Base):
    """Tracks idempotency for external effects like SharePoint and SMTP."""
    __tablename__ = "external_delivery_records"

    id = Column(Integer, primary_key=True, index=True)
    delivery_id = Column(String, index=True, unique=True, nullable=False)
    job_id = Column(String, index=True, nullable=False)
    
    target_system = Column(String, index=True, nullable=False) # e.g., 'SHAREPOINT', 'SMTP'
    target_address = Column(String, nullable=False) # e.g., 'https://site/library', 'user@domain.com'
    
    artifact_hash = Column(String, index=True, nullable=False)
    external_identifier = Column(String, nullable=True) # e.g., SP Item ID, SMTP Message-ID
    
    status = Column(String, index=True, default="DELIVERED") # PENDING, DELIVERED, FAILED
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    
    # Ensure we don't deliver the exact same artifact to the exact same target system twice accidentally
    __table_args__ = (
        UniqueConstraint('target_system', 'target_address', 'artifact_hash', name='uq_delivery_artifact'),
    )
