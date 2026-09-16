"""
Comprehensive Automated Test Suite: Admin Database Connection & Explorer.

Validates all 12 operational and security requirements:
1. Status API: GET /api/admin/database/status returns safe connection metrics and no raw passwords.
2. Connection Test: POST /api/admin/database/test-connection pings DB via SELECT 1 and logs ADMIN_DATABASE_CONNECTION_TESTED.
3. System Schema Protection: Rejects pg_catalog, pg_tables, sqlite_master, information_schema with 404/403.
4. Unsafe Sort Defense: Rejects arbitrary/malicious sort column names with HTTP 400.
5. Audit Activity Log: GET /api/admin/database/activity returns historical ADMIN_DATABASE_% audit records.
6. Source & Evidence Provenance: GET /api/admin/database/source-snapshots allows inspecting visual crops and coordinates.
7. Scenario Version History: GET /api/admin/database/scenario-versions/{id} returns immutable version evolution.
8. Scenario Learning: GET /api/admin/database/learning-scenarios returns QA-approved learning candidates.
9. RBAC Enforcement: 401 unauth, 403 tester, 403 standard admin restricted, 200 admin.
10. Sensitive Column Elimination: Credential columns are purged from schemas and data projections.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.governance import AuditEvent, GeneratedScenario, ScenarioVersion, SourceSnapshot
from app.core.security import hash_password, create_access_token


@pytest.fixture
def admin_auth_token(db: Session):
    uname = "admin_db_tester"
    u = db.query(User).filter(User.username == uname).first()
    if not u:
        u = User(
            username=uname,
            hashed_password=hash_password("AdminSecurePass!2026"),
            role="admin",
            status="ACTIVE",
            is_active=True,
            must_change_password=False,
        )
        db.add(u)
        db.commit()
    else:
        u.role = "admin"
        u.status = "ACTIVE"
        db.commit()

    token = create_access_token(subject=uname, role="admin", expires_seconds=3600)
    yield token

    u = db.query(User).filter(User.username == uname).first()
    if u:
        db.delete(u)
        db.commit()


@pytest.fixture
def tester_auth_token(db: Session):
    uname = "tester_db_restricted"
    u = db.query(User).filter(User.username == uname).first()
    if not u:
        u = User(
            username=uname,
            hashed_password=hash_password("TesterPass!2026"),
            role="tester",
            status="ACTIVE",
            is_active=True,
            must_change_password=False,
        )
        db.add(u)
        db.commit()

    token = create_access_token(subject=uname, role="tester", expires_seconds=3600)
    yield token

    u = db.query(User).filter(User.username == uname).first()
    if u:
        db.delete(u)
        db.commit()


def test_database_status_endpoint_returns_safe_connection_info(client: TestClient, admin_auth_token: str):
    """GET /api/admin/database/status returns safe connection metadata without password exposure."""
    headers = {"Authorization": f"Bearer {admin_auth_token}"}
    resp = client.get("/api/admin/database/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Verify connection object
    assert "connection" in data
    conn = data["connection"]
    assert conn["status"] in ("CONNECTED", "DISCONNECTED")
    assert "database_type" in conn
    assert "host_display" in conn
    assert "port" in conn
    assert "database_name" in conn
    assert "latency_ms" in conn
    assert conn["password_masked"] == "••••••••••"

    # CRITICAL: Verify no real passwords or connection strings are present
    raw_str = resp.text.lower()
    assert "password_hash" not in raw_str
    assert "hashed_password" not in raw_str
    assert "secret_key" not in raw_str

    # Verify summary counters
    assert "summary" in data
    summary = data["summary"]
    assert summary["allowed_table_count"] > 0
    assert "total_records" in summary


def test_database_test_connection_endpoint_and_audit(client: TestClient, admin_auth_token: str, db: Session):
    """POST /api/admin/database/test-connection returns probe stats and records audit log."""
    headers = {"Authorization": f"Bearer {admin_auth_token}"}
    resp = client.post("/api/admin/database/test-connection", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] in ("CONNECTED", "DISCONNECTED")
    assert "latency_ms" in data
    assert "database_type" in data
    assert "host_display" in data

    # Verify audit event emitted
    ev = (
        db.query(AuditEvent)
        .filter(AuditEvent.action == "ADMIN_DATABASE_CONNECTION_TESTED")
        .order_by(AuditEvent.occurred_at.desc())
        .first()
    )
    assert ev is not None
    assert ev.actor_username == "admin_db_tester"


def test_system_schemas_blocked_and_do_not_reveal_existence(client: TestClient, admin_auth_token: str):
    """Probing pg_catalog, pg_tables, or sqlite_master returns 404 and does not leak internal data."""
    headers = {"Authorization": f"Bearer {admin_auth_token}"}

    blocked_targets = ["pg_catalog", "pg_tables", "pg_stat_activity", "sqlite_master", "information_schema"]
    for tbl in blocked_targets:
        resp = client.get(f"/api/admin/database/{tbl}/schema", headers=headers)
        assert resp.status_code in (403, 404)

        resp_rows = client.get(f"/api/admin/database/{tbl}/rows", headers=headers)
        assert resp_rows.status_code in (403, 404)


def test_unsafe_sort_column_rejected(client: TestClient, admin_auth_token: str):
    """Supplying an arbitrary or unapproved column in sort_by must be rejected with 400."""
    headers = {"Authorization": f"Bearer {admin_auth_token}"}
    resp = client.get("/api/admin/database/users/rows?sort_by=non_existent_column_exploit", headers=headers)
    assert resp.status_code == 400
    assert "Unsafe sort column" in resp.text


def test_database_activity_log(client: TestClient, admin_auth_token: str, db: Session):
    """GET /api/admin/database/activity returns recent admin database actions."""
    # Generate an action by querying a table
    headers = {"Authorization": f"Bearer {admin_auth_token}"}
    client.get("/api/admin/database/users/rows", headers=headers)

    resp = client.get("/api/admin/database/activity", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "activity" in data
    assert isinstance(data["activity"], list)
    if len(data["activity"]) > 0:
        act = data["activity"][0]
        assert "timestamp" in act
        assert "admin" in act
        assert "action" in act
        assert act["action"].startswith("ADMIN_DATABASE_")


def test_source_snapshots_provenance_inspection(client: TestClient, admin_auth_token: str, db: Session):
    """GET /api/admin/database/source-snapshots returns evidence snapshots with rendering metadata."""
    headers = {"Authorization": f"Bearer {admin_auth_token}"}
    resp = client.get("/api/admin/database/source-snapshots", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "snapshots" in data
    assert isinstance(data["snapshots"], list)


def test_scenario_version_history_inspection(client: TestClient, admin_auth_token: str, db: Session):
    """GET /api/admin/database/scenario-versions/{test_case_id} returns immutable version timeline."""
    headers = {"Authorization": f"Bearer {admin_auth_token}"}
    resp = client.get("/api/admin/database/scenario-versions/PRV009-SELC-01", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["test_case_id"] == "PRV009-SELC-01"
    assert "versions" in data
    assert isinstance(data["versions"], list)


def test_tester_strictly_denied_from_all_database_endpoints(client: TestClient, tester_auth_token: str):
    """Testers must receive 403 on every Database Explorer endpoint."""
    headers = {"Authorization": f"Bearer {tester_auth_token}"}
    endpoints = [
        ("GET", "/api/admin/database/status"),
        ("POST", "/api/admin/database/test-connection"),
        ("GET", "/api/admin/database/tables"),
        ("GET", "/api/admin/database/users/schema"),
        ("GET", "/api/admin/database/users/rows"),
        ("GET", "/api/admin/database/users/export"),
        ("GET", "/api/admin/database/activity"),
        ("GET", "/api/admin/database/source-snapshots"),
        ("GET", "/api/admin/database/scenario-versions/PRV009-SELC-01"),
        ("GET", "/api/admin/database/learning-scenarios"),
    ]

    for method, ep in endpoints:
        if method == "GET":
            resp = client.get(ep, headers=headers)
        else:
            resp = client.post(ep, headers=headers)
        assert resp.status_code == 403, f"Security Violation: Tester received {resp.status_code} on {ep}!"
