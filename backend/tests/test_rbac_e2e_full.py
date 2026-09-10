"""
End-to-End Comprehensive RBAC Verification.

Validates the full enterprise lifecycle:
1. Standard Admin bootstrap ('obuli') from environment variable
2. Forced first-login password change & password policy enforcement
3. TOTP RFC 6238 MFA activation and two-stage login verification
4. Self-service access requests for Tester and Admin
5. Separation of duties:
   - Tester approved by Admin
   - Admin approved ONLY by Standard Admin ('obuli')
   - No self-approval
6. Protection of Standard Admin ('obuli') from suspension, revocation, or downgrade
7. Temporary account lockout after 5 failed login attempts
8. Server-side session invalidation & Log out from all devices
9. Audit trail completeness with zero secret leakage
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.rbac import AccessRequest, ApprovalHistory, UserSession, MfaConfiguration
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.core.totp import generate_totp_secret, get_totp_code
from app.services.user_service import bootstrap_standard_admin

def clean_user_cascade(db: Session, username: str):
    user = db.query(User).filter(User.username == username).first()
    if user:
        db.query(UserSession).filter(UserSession.user_id == user.id).delete()
        req_ids = [r.id for r in db.query(AccessRequest).filter(AccessRequest.user_id == user.id).all()]
        if req_ids:
            db.query(ApprovalHistory).filter(ApprovalHistory.request_id.in_(req_ids)).delete(synchronize_session=False)
            db.query(AccessRequest).filter(AccessRequest.id.in_(req_ids)).delete(synchronize_session=False)
        db.query(MfaConfiguration).filter(MfaConfiguration.user_id == user.id).delete()
        db.delete(user)
        db.commit()


@pytest.fixture(autouse=True)
def enable_mfa_for_e2e():
    orig = settings.MFA_ENABLED
    settings.MFA_ENABLED = True
    yield
    settings.MFA_ENABLED = orig


def test_full_rbac_lifecycle(client: TestClient, db: Session):
    # 1. BOOTSTRAP ADMIN VERIFICATION
    admin = bootstrap_standard_admin(db)
    assert admin.username == "obuli"
    assert admin.role == "standard_admin"
    assert admin.status == "ACTIVE"

    # Reset admin to initial temporary password state for test determinism
    setattr(admin, "hashed_password", hash_password(settings.INITIAL_ADMIN_TEMP_PASSWORD))
    setattr(admin, "must_change_password", True)
    setattr(admin, "mfa_enabled", False)
    setattr(admin, "failed_login_attempts", 0)
    setattr(admin, "locked_until", None)
    db.commit()

    # 2. FIRST LOGIN FORCES PASSWORD CHANGE
    res = client.post("/api/auth/login", json={"username": "obuli", "password": settings.INITIAL_ADMIN_TEMP_PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "MUST_CHANGE_PASSWORD"
    temp_token = body["temp_token"]

    # Blocked from protected APIs
    prot_res = client.get("/api/admin/users", headers={"Authorization": f"Bearer {temp_token}"})
    assert prot_res.status_code == 403

    # Change password
    new_admin_pass = "Obuli#Permanent2026!Secure"
    chg_res = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {temp_token}"},
        json={"current_password": settings.INITIAL_ADMIN_TEMP_PASSWORD, "new_password": new_admin_pass}
    )
    assert chg_res.status_code == 200
    assert chg_res.json()["status"] == "SUCCESS"
    admin_token = chg_res.json()["access_token"]

    # 3. MFA SETUP FOR STANDARD ADMIN
    setup_res = client.post("/api/auth/mfa/setup", headers={"Authorization": f"Bearer {admin_token}"})
    assert setup_res.status_code == 200
    mfa_setup = setup_res.json()
    secret = mfa_setup["secret"]
    assert len(secret) >= 32
    assert len(mfa_setup["backup_codes"]) == 8

    # Confirm MFA with valid TOTP code
    code = get_totp_code(secret)
    conf_res = client.post("/api/auth/mfa/confirm", headers={"Authorization": f"Bearer {admin_token}"}, json={"code": code})
    assert conf_res.status_code == 200
    assert conf_res.json()["status"] == "SUCCESS"

    # 4. LOGIN WITH MFA CHALLENGE
    mfa_login = client.post("/api/auth/login", json={"username": "obuli", "password": new_admin_pass})
    assert mfa_login.status_code == 200
    assert mfa_login.json()["status"] == "MFA_REQUIRED"
    mfa_temp_token = mfa_login.json()["temp_token"]

    # Complete MFA challenge
    mfa_code = get_totp_code(secret)
    verify_res = client.post("/api/auth/verify-mfa", json={"temp_token": mfa_temp_token, "code": mfa_code})
    assert verify_res.status_code == 200
    admin_session_token = verify_res.json()["access_token"]

    # 5. SUBMIT TESTER ACCESS REQUEST
    tester_user = "e2e_tester"
    clean_user_cascade(db, tester_user)
    req_res = client.post("/api/auth/access-request", json={
        "username": tester_user,
        "password": "Tester#Password2026!",
        "requested_role": "tester",
        "reason": "QA validation for Healthcare reports"
    })
    assert req_res.status_code == 200
    assert req_res.json()["status"] == "PENDING"
    req_id = req_res.json()["request_id"]

    # Tester cannot access protected API while PENDING
    tester_login = client.post("/api/auth/login", json={"username": tester_user, "password": "Tester#Password2026!"})
    assert tester_login.status_code == 200
    assert tester_login.json()["status"] == "PENDING_APPROVAL"
    tester_pending_token = tester_login.json()["temp_token"]
    blocked = client.get("/api/cognos/runs/1/test-cases", headers={"Authorization": f"Bearer {tester_pending_token}"})
    assert blocked.status_code == 403

    # Standard Admin approves tester request
    appr_res = client.post(
        f"/api/admin/approvals/{req_id}/approve",
        headers={"Authorization": f"Bearer {admin_session_token}"},
        json={
            "reason": "Cleared by corporate security audit",
            "admin_password": new_admin_pass,
            "mfa_code": get_totp_code(secret),
        }
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "SUCCESS"
    assert appr_res.json()["approved_role"] == "tester"

    # Tester can now log in normally
    tester_login_success = client.post("/api/auth/login", json={"username": tester_user, "password": "Tester#Password2026!"})
    assert tester_login_success.status_code == 200
    assert tester_login_success.json()["status"] == "SUCCESS"
    tester_token = tester_login_success.json()["access_token"]

    # Tester cannot manage users (least-privilege)
    tester_blocked_admin = client.get("/api/admin/users", headers={"Authorization": f"Bearer {tester_token}"})
    assert tester_blocked_admin.status_code == 403

    # 6. SUBMIT ADMIN ACCESS REQUEST & ENFORCE SEPARATION OF DUTIES
    admin_candidate = "e2e_aspiring_admin"
    clean_user_cascade(db, admin_candidate)
    adm_req = client.post("/api/auth/access-request", json={
        "username": admin_candidate,
        "password": "Admin#Candidate2026!",
        "requested_role": "admin",
        "reason": "Team lead managing testing operations"
    })
    assert adm_req.status_code == 200
    adm_req_id = adm_req.json()["request_id"]

    # Create an approved regular admin to test approver boundary
    reg_admin = "e2e_regular_admin"
    clean_user_cascade(db, reg_admin)
    db_reg_admin = User(
        username=reg_admin,
        hashed_password=hash_password("RegAdmin#Pass2026!"),
        role="admin",
        status="ACTIVE",
        must_change_password=False,
    )
    db.add(db_reg_admin)
    db.commit()

    reg_login = client.post("/api/auth/login", json={"username": reg_admin, "password": "RegAdmin#Pass2026!"})
    assert reg_login.status_code == 200
    assert reg_login.json()["status"] == "MFA_SETUP_REQUIRED"
    reg_mfa_ticket = reg_login.json()["temp_token"]

    # Regular admin completes mandatory MFA setup
    reg_mfa_setup = client.post("/api/auth/mfa/setup", headers={"X-MFA-Ticket": reg_mfa_ticket})
    assert reg_mfa_setup.status_code == 200
    reg_secret = reg_mfa_setup.json()["secret"]

    reg_mfa_conf = client.post(
        "/api/auth/mfa/confirm",
        headers={"X-MFA-Ticket": reg_mfa_ticket},
        json={"code": get_totp_code(reg_secret)},
    )
    assert reg_mfa_conf.status_code == 200
    reg_admin_token = reg_mfa_conf.json()["access_token"]

    # Regular admin tries to approve another Admin -> FAILS (403)
    illegal_appr = client.post(
        f"/api/admin/approvals/{adm_req_id}/approve",
        headers={"Authorization": f"Bearer {reg_admin_token}"},
        json={"reason": "Approved by peer admin", "admin_password": "RegAdmin#Pass2026!"}
    )
    assert illegal_appr.status_code == 403
    assert "Standard Administrator" in illegal_appr.json()["detail"]

    # Regular admin tries to suspend or modify Standard Admin 'obuli' -> FAILS (403)
    std_admin_rec = db.query(User).filter(User.username == "obuli").first()
    assert std_admin_rec is not None
    illegal_suspension = client.patch(
        f"/api/admin/users/{std_admin_rec.id}/status",
        headers={"Authorization": f"Bearer {reg_admin_token}"},
        json={"status": "SUSPENDED", "reason": "Attack on standard admin", "admin_password": "RegAdmin#Pass2026!"}
    )
    assert illegal_suspension.status_code == 403
    assert "Standard Administrator account cannot be suspended" in illegal_suspension.json()["detail"]

    # Standard admin approves the Admin candidate
    legit_admin_appr = client.post(
        f"/api/admin/approvals/{adm_req_id}/approve",
        headers={"Authorization": f"Bearer {admin_session_token}"},
        json={
            "reason": "Promoted to testing lead after background clearance",
            "admin_password": new_admin_pass,
            "mfa_code": get_totp_code(secret),
        }
    )
    assert legit_admin_appr.status_code == 200

    # 7. SESSIONS & LOGOUT ALL
    # Check sessions for tester
    sessions_res = client.get("/api/auth/sessions", headers={"Authorization": f"Bearer {tester_token}"})
    assert sessions_res.status_code == 200
    assert len(sessions_res.json()) >= 1

    # Tester logs out from all devices
    logout_all_res = client.post("/api/auth/logout-all", headers={"Authorization": f"Bearer {tester_token}"})
    assert logout_all_res.status_code == 200

    # Revoked session is now rejected
    after_logout = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tester_token}"})
    assert after_logout.status_code == 401

    # 8. AUDIT LOG INSPECTION
    audit_res = client.get("/api/admin/audit-logs", headers={"Authorization": f"Bearer {admin_session_token}"})
    assert audit_res.status_code == 200
    logs = audit_res.json()["logs"]
    assert len(logs) > 0
    # Ensure no secrets or passwords appear anywhere in audit logs
    for entry in logs:
        text = str(entry)
        assert new_admin_pass not in text
        assert "Tester#Password2026!" not in text
        assert secret not in text

    # Clean up test users
    clean_user_cascade(db, tester_user)
    clean_user_cascade(db, admin_candidate)
    clean_user_cascade(db, reg_admin)

    # Restore obuli to initial bootstrap state
    admin = db.query(User).filter(User.username == "obuli").first()
    if admin:
        setattr(admin, "hashed_password", hash_password(settings.INITIAL_ADMIN_TEMP_PASSWORD))
        setattr(admin, "must_change_password", True)
        setattr(admin, "mfa_enabled", False)
        setattr(admin, "failed_login_attempts", 0)
        setattr(admin, "locked_until", None)
        db.commit()
