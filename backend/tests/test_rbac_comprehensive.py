"""
Comprehensive Test Suite for RBAC, Bootstrap Admin, and Security Modules.

Covers:
- Standard Admin bootstrap ('obuli') and forced first-login password change
- Access request workflow (Pending -> Approved / Rejected)
- Role hierarchy & boundaries (Admin cannot approve Admin; only Standard Admin can; no self-approval)
- Standard Admin account protection from suspension, revocation, or downgrade
- Account lockout after 5 failed login attempts
- Server-side session invalidation and "Log out from all devices"
- RFC 6238 TOTP and backup recovery code verification
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import cast
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_db, SessionLocal
from app.models.user import User
from app.models.rbac import AccessRequest, UserSession, MfaConfiguration
from app.core.config import settings
from app.core.security import hash_password, verify_password, validate_password_strength
from app.core.totp import (
    generate_totp_secret,
    get_totp_code,
    verify_totp_code,
    generate_backup_codes,
    verify_backup_code,
)
from app.services.user_service import (
    bootstrap_standard_admin,
    handle_failed_login,
    is_account_locked,
    reset_failed_logins,
    change_user_password,
    update_user_status,
    update_user_role,
    UserError,
)
from app.services.approval_service import (
    submit_access_request,
    get_pending_requests,
    approve_access_request,
    reject_access_request,
    ApprovalError,
)
from app.services.session_service import (
    create_session,
    revoke_session,
    revoke_all_user_sessions,
    list_user_sessions,
)
from app.core.rbac import CurrentUser


# ─── 1. BOOTSTRAP STANDARD ADMIN TESTS ───────────────────────────────────────

def _reset_obuli(db: Session):
    admin = db.query(User).filter(User.username == "obuli").first()
    if admin:
        setattr(admin, "hashed_password", hash_password(settings.INITIAL_ADMIN_TEMP_PASSWORD))
        setattr(admin, "must_change_password", True)
        setattr(admin, "mfa_enabled", False)
        setattr(admin, "failed_login_attempts", 0)
        setattr(admin, "locked_until", None)
        db.commit()


def test_bootstrap_standard_admin(db: Session):
    """Ensures Standard Admin 'obuli' is created with correct role and forced password change."""
    _reset_obuli(db)
    admin = bootstrap_standard_admin(db)
    assert admin is not None
    assert admin.username == "obuli"
    assert admin.role == "standard_admin"
    assert admin.status == "ACTIVE"
    assert admin.is_active is True
    assert admin.must_change_password is True
    # Password must verify against the configured temp password
    assert verify_password(settings.INITIAL_ADMIN_TEMP_PASSWORD, admin.hashed_password) is True


def test_first_login_forces_password_change(client: TestClient):
    """Logging in with temporary password must flag MUST_CHANGE_PASSWORD and prevent protected access."""
    res = client.post(
        "/api/auth/login",
        json={"username": "obuli", "password": settings.INITIAL_ADMIN_TEMP_PASSWORD},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "MUST_CHANGE_PASSWORD"
    assert "temp_token" in data

    # Attempting to access protected endpoint with temp token should be blocked
    protected_res = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {data['temp_token']}"},
    )
    assert protected_res.status_code == 403
    assert "Password change required" in protected_res.json()["detail"]


def test_password_strength_and_successful_change(db: Session, client: TestClient):
    """Tests password policy validation and successful password change clearing must_change_password."""
    # Weak password checks
    ok, err = validate_password_strength("weak")
    assert ok is False
    assert "12 characters" in err

    ok, err = validate_password_strength("alllowercaseletters123!")
    assert ok is False
    assert "uppercase" in err

    ok, err = validate_password_strength("ALLUPPERCASE123!@#")
    assert ok is False
    assert "lowercase" in err

    ok, err = validate_password_strength("NoSpecialCharacter123")
    assert ok is False
    assert "special character" in err

    ok, err = validate_password_strength("Strong#Pass2026!Secure", "obuli")
    assert ok is True

    # Get temp token for obuli
    login_res = client.post(
        "/api/auth/login",
        json={"username": "obuli", "password": settings.INITIAL_ADMIN_TEMP_PASSWORD},
    )
    temp_token = login_res.json()["temp_token"]

    # Change password
    change_res = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {temp_token}"},
        json={
            "current_password": settings.INITIAL_ADMIN_TEMP_PASSWORD,
            "new_password": "New#StrongPass2026!Secure",
        },
    )
    assert change_res.status_code == 200
    assert change_res.json()["status"] == "SUCCESS"

    # Verify must_change_password is now False
    user = db.query(User).filter(User.username == "obuli").first()
    assert user is not None
    assert user.must_change_password is False

    # Reset password back so other tests continue seamlessly
    setattr(user, "hashed_password", hash_password(settings.INITIAL_ADMIN_TEMP_PASSWORD))
    setattr(user, "must_change_password", True)
    db.commit()


def cleanup_user(db: Session, username: str):
    """Safely cleans up a test user and all related child records."""
    user = db.query(User).filter(User.username == username).first()
    if user:
        from app.models.rbac import ApprovalHistory
        db.query(UserSession).filter(UserSession.user_id == user.id).delete()
        req_ids = [r.id for r in db.query(AccessRequest).filter(AccessRequest.user_id == user.id).all()]
        if req_ids:
            db.query(ApprovalHistory).filter(ApprovalHistory.request_id.in_(req_ids)).delete(synchronize_session=False)
            db.query(AccessRequest).filter(AccessRequest.id.in_(req_ids)).delete(synchronize_session=False)
        db.query(MfaConfiguration).filter(MfaConfiguration.user_id == user.id).delete()
        db.delete(user)
        db.commit()


# ─── 2. ACCESS REQUEST & APPROVAL WORKFLOW TESTS ─────────────────────────────

def test_access_request_submission_and_pending_gate(client: TestClient, db: Session):
    """New registrations start in PENDING status and are blocked from protected endpoints."""
    test_user = "test_candidate_1"
    cleanup_user(db, test_user)

    reg_res = client.post(
        "/api/auth/access-request",
        json={
            "username": test_user,
            "password": "Valid#Password2026!",
            "requested_role": "tester",
            "reason": "Need access to run Cognos report validation for sprint 42.",
        },
    )
    assert reg_res.status_code == 200
    data = reg_res.json()
    assert data["status"] == "PENDING"
    assert data["requested_role"] == "tester"

    # Login should return PENDING_APPROVAL
    login_res = client.post(
        "/api/auth/login",
        json={"username": test_user, "password": "Valid#Password2026!"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["status"] == "PENDING_APPROVAL"
    token = login_res.json()["temp_token"]

    # Accessing protected tester endpoint must be rejected with 403
    prot_res = client.get(
        "/api/cognos/runs/1/test-cases",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert prot_res.status_code == 403
    assert "pending approval" in prot_res.json()["detail"].lower()
    cleanup_user(db, test_user)


def test_self_approval_is_forbidden(db: Session):
    """Users cannot approve their own access request."""
    cleanup_user(db, "self_approver")
    user = User(
        username="self_approver",
        hashed_password=hash_password("Dummy#Pass123!"),
        role="pending",
        status="PENDING",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    req = submit_access_request(db, cast(int, user.id), "tester", "Self test request reason")
    reviewer = CurrentUser(username="self_approver", role="admin", user_id=cast(int, user.id))

    with pytest.raises(ApprovalError, match="Self-approval is strictly forbidden"):
        approve_access_request(db, cast(int, req.id), reviewer, reason="Approving myself")

    cleanup_user(db, "self_approver")


def test_admin_cannot_approve_admin_request(db: Session):
    """Regular Admins cannot approve Admin access requests; only Standard Admin can."""
    cleanup_user(db, "aspiring_admin")
    cleanup_user(db, "regular_admin")

    candidate = User(
        username="aspiring_admin",
        hashed_password=hash_password("Dummy#Pass123!"),
        role="pending",
        status="PENDING",
    )
    admin_user = User(
        username="regular_admin",
        hashed_password=hash_password("Dummy#Pass123!"),
        role="admin",
        status="ACTIVE",
    )
    db.add_all([candidate, admin_user])
    db.commit()

    req = submit_access_request(db, cast(int, candidate.id), "admin", "Need admin rights for IT operations")

    # Regular admin tries to approve
    reg_reviewer = CurrentUser(username="regular_admin", role="admin", user_id=cast(int, admin_user.id))
    with pytest.raises(ApprovalError, match="exclusively by the Standard Administrator"):
        approve_access_request(db, cast(int, req.id), reg_reviewer, reason="Approved by coworker")

    # Standard admin approves
    std_reviewer = CurrentUser(username="obuli", role="standard_admin", user_id=999)
    approved = approve_access_request(db, cast(int, req.id), std_reviewer, reason="Verified corporate security clearance")
    assert approved.status == "APPROVED"

    db.refresh(candidate)
    assert candidate.role == "admin"
    assert candidate.status == "ACTIVE"

    cleanup_user(db, "aspiring_admin")
    cleanup_user(db, "regular_admin")


# ─── 3. STANDARD ADMIN PROTECTION TESTS ─────────────────────────────────────

def test_standard_admin_cannot_be_suspended_or_downgraded(db: Session):
    """Standard Admin account cannot be modified, suspended, or downgraded by any administrator."""
    admin = bootstrap_standard_admin(db)
    regular_admin = CurrentUser(username="regular_admin", role="admin", user_id=123)

    # Attempt to suspend Standard Admin
    with pytest.raises(UserError, match="Standard Administrator account cannot be suspended or revoked"):
        update_user_status(db, cast(int, admin.id), "SUSPENDED", regular_admin, reason="Malicious attack")

    # Attempt to downgrade Standard Admin role
    std_admin_actor = CurrentUser(username="obuli", role="standard_admin", user_id=cast(int, admin.id))
    with pytest.raises(UserError, match="Standard Administrator role cannot be changed"):
        update_user_role(db, cast(int, admin.id), "tester", std_admin_actor, reason="Self demote")


# ─── 4. ACCOUNT LOCKOUT TESTS ────────────────────────────────────────────────

def test_account_lockout_after_five_failures(db: Session):
    """Repeated failed login attempts trigger 15-minute temporary lockout."""
    cleanup_user(db, "lockout_victim")
    user = User(
        username="lockout_victim",
        hashed_password=hash_password("Target#Password123!"),
        role="tester",
        status="ACTIVE",
        failed_login_attempts=0,
    )
    db.add(user)
    db.commit()

    # Fail 4 times -> not locked yet
    for _ in range(4):
        is_locked = handle_failed_login(db, user)
        assert is_locked is False

    # 5th failure -> locked
    is_locked = handle_failed_login(db, user)
    assert is_locked is True

    locked, rem = is_account_locked(user)
    assert locked is True
    assert rem is not None and rem >= 14

    # Reset
    reset_failed_logins(db, user)
    locked, _ = is_account_locked(user)
    assert locked is False
    assert user.failed_login_attempts == 0
    cleanup_user(db, "lockout_victim")


# ─── 5. SESSION MANAGEMENT & LOGOUT TESTS ───────────────────────────────────

def test_session_lifecycle_and_logout_all(db: Session):
    """Validates session creation, activity tracking, single logout, and logout-all."""
    cleanup_user(db, "session_traveler")
    user = User(
        username="session_traveler",
        hashed_password=hash_password("Travel#2026Pass!"),
        role="tester",
        status="ACTIVE",
    )
    db.add(user)
    db.commit()

    # Create 3 sessions on different devices
    s1 = create_session(db, user, ip_address="1.1.1.1", user_agent="Mozilla/5.0 (Windows NT 10.0)")
    s2 = create_session(db, user, ip_address="2.2.2.2", user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16)")
    s3 = create_session(db, user, ip_address="3.3.3.3", user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X)")

    sessions = list_user_sessions(db, cast(int, user.id))
    assert len(sessions) == 3

    # Revoke single session (s1)
    ok = revoke_session(db, str(s1.session_id), reason="LOGOUT")
    assert ok is True

    # Revoke all remaining sessions
    revoked_count = revoke_all_user_sessions(db, cast(int, user.id), reason="LOGOUT_ALL")
    assert revoked_count == 2

    # Verify no active sessions remain
    active = db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.is_active == True).all()  # noqa: E712
    assert len(active) == 0
    cleanup_user(db, "session_traveler")


# ─── 6. TOTP RFC 6238 & BACKUP CODE TESTS ───────────────────────────────────

def test_totp_rfc6238_and_recovery_codes():
    """Validates TOTP secret generation, 6-digit verification, and backup codes single-use."""
    secret = generate_totp_secret()
    assert len(secret) >= 32

    # Verification of current code
    code = get_totp_code(secret)
    assert len(code) == 6
    assert verify_totp_code(secret, code) is True

    # Verification with drift (+30s)
    future_code = get_totp_code(secret, timestamp=datetime.now(timezone.utc).timestamp() + 30)
    assert verify_totp_code(secret, future_code, drift_steps=1) is True

    # Invalid code
    assert verify_totp_code(secret, "999999" if code != "999999" else "000000") is False

    # Backup codes
    plain_codes, hashed_codes = generate_backup_codes(4)
    assert len(plain_codes) == 4
    assert len(hashed_codes) == 4

    # Use first backup code
    used_code = plain_codes[0]
    matched, remaining = verify_backup_code(used_code, hashed_codes)
    assert matched is True
    assert len(remaining) == 3

    # Reusing same code must fail (single-use guarantee)
    matched2, _ = verify_backup_code(used_code, remaining)
    assert matched2 is False
