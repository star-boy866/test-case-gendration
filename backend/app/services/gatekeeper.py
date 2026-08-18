"""
Gatekeeper service — Phase 2.

Implements the "strict blocking step" from the Master System Prompt: before
the generation pipeline (Phase 4/5) is allowed to run, a human must
explicitly confirm CR ID, CR Description, and Report ID against the scope
that was actually extracted into the Knowledge Base during ingestion.

Two halves:
1. `get_scope_summary` / `confirm_scope` — power the Gatekeeper UI.
2. `require_gatekeeper_confirmation` — the actual gate. Any endpoint that
   would trigger generation MUST call this first. It is intentionally
   strict: no confirmed Session for the report_id means no generation,
   full stop.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from app.models.audit import Session as SessionModel, AuditLogEntry
from app.services.knowledge_base import get_knowledge_base_summary


class GatekeeperError(Exception):
    """Raised when scope cannot be confirmed (e.g. insufficient metadata)."""


class GatekeeperBlockedError(Exception):
    """
    Raised when a downstream step (generation) is attempted without a
    confirmed Gatekeeper session. Callers (API layer) should translate this
    into an HTTP 403.
    """


def _latest_session(db: DBSession, report_id: str) -> SessionModel | None:
    return (
        db.query(SessionModel)
        .filter(SessionModel.report_id == report_id)
        .order_by(SessionModel.id.desc())
        .first()
    )


def get_scope_summary(db: DBSession, report_id: str) -> dict:
    """
    Everything the Gatekeeper UI needs to render its confirmation card:
    what was extracted, what CR ID/description are on file (if any), and
    whether this report_id is currently confirmed.
    """
    kb = get_knowledge_base_summary(db, report_id)
    latest_session = _latest_session(db, report_id)

    # CR ID: prefer whatever was confirmed previously; otherwise fall back
    # to the cr_id captured at ingestion time (from the most recent doc
    # that had one).
    cr_id_from_docs = None
    if kb["source_documents"]:
        from app.models.knowledge_base import SourceDocument
        doc = (
            db.query(SourceDocument)
            .filter(SourceDocument.report_id == report_id, SourceDocument.cr_id.isnot(None))
            .order_by(SourceDocument.id.desc())
            .first()
        )
        cr_id_from_docs = doc.cr_id if doc else None

    counts = {
        "tables": len(kb["tables"]),
        "columns": len(kb["columns"]),
        "joins": len(kb["joins"]),
        "valid_values": len(kb["valid_values"]),
        "business_rules": len(kb["business_rules"]),
        "unstructured_notes": len(kb["unstructured_notes_pending_review"]),
    }
    has_scope = any(v > 0 for k, v in counts.items() if k != "unstructured_notes")

    return {
        "report_id": report_id,
        "session_id": latest_session.id if latest_session else None,
        "cr_id": (latest_session.cr_id if latest_session else None) or cr_id_from_docs,
        "cr_description": latest_session.cr_description if latest_session else None,
        "counts": counts,
        "source_documents": kb["source_documents"],
        "is_confirmed": bool(latest_session and latest_session.status == "gatekeeper_confirmed"),
        "confirmed_at": latest_session.confirmed_at.isoformat() if latest_session and latest_session.confirmed_at else None,
        "confirmed_by": latest_session.confirmed_by if latest_session else None,
        "can_confirm": has_scope,
    }


def confirm_scope(
    db: DBSession,
    *,
    report_id: str,
    cr_id: str,
    cr_description: str,
    confirmed_by: str,
) -> dict:
    """
    Records human confirmation of scope. Raises GatekeeperError if the
    Knowledge Base for this report_id has no structured content — you
    cannot confirm scope that doesn't exist.
    """
    if not report_id or not report_id.strip():
        raise GatekeeperError("report_id is required.")
    if not cr_id or not cr_id.strip():
        raise GatekeeperError("cr_id is required for Gatekeeper confirmation.")
    if not cr_description or not cr_description.strip():
        raise GatekeeperError("cr_description is required for Gatekeeper confirmation.")

    kb = get_knowledge_base_summary(db, report_id)
    has_scope = bool(kb["tables"] or kb["columns"] or kb["joins"] or kb["valid_values"] or kb["business_rules"])
    if not has_scope:
        raise GatekeeperError(
            "Insufficient metadata available. Additional documentation is "
            "required before generation can continue."
        )

    now = datetime.now(timezone.utc)
    session = SessionModel(
        user_id=confirmed_by,
        cr_id=cr_id.strip(),
        cr_description=cr_description.strip(),
        report_id=report_id,
        status="gatekeeper_confirmed",
        confirmed_at=now,
        confirmed_by=confirmed_by,
    )
    db.add(session)

    db.add(AuditLogEntry(
        user_id=confirmed_by,
        event_type="CONFIRM_GATEKEEPER",
        detail=(
            f'{{"report_id": "{report_id}", "cr_id": "{cr_id}", '
            f'"cr_description_length": {len(cr_description)}}}'
        ),
    ))

    db.commit()
    db.refresh(session)

    return {
        "session_id": session.id,
        "report_id": report_id,
        "cr_id": session.cr_id,
        "cr_description": session.cr_description,
        "confirmed_at": session.confirmed_at.isoformat(),
        "confirmed_by": session.confirmed_by,
    }


def require_gatekeeper_confirmation(db: DBSession, report_id: str) -> SessionModel:
    """
    THE GATE. Call this at the top of any endpoint that triggers generation
    (Phase 4/5). Raises GatekeeperBlockedError if no confirmed session
    exists for report_id, or if the underlying Knowledge Base changed since
    confirmation (re-upload invalidation — see knowledge_base.py) and the
    session was consequently downgraded.
    """
    session = _latest_session(db, report_id)
    if session is None or session.status != "gatekeeper_confirmed":
        raise GatekeeperBlockedError(
            f"Generation blocked: report_id='{report_id}' has not completed "
            f"Gatekeeper confirmation. Confirm CR ID, CR Description, and "
            f"Report ID via /api/gatekeeper/confirm before requesting "
            f"generation."
        )
    return session
