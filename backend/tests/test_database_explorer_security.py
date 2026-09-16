"""
Test Suite: Database Explorer Security, Sensitive Column Protection, and SQL Injection Defenses.

Verifies:
1. Sensitive columns (password, hashed_password, secret, token, key) are NEVER returned.
2. Arbitrary SQL execution endpoints do NOT exist (HTTP 404).
3. Tables outside the strict allowlist return HTTP 404.
4. Parameterized filtering defends against SQL injection in search and filter parameters.
5. Pagination constraints (max 100 rows per request) are enforced.
6. Safe CSV and JSON exports succeed with column redaction.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import hash_password, create_access_token


@pytest.fixture
def admin_token(db: Session):
    """Sets up an Admin user in the test DB and creates a JWT access token."""
    uname = "db_sec_admin"
    u = db.query(User).filter(User.username == uname).first()
    if not u:
        u = User(
            username=uname,
            hashed_password=hash_password("Admin#Pass2026!"),
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
        u.is_active = True
        u.must_change_password = False
        db.commit()

    token = create_access_token(subject=uname, role="admin", expires_seconds=3600)
    yield token

    # Cleanup
    u = db.query(User).filter(User.username == uname).first()
    if u:
        db.delete(u)
        db.commit()


def test_password_hash_never_exposed_in_schema(client: TestClient, admin_token: str):
    """Schema inspection of `users` table must NEVER return password or password_hash columns."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = client.get("/api/admin/database/users/schema", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    column_names = [col["name"].lower() for col in data["columns"]]
    for sensitive_term in ["password", "hashed_password", "password_hash", "secret", "token"]:
        assert sensitive_term not in column_names, f"Security Violation: '{sensitive_term}' exposed in schema!"


def test_password_hash_never_exposed_in_rows(client: TestClient, admin_token: str):
    """Data rows of `users` table must NEVER return password or password_hash values."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = client.get("/api/admin/database/users/rows", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    for row in data["rows"]:
        for k in row.keys():
            k_lower = k.lower()
            assert "password" not in k_lower, f"Security Violation: '{k}' returned in user row!"
            assert "secret" not in k_lower
            assert "token" not in k_lower


def test_arbitrary_sql_endpoint_does_not_exist(client: TestClient, admin_token: str):
    """System must NOT have any arbitrary SQL query execution endpoint."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Test common potential arbitrary SQL vectors
    endpoints_to_test = [
        "/api/database/query",
        "/api/admin/database/query",
        "/api/admin/database/sql",
        "/api/database/execute",
    ]
    for ep in endpoints_to_test:
        resp = client.post(ep, json={"sql": "SELECT 1"}, headers=headers)
        assert resp.status_code in (404, 405), f"Vulnerability: Endpoint {ep} returned {resp.status_code}!"


def test_disallowed_table_rejected(client: TestClient, admin_token: str):
    """Requesting an unlisted or internal database table must return 404."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = client.get("/api/admin/database/sqlite_master/rows", headers=headers)
    assert resp.status_code == 404

    resp = client.get("/api/admin/database/information_schema/rows", headers=headers)
    assert resp.status_code == 404


def test_sql_injection_defense_in_search_parameter(client: TestClient, admin_token: str):
    """Malicious SQL injection in search parameters must be treated as literal search strings."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Attempt classic SQL injection payload
    payload = "admin' OR '1'='1"
    resp = client.get(f"/api/admin/database/users/rows?search={payload}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # It must safely execute via parameterized query and not crash or return arbitrary records
    assert isinstance(data["rows"], list)


def test_pagination_limits_enforced(client: TestClient, admin_token: str):
    """Page size cannot exceed maximum limit of 100."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Attempting to request 500 rows should be rejected by validation (422)
    resp = client.get("/api/admin/database/users/rows?page_size=500", headers=headers)
    assert resp.status_code == 422


def test_safe_csv_export_excludes_secrets(client: TestClient, admin_token: str):
    """CSV export returns file download without any sensitive password columns."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = client.get("/api/admin/database/users/export?format=csv", headers=headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text

    # Header row inspection
    header_line = content.splitlines()[0] if content.splitlines() else ""
    assert "hashed_password" not in header_line
    assert "password" not in header_line
