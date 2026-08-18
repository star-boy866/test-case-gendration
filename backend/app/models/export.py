"""
Export Record ORM model — Phase 7, extended in Phase 8.

One row per generated Excel workbook. Exists so GET /api/export/{session_id}/download
can serve "the latest export for this session" without scanning the
filesystem, and so the SHA-256 of every exported artifact is tracked the
same way source document hashes are (Phase 1) — consistent integrity
tracking across the whole pipeline.

Phase 8 adds sharepoint_url and email_sent_to here rather than inventing a
new table, exactly as this docstring originally promised.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from app.db.session import Base


class ExportRecord(Base):
    __tablename__ = "export_records"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    report_id = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_sha256 = Column(String, nullable=False)
    row_count = Column(Integer, nullable=False)
    exported_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # --- Phase 8 ---
    sharepoint_url = Column(String, nullable=True)
    email_sent_to = Column(String, nullable=True)  # AES-256-GCM ciphertext (see core/encryption.py), NOT plaintext — comma-joined recipient list, encrypted at rest
