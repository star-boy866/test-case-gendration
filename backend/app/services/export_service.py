"""
Export orchestration — Phase 7 (Excel), extended in Phase 8 (SharePoint +
email).

Wires excel_compiler.build_workbook() (pure, DB-free) to the actual
session/grid/source-document data and disk persistence. Kept separate from
excel_compiler.py specifically so the workbook-building logic stays
testable without sqlalchemy (see tests/test_excel_compiler.py) while this
module carries all the DB/filesystem side effects.

Phase 8 adds `sync_and_notify()`, which best-effort uploads an already-
generated export to SharePoint and/or emails a distribution list — see
that function's own docstring for the partial-success semantics.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit import AuditLogEntry, Session as SessionModel
from app.models.export import ExportRecord
from app.models.knowledge_base import SourceDocument
from app.services.excel_compiler import build_workbook
from app.services.refinement import get_grid
from app.services.sharepoint_client import upload_file, SharePointSyncError
from app.services.email_service import send_export_notification, EmailSendError
from app.core.encryption import encrypt_field, EncryptionNotConfiguredError
from app.core.telemetry import get_logger

_logger = get_logger(__name__)


class ExportError(Exception):
    """Raised when an export can't proceed (missing session, empty grid, etc.)."""


def _compute_sha256(path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _safe_filename(report_id: str, session_id: int, timestamp: datetime) -> str:
    # Keep it filesystem-safe: alphanumeric/dash/underscore only.
    safe_report_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in report_id)
    ts = timestamp.strftime("%Y%m%dT%H%M%SZ")
    return f"{safe_report_id}_session{session_id}_{ts}.xlsx"


def export_session_to_excel(
    db: Session,
    *,
    session_id: int,
    exported_by: str | None = None,
) -> ExportRecord:
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if session is None:
        raise ExportError(f"No session id={session_id}.")

    grid_rows = get_grid(db, session_id)
    if not grid_rows:
        raise ExportError(
            f"Session {session_id} has no scenarios in its Refinement Grid yet — "
            f"generate or manually add at least one before exporting."
        )

    source_documents = [
        {
            "filename": doc.filename,
            "file_sha256": doc.file_sha256,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else "",
        }
        for doc in (
            db.query(SourceDocument)
            .filter(SourceDocument.report_id == session.report_id)
            .order_by(SourceDocument.uploaded_at)
            .all()
        )
    ]

    generated_at = datetime.now(timezone.utc)
    workbook = build_workbook(
        grid_rows,
        report_id=session.report_id,
        cr_id=session.cr_id,
        cr_description=session.cr_description,
        source_documents=source_documents,
        generated_at=generated_at,
    )

    export_dir = Path(settings.EXPORT_DIR)
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(session.report_id, session_id, generated_at)
    file_path = export_dir / filename
    workbook.save(file_path)

    file_hash = _compute_sha256(file_path)

    record = ExportRecord(
        session_id=session_id,
        report_id=session.report_id,
        filename=filename,
        file_path=str(file_path),
        file_sha256=file_hash,
        row_count=len(grid_rows),
        exported_by=exported_by,
    )
    db.add(record)

    db.add(AuditLogEntry(
        user_id=exported_by or "unknown",
        session_id=session_id,
        event_type="EXPORT",
        detail=(
            f'{{"report_id": "{session.report_id}", "row_count": {len(grid_rows)}, '
            f'"filename": "{filename}"}}'
        ),
        file_sha256=file_hash,
    ))

    db.commit()
    db.refresh(record)
    return record


def get_latest_export(db: Session, session_id: int) -> ExportRecord | None:
    return (
        db.query(ExportRecord)
        .filter(ExportRecord.session_id == session_id)
        .order_by(ExportRecord.id.desc())
        .first()
    )


