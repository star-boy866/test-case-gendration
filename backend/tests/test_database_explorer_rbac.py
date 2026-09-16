"""
Test Suite: Database Explorer RBAC and Authorization Boundaries.

Verifies:
1. Tester -> Database Explorer (/api/admin/database/tables) = 403 Forbidden.
2. Tester -> Table row browser (/api/admin/database/users/rows) = 403 Forbidden.
3. Standard Admin -> restricted from browsing database without explicit permission = 403 Forbidden.
4. Admin -> Database Explorer (/api/admin/database/tables) = 200 OK.
5. Admin -> Table rows (/api/admin/database/cognos_test_cases/rows) = 200 OK.
6. Unauthenticated -> 401 Unauthorized.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import hash_password, create_access_token


@pytest.fixture
def rbac_users(db: Session):
    """Sets up distinct accounts for Tester, Standard Admin, and Admin in the test DB."""
    accounts = {
        "db_test_tester": {"role": "tester"},
        "db_test_admin": {"role": "admin"},
        "db_test_std_admin": {"role": "standard_admin"},
    }
    tokens = {}

    for uname, info in accounts.items():
        u = db.query(User).filter(User.username == uname).first()
        if not u:
            u = User(
                username=uname,
                hashed_password=hash_password("Pass#Secure2026!"),
                role=info["role"],
                status="ACTIVE",
                is_active=True,
                must_change_password=False,
            )
            db.add(u)
            db.commit()
            db.refresh(u)
        else:
            u.role = info["role"]
            u.status = "ACTIVE"
            u.is_active = True
            u.must_change_password = False
            db.commit()

        tokens[uname] = create_access_token(
            subject=uname,
            role=info["role"],
            expires_seconds=3600,
        )

    yield tokens

    # Cleanup
    for uname in accounts:
        u = db.query(User).filter(User.username == uname).first()
        if u:
            db.delete(u)
    db.commit()


def test_unauthenticated_database_explorer_access(client: TestClient):
    """Unauthenticated requests must be rejected with 401 Unauthorized."""
    resp = client.get("/api/admin/database/tables")
    assert resp.status_code == 401


def test_tester_forbidden_from_database_explorer(client: TestClient, rbac_users: dict):
    """Testers must NEVER be allowed access to Database Explorer (403 Forbidden)."""
    token = rbac_users["db_test_tester"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/admin/database/tables", headers=headers)
    assert resp.status_code == 403
    assert "Testers cannot access Database Explorer" in resp.text

    # Attempting to fetch rows
    resp_rows = client.get("/api/admin/database/users/rows", headers=headers)
    assert resp_rows.status_code == 403


def test_standard_admin_restricted_without_explicit_governance_permission(client: TestClient, rbac_users: dict):
    """
    Standard Admin is restricted from arbitrary database browsing
    unless explicitly granted separate read-only governance permission (403 Forbidden).
    """
    token = rbac_users["db_test_std_admin"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/admin/database/tables", headers=headers)
    assert resp.status_code == 403
    assert "Standard Admin requires explicit 'database:read'" in resp.text


def test_admin_allowed_access_to_database_explorer(client: TestClient, rbac_users: dict):
    """Admin role has full read-only access to Database Explorer (200 OK)."""
    token = rbac_users["db_test_admin"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/admin/database/tables", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "tables" in data
    assert data["access_mode"] == "READ_ONLY"

    table_names = [t["table_name"] for t in data["tables"]]
    assert "users" in table_names
    assert "cognos_test_cases" in table_names
    assert "audit_events" in table_names


def test_admin_can_read_allowed_table_rows(client: TestClient, rbac_users: dict):
    """Admin can query paginated rows of an allowed table."""
    token = rbac_users["db_test_admin"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/admin/database/cognos_test_cases/rows", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["table"] == "cognos_test_cases"
    assert "rows" in data
    assert "columns" in data
    assert isinstance(data["rows"], list)
