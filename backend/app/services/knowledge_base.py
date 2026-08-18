"""
Knowledge Base service — persists ParsedDocument results and manages the
cache-busting rule from the Master System Prompt:

  "Automatically invalidate or clear cached scenarios for a specific
   Report/CR ID if its underlying source file hash or LDM configuration
   changes."

Phase 1 implements the *detection and KB row invalidation* half of this.
Phase 3 (FAISS semantic cache) will call `was_invalidated` to also drop the
corresponding vector cache entries.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.audit import AuditLogEntry
from app.models.audit import Session as SessionModel
from app.models.knowledge_base import (
    SourceDocument,
    KBTable,
    KBColumn,
    KBJoin,
    KBValidValue,
    KBBusinessRule,
    UnstructuredNote,
)
from app.services.document_parser import ParsedDocument

INSUFFICIENT_METADATA_MESSAGE = (
    "Insufficient metadata available. Additional documentation is required "
    "before generation can continue."
)


def compute_file_sha256(path: str | Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _previous_hash_for_report(db: Session, report_id: str) -> str | None:
    last = (
        db.query(SourceDocument)
        .filter(SourceDocument.report_id == report_id)
        .order_by(SourceDocument.id.desc())
        .first()
    )
    return last.file_sha256 if last else None


def get_current_file_hash(db: Session, report_id: str) -> str | None:
    """
    Public wrapper for the most-recently-ingested source file's hash for a
    report_id. Used by generation.py to scope semantic cache lookups to
    (report_id, source_file_hash) — see semantic_cache.py.
    """
    return _previous_hash_for_report(db, report_id)


def invalidate_existing_kb(db: Session, report_id: str) -> int:
    """
    Delete all previously stored KB rows for a report_id (cache-busting on
    file change). Returns the number of SourceDocument rows removed
    (cascades to tables/columns/joins/valid_values/business_rules/notes).

    Also downgrades any Gatekeeper-confirmed session for this report_id
    back to "ingestion" status — a prior human confirmation of scope is no
    longer valid once the underlying source document has changed. This is
    what makes the Phase 2 blocking gate trustworthy across re-uploads.
    """
    docs = db.query(SourceDocument).filter(SourceDocument.report_id == report_id).all()
    count = len(docs)
    for doc in docs:
        db.delete(doc)

    confirmed_sessions = (
        db.query(SessionModel)
        .filter(SessionModel.report_id == report_id, SessionModel.status == "gatekeeper_confirmed")
        .all()
    )
    for s in confirmed_sessions:
        s.status = "ingestion"
        s.confirmed_at = None
        s.confirmed_by = None
        db.add(AuditLogEntry(
            user_id=s.user_id,
            session_id=s.id,
            event_type="GATEKEEPER_INVALIDATED_ON_REUPLOAD",
            detail=f'{{"report_id": "{report_id}", "reason": "source file changed"}}',
        ))

    db.commit()
    return count


def persist_parsed_document(
    db: Session,
    *,
    report_id: str,
    cr_id: str | None,
    filename: str,
    file_path: str | Path,
    file_type: str,
    uploaded_by: str | None,
    parsed: ParsedDocument,
) -> dict:
    """
    Persist a ParsedDocument's rows into the Knowledge Base, scoped to
    report_id. Applies the cache-busting rule: if this report_id already has
    KB data from a DIFFERENT source file hash, the old data is invalidated
    first so stale metadata never silently coexists with new metadata.

    Returns a summary dict suitable for the API response and audit log.
    """
    file_hash = compute_file_sha256(file_path)
    previous_hash = _previous_hash_for_report(db, report_id)
    was_invalidated = False

    if previous_hash is not None and previous_hash != file_hash:
        invalidate_existing_kb(db, report_id)
        was_invalidated = True

    parse_status = "parsed" if parsed.has_structured_content else "insufficient_metadata"

    source_doc = SourceDocument(
        report_id=report_id,
        cr_id=cr_id,
        filename=filename,
        file_sha256=file_hash,
        file_type=file_type,
        uploaded_by=uploaded_by,
        parse_status=parse_status,
        parse_summary=json.dumps({
            "tables": len(parsed.tables),
            "columns": len(parsed.columns),
            "joins": len(parsed.joins),
            "valid_values": len(parsed.valid_values),
            "business_rules": len(parsed.business_rules),
            "unstructured_notes": len(parsed.unstructured_notes),
            "sheets_parsed": parsed.sheets_parsed,
            "sheets_skipped": parsed.sheets_skipped,
            "warnings": parsed.warnings,
        }),
    )
    db.add(source_doc)
    db.flush()  # get source_doc.id without committing yet

    for t in parsed.tables:
        db.add(KBTable(report_id=report_id, source_document_id=source_doc.id, **t))
    for c in parsed.columns:
        db.add(KBColumn(report_id=report_id, source_document_id=source_doc.id, **c))
    for j in parsed.joins:
        db.add(KBJoin(report_id=report_id, source_document_id=source_doc.id, **j))
    for v in parsed.valid_values:
        db.add(KBValidValue(report_id=report_id, source_document_id=source_doc.id, **v))
    for r in parsed.business_rules:
        db.add(KBBusinessRule(report_id=report_id, source_document_id=source_doc.id, **r))
    for n in parsed.unstructured_notes:
        db.add(UnstructuredNote(report_id=report_id, source_document_id=source_doc.id, **n))

    db.add(AuditLogEntry(
        user_id=uploaded_by or "unknown",
        event_type="UPLOAD",
        detail=json.dumps({
            "report_id": report_id,
            "cr_id": cr_id,
            "filename": filename,
            "parse_status": parse_status,
            "kb_invalidated_prior_version": was_invalidated,
        }),
        file_sha256=file_hash,
    ))

    db.commit()
    db.refresh(source_doc)

    return {
        "source_document_id": source_doc.id,
        "file_sha256": file_hash,
        "parse_status": parse_status,
        "kb_invalidated_prior_version": was_invalidated,
        "counts": {
            "tables": len(parsed.tables),
            "columns": len(parsed.columns),
            "joins": len(parsed.joins),
            "valid_values": len(parsed.valid_values),
            "business_rules": len(parsed.business_rules),
            "unstructured_notes": len(parsed.unstructured_notes),
        },
        "warnings": parsed.warnings,
        "message": None if parsed.has_structured_content else INSUFFICIENT_METADATA_MESSAGE,
    }


def get_knowledge_base_summary(db: Session, report_id: str) -> dict:
    """Full listing of everything currently in the KB for a report_id."""
    tables = db.query(KBTable).filter(KBTable.report_id == report_id).all()
    columns = db.query(KBColumn).filter(KBColumn.report_id == report_id).all()
    joins = db.query(KBJoin).filter(KBJoin.report_id == report_id).all()
    valid_values = db.query(KBValidValue).filter(KBValidValue.report_id == report_id).all()
    business_rules = db.query(KBBusinessRule).filter(KBBusinessRule.report_id == report_id).all()
    notes = db.query(UnstructuredNote).filter(UnstructuredNote.report_id == report_id).all()
    documents = db.query(SourceDocument).filter(SourceDocument.report_id == report_id).all()

    def _row(obj, fields):
        return {f: getattr(obj, f) for f in fields}

    return {
        "report_id": report_id,
        "source_documents": [
            _row(d, ["id", "filename", "file_sha256", "file_type", "parse_status", "uploaded_at"])
            for d in documents
        ],
        "tables": [_row(t, ["table_name", "description"]) for t in tables],
        "columns": [
            _row(c, ["table_name", "column_name", "data_type", "key_type", "description"])
            for c in columns
        ],
        "joins": [
            _row(j, ["from_table", "from_column", "to_table", "to_column", "join_type"])
            for j in joins
        ],
        "valid_values": [
            _row(v, ["table_name", "column_name", "valid_value", "meaning"])
            for v in valid_values
        ],
        "business_rules": [
            _row(r, ["rule_text", "related_table", "related_column"])
            for r in business_rules
        ],
        "unstructured_notes_pending_review": [
            _row(n, ["content", "reason"]) for n in notes
        ],
    }