def sync_and_notify(
    db: Session,
    *,
    record: ExportRecord,
    sync_to_sharepoint: bool,
    email_distribution_list: list[str] | None,
    requested_by: str | None = None,
    quality_score: float | None = None,
) -> dict:
    """
    Best-effort SharePoint sync + email notification for an already-created
    ExportRecord. Deliberately uses PARTIAL-SUCCESS semantics: the Excel
    file itself was already generated and is already downloadable by the
    time this runs, so a SharePoint or email failure is reported back to
    the caller (and logged) rather than raised — there's no reason a
    misconfigured mail server should make an otherwise-successful export
    look like it failed.

    Returns {"sharepoint_url": str|None, "sharepoint_error": str|None,
             "email_sent": bool, "email_error": str|None}.
    """
    session = db.query(SessionModel).filter(SessionModel.id == record.session_id).first()
    result = {
        "sharepoint_url": None,
        "sharepoint_error": None,
        "email_sent": False,
        "email_error": None,
    }

    if sync_to_sharepoint:
        try:
            upload_result = upload_file(record.file_path, record.filename)
            record.sharepoint_url = upload_result["web_url"]
            result["sharepoint_url"] = upload_result["web_url"]

            db.add(AuditLogEntry(
                user_id=requested_by or "unknown",
                session_id=record.session_id,
                event_type="SHAREPOINT_SYNC",
                detail=json.dumps({"filename": record.filename, "web_url": upload_result["web_url"]}),
                file_sha256=record.file_sha256,
            ))
        except SharePointSyncError as e:
            result["sharepoint_error"] = str(e)
            db.add(AuditLogEntry(
                user_id=requested_by or "unknown",
                session_id=record.session_id,
                event_type="SHAREPOINT_SYNC_FAILED",
                detail=json.dumps({"filename": record.filename, "error": str(e)}),
                file_sha256=record.file_sha256,
            ))

    if email_distribution_list:
        try:
            send_export_notification(
                to_addresses=email_distribution_list,
                report_id=record.report_id,
                cr_id=session.cr_id if session else None,
                scenario_count=record.row_count,
                filename=record.filename,
                quality_score=quality_score,
                sharepoint_url=result["sharepoint_url"],
            )
            result["email_sent"] = True

            # Encrypt at rest per Phase 9's Security requirement (AES-256).
            # This field is genuinely PII (real recipient email addresses).
            # The audit log entries below intentionally log only a
            # recipient COUNT, not the addresses themselves — logging the
            # raw list there would defeat this encryption immediately below
            # it, since audit_log.detail is plaintext by design (compliance
            # staff need to read audit entries directly). Fail CLOSED if
            # ENCRYPTION_KEY isn't configured: store nothing rather than
            # silently persisting plaintext PII just because the unrelated
            # email-send itself already succeeded.
            try:
                record.email_sent_to = encrypt_field(", ".join(email_distribution_list))
            except EncryptionNotConfiguredError:
                record.email_sent_to = None
                _logger.warning(
                    "email_sent_to_not_persisted_encryption_unconfigured",
                    session_id=record.session_id,
                    reason="ENCRYPTION_KEY is not set; refusing to store recipient "
                           "addresses in plaintext. The email itself was still sent.",
                )

            db.add(AuditLogEntry(
                user_id=requested_by or "unknown",
                session_id=record.session_id,
                event_type="EMAIL_SENT",
                # Recipient COUNT only, not the raw addresses — logging the
                # actual email list here in plaintext would defeat the
                # encrypt_field() call immediately above, which exists
                # specifically because these addresses are genuine PII.
                # The encrypted record.email_sent_to is the authoritative,
                # protected place to find who actually received this.
                detail=json.dumps({"recipient_count": len(email_distribution_list), "filename": record.filename}),
                file_sha256=record.file_sha256,
            ))
        except EmailSendError as e:
            result["email_error"] = str(e)
            db.add(AuditLogEntry(
                user_id=requested_by or "unknown",
                session_id=record.session_id,
                event_type="EMAIL_FAILED",
                detail=json.dumps({"recipient_count": len(email_distribution_list), "error": str(e)}),
                file_sha256=record.file_sha256,
            ))

    db.commit()
    db.refresh(record)
    return result
