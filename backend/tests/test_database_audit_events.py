"""
Test Suite: Audit Trail Completeness, Event Logging, and Secret Scrubbing.

Verifies:
1. Every Database Explorer row access emits an `ADMIN_DATABASE_VIEWED` event.
2. Every Database Explorer export emits an `ADMIN_DATABASE_EXPORT` event.
3. Audit events never contain passwords, API keys, tokens, or raw secrets.
4. sanitize_audit_details redacts sensitive keys recursively.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.governance import AuditEvent
from app.core.security import hash_password, create_access_token
from app.services.audit_service import sanitize_audit_details


@pytest.fixture
def admin_identity(db: Session):
    """Sets up an Admin user in the test DB for audit trail testing."""
    uname = "db_audit_admin"
    u = db.query(User).filter(User.username == uname).first()
    if not u:
        u = User(
            username=uname,
            hashed_password=hash_password("Audit#Admin2026!"),
            role="admin",
            status="ACTIVE",
            is_active=True,
            must_change_password=False,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
    else:
        u.role = "admin"
        u.status = "ACTIVE"
        u.is_active = True
        u.must_change_password = False
        db.commit()

    token = create_access_token(subject=uname, role="admin", expires_seconds=3600)
    yield {"user": u, "token": token}

    # Cleanup
    db.query(AuditEvent).filter(AuditEvent.actor_username == uname).delete(synchronize_session=False)
    u_obj = db.query(User).filter(User.username == uname).first()
    if u_obj:
        db.delete(u_obj)
        db.commit()


def test_database_explorer_access_generates_audit_event(client: TestClient, admin_identity: dict, db: Session):
    """Querying table rows must record an ADMIN_DATABASE_VIEWED event in audit_events."""
    token = admin_identity["token"]
    username = admin_identity["user"].username
    headers = {"Authorization": f"Bearer {token}"}

    # Make request to view rows
    resp = client.get("/api/admin/database/cognos_test_cases/rows?page=1&page_size=10", headers=headers)
    assert resp.status_code == 200

    # Verify audit event in test DB
    ev = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.actor_username == username,
            AuditEvent.action.in_(["ADMIN_DATABASE_VIEWED", "ADMIN_DATABASE_TABLE_VIEWED"]),
            AuditEvent.resource_id == "cognos_test_cases"
        )
        .order_by(AuditEvent.occurred_at.desc())
        .first()
    )
    assert ev is not None, "Audit event ADMIN_DATABASE_VIEWED was not recorded!"
    assert ev.resource_type == "DATABASE_TABLE"
    assert ev.success is True
    assert ev.details["table"] == "cognos_test_cases"
    assert ev.details["page"] == 1


def test_database_explorer_export_generates_audit_event(client: TestClient, admin_identity: dict, db: Session):
    """Exporting table data must record an ADMIN_DATABASE_EXPORT event in audit_events."""
    token = admin_identity["token"]
    username = admin_identity["user"].username
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/admin/database/users/export?format=csv", headers=headers)
    assert resp.status_code == 200

    ev = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.actor_username == username,
            AuditEvent.action == "ADMIN_DATABASE_EXPORT",
            AuditEvent.resource_id == "users"
        )
        .order_by(AuditEvent.occurred_at.desc())
        .first()
    )
    assert ev is not None, "Audit event ADMIN_DATABASE_EXPORT was not recorded!"
    assert ev.resource_type == "DATABASE_EXPORT"
    assert ev.details["format"] == "csv"


def test_audit_detail_sanitizer_redacts_sensitive_keys():
    """sanitize_audit_details must recursively scrub any passwords, tokens, or keys."""
    raw_payload = {
        "user": "analyst",
        "action": "CONFIG_UPDATE",
        "nested": {
            "password": "SuperSecretPassword123!",
            "hashed_password": "argon2id$v=19$m=65536,t=3,p=4$...",
            "api_key": "sk-proj-xyz123456",
            "safe_attribute": "valid_value",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        },
        "connection_url": "postgresql://postgres:MyPass123@aws-0-ap-south-1.pooler.supabase.com:6543/postgres",
    }

    cleaned = sanitize_audit_details(raw_payload)

    assert cleaned["nested"]["password"] == "[REDACTED]"
    assert cleaned["nested"]["hashed_password"] == "[REDACTED]"
    assert cleaned["nested"]["api_key"] == "[REDACTED]"
    assert cleaned["nested"]["token"] == "[REDACTED]"
    assert cleaned["nested"]["safe_attribute"] == "valid_value"
    assert "[REDACTED_DATABASE_URL]" in str(cleaned["connection_url"])
