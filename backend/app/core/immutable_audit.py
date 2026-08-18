"""
Immutable audit logging — Phase 9.

Two independent layers, since they protect against different threats:

1. ORM-level guards (before_update/before_delete event listeners) block
   any attempt to modify or delete an AuditLogEntry through SQLAlchemy —
   the only way the application code itself ever touches this table.
   This stops accidental/buggy application code from ever running
   `db.delete(some_audit_row)` or mutating a field after the fact.

2. Hash chaining (before_insert event listener) makes tampering that
   bypasses the ORM entirely — e.g. someone opens the SQLite file with a
   raw `sqlite3` client, or restores from a hand-edited backup — provable
   after the fact rather than silently accepted. Each row's `chain_hash`
   covers its own fields plus the PREVIOUS row's chain_hash, so altering
   any historical row (or splicing in/deleting rows) breaks the chain from
   that point forward. `verify_audit_chain()` walks the table and reports
   exactly where a break occurs, rather than just a pass/fail bit.

Layer 1 alone would be insufficient (a determined attacker with file
access bypasses the ORM); layer 2 alone would be insufficient (nothing
stops the application itself from happily running an UPDATE if the guard
didn't exist). Together they cover both the "well-behaved app, is the
mechanism trustworthy" and "what if someone touches the file directly"
threat models.

`register_immutability_guards()` must be called once at application
startup (see app/main.py) — it's idempotent (registering the same
listener twice is a no-op) so it's safe to call from tests too.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import event, select

from app.models.audit import AuditLogEntry

_GENESIS_HASH = "genesis"
_registered = False


class ImmutableAuditLogError(Exception):
    """Raised when application code attempts to UPDATE or DELETE an audit log row."""


def _row_payload(entry: AuditLogEntry, previous_hash: str) -> str:
    """Deterministic string representation of everything that should be
    covered by the tamper-evidence hash. Order matters and must never
    change without a migration plan — reordering silently breaks every
    previously-computed chain_hash's verifiability."""
    return "|".join([
        previous_hash,
        str(entry.timestamp),
        str(entry.user_id),
        str(entry.session_id),
        str(entry.event_type),
        str(entry.detail),
        str(entry.file_sha256),
    ])


def _compute_hash(entry: AuditLogEntry, previous_hash: str) -> str:
    return hashlib.sha256(_row_payload(entry, previous_hash).encode("utf-8")).hexdigest()


def _before_insert(mapper, connection, target: AuditLogEntry) -> None:
    if target.timestamp is None:
        target.timestamp = datetime.now(timezone.utc)

    result = connection.execute(
        select(AuditLogEntry.chain_hash)
        .order_by(AuditLogEntry.id.desc())
        .limit(1)
    ).first()
    previous_hash = result[0] if result and result[0] else _GENESIS_HASH
    target.chain_hash = _compute_hash(target, previous_hash)


def _before_update(mapper, connection, target: AuditLogEntry) -> None:
    raise ImmutableAuditLogError(
        f"Audit log entry {target.id} cannot be modified — audit_log is append-only."
    )


def _before_delete(mapper, connection, target: AuditLogEntry) -> None:
    raise ImmutableAuditLogError(
        f"Audit log entry {target.id} cannot be deleted — audit_log is append-only."
    )


def register_immutability_guards() -> None:
    global _registered
    if _registered:
        return
    event.listen(AuditLogEntry, "before_insert", _before_insert)
    event.listen(AuditLogEntry, "before_update", _before_update)
    event.listen(AuditLogEntry, "before_delete", _before_delete)
    _registered = True


def verify_audit_chain(db) -> tuple[bool, list[str]]:
    """
    Walks the entire audit_log table in id order, recomputing each row's
    expected hash from its own fields + the previous row's STORED hash,
    and comparing against what's actually stored. Returns (is_intact,
    list_of_problem_descriptions) — an empty list means the chain is fully
    intact from genesis to the latest row.
    """
    problems: list[str] = []
    previous_hash = _GENESIS_HASH

    rows = db.query(AuditLogEntry).order_by(AuditLogEntry.id.asc()).all()
    for row in rows:
        expected = _compute_hash(row, previous_hash)
        if row.chain_hash != expected:
            problems.append(
                f"Row id={row.id} (event_type={row.event_type}, timestamp={row.timestamp}): "
                f"stored chain_hash does not match the recomputed value — this row or an "
                f"earlier one in the chain has been altered outside the application."
            )
        previous_hash = row.chain_hash or expected

    return (len(problems) == 0, problems)
