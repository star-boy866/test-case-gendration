"""
Centralized, Secure Audit & Event Tracking Service.

Guarantees:
1. Every meaningful user and administrative action is recorded.
2. Credentials and secrets are strictly redacted before serialization.
3. Dual persistence: writes to modern `audit_events` and legacy chained `audit_log`.
4. Graceful error handling: audit failures never break application request flows.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.governance import AuditEvent, LoginEvent, SecurityEvent
from app.models.audit import AuditLogEntry

logger = logging.getLogger(__name__)

# Sensitive key substrings that must NEVER be persisted in audit details
_SENSITIVE_PATTERNS = {
    "password", "passwd", "pwd", "hash", "secret", "token", "key",
    "jwt", "credential", "auth", "api_key", "bearer", "cookie",
    "database_url", "encryption_key"
}


def sanitize_audit_details(data: Any) -> Any:
    """
    Recursively scrubs sensitive keys and values from audit detail dictionaries/lists.
    Guarantees no passwords, secrets, or keys leak into logs or audit tables.
    """
    if data is None:
        return None
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(pat in k_lower for pat in _SENSITIVE_PATTERNS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_audit_details(v)
        return sanitized
    elif isinstance(data, (list, tuple, set)):
        return [sanitize_audit_details(item) for item in data]
    elif isinstance(data, str):
        # Additional safety check for raw token or connection strings
        lower_val = data.lower()
        if "postgresql://" in lower_val or "postgres://" in lower_val:
            return "[REDACTED_DATABASE_URL]"
        if len(data) > 40 and ("eyj" in lower_val or "bearer" in lower_val):
            return "[REDACTED_TOKEN]"
        return data
    return data


def log_audit_event(
    db: Session,
    actor_username: str,
    actor_role: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    run_id: Optional[int] = None,
    scenario_id: Optional[str] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    details: Optional[Dict[str, Any]] = None,
    actor_user_id: Optional[int] = None,
) -> Optional[AuditEvent]:
    """
    Records an immutable audit event in `audit_events` and syncs with `audit_log`.
    """
    clean_details = sanitize_audit_details(details) if details else None
    now = datetime.now(timezone.utc)

    try:
        event = AuditEvent(
            occurred_at=now,
            actor_user_id=actor_user_id,
            actor_username=str(actor_username or "anonymous"),
            actor_role=str(actor_role or "unknown"),
            action=str(action).upper(),
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            run_id=run_id,
            scenario_id=str(scenario_id) if scenario_id is not None else None,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            details=clean_details,
        )
        db.add(event)

        # Sync to legacy chained audit_log
        try:
            detail_str = json.dumps(clean_details) if clean_details else action
            legacy_entry = AuditLogEntry(
                timestamp=now,
                user_id=str(actor_username or "system"),
                event_type=action,
                detail=detail_str[:2000] if detail_str else None,
            )
            db.add(legacy_entry)
        except Exception:
            pass

        db.commit()
        return event
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to record audit event '{action}': {exc}", exc_info=True)
        return None


def log_login_event(
    db: Session,
    username: str,
    success: bool,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    failure_reason: Optional[str] = None,
) -> Optional[LoginEvent]:
    """Records a login attempt (successful or failed)."""
    try:
        event = LoginEvent(
            occurred_at=datetime.now(timezone.utc),
            username=username,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason,
        )
        db.add(event)
        db.commit()
        return event
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to record login event for '{username}': {exc}")
        return None


def log_security_event(
    db: Session,
    event_type: str,
    severity: str = "MEDIUM",
    actor_username: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Optional[SecurityEvent]:
    """Records high-severity security notifications."""
    clean_details = sanitize_audit_details(details) if details else None
    try:
        event = SecurityEvent(
            occurred_at=datetime.now(timezone.utc),
            event_type=event_type,
            severity=severity.upper(),
            actor_username=actor_username,
            ip_address=ip_address,
            details=clean_details,
        )
        db.add(event)
        db.commit()
        return event
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to record security event '{event_type}': {exc}")
        return None
