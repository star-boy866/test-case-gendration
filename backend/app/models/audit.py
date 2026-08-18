"""
Metadata/audit ORM models.

Phase 0: table shapes only, to establish the schema early and let the
frontend/backend contract stabilize. Immutability enforcement, hashing,
and RBAC integration land in Phase 9.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Text

from app.db.session import Base


class Session(Base):
    """One record per user working session through the 4-step workflow."""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    cr_id = Column(String, nullable=True, index=True)
    cr_description = Column(Text, nullable=True)
    report_id = Column(String, nullable=True, index=True)
    status = Column(String, default="ingestion")  # ingestion | gatekeeper_confirmed | refinement | exported
    confirmed_at = Column(DateTime, nullable=True)
    confirmed_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AuditLogEntry(Base):
    """
    Append-only audit trail. Immutability is enforced two ways (see
    app/core/immutable_audit.py, which registers the actual SQLAlchemy
    event listeners — kept in a separate module so this file stays a pure
    schema definition):

    1. ORM-level guards block any UPDATE/DELETE issued through SQLAlchemy.
    2. `chain_hash` makes tampering that bypasses the ORM entirely (e.g. a
       raw sqlite3 edit of the database file) detectable, not just
       forbidden — each row's hash covers its own fields AND the previous
       row's hash, so altering any historical row breaks the chain from
       that point forward. verify_audit_chain() in the same module walks
       the table and reports exactly where a chain breaks.
    """

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = Column(String, nullable=False)
    session_id = Column(Integer, nullable=True)
    event_type = Column(String, nullable=False)  # e.g. UPLOAD, CONFIRM_GATEKEEPER, EXPORT, EMAIL_SENT
    detail = Column(Text, nullable=True)
    file_sha256 = Column(String, nullable=True)
    chain_hash = Column(String, nullable=True)  # set automatically by a before_insert event listener

# Note: the Phase 0 "CacheMetadata" stub that used to live here has been
# superseded by SemanticCacheEntry in app/models/cache.py (Phase 3), which
# stores the full cached payload alongside its vector-index id rather than
# just a pointer. Nothing referenced the old stub, so it was removed rather
# than migrated.
