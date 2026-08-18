import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.outbox import OutboxEvent

class OutboxService:
    @staticmethod
    def create_event(
        db: Session,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload_reference: str
    ) -> OutboxEvent:
        event = OutboxEvent(
            outbox_id=str(uuid.uuid4()),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload_reference=payload_reference,
            status="PENDING"
        )
        db.add(event)
        return event

    @staticmethod
    def mark_published(db: Session, outbox_id: str):
        event = db.query(OutboxEvent).filter(OutboxEvent.outbox_id == outbox_id).with_for_update().first()
        if event and event.status == "PENDING":
            event.status = "PUBLISHED"
            event.published_at = datetime.now(timezone.utc)

    @staticmethod
    def mark_failed(db: Session, outbox_id: str, error: str):
        event = db.query(OutboxEvent).filter(OutboxEvent.outbox_id == outbox_id).with_for_update().first()
        if event:
            event.status = "FAILED"
            event.last_error = error
            event.attempt_count += 1
