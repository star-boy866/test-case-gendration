"""
Authentication API Endpoints.

Implements:
- 2-Stage secure login with Argon2id and TOTP RFC 6238 MFA
- First-login forced password change
- 5-strike account lockout prevention
- Self-service access request (registration) for Pending users
- HttpOnly cookie and Bearer token session management
- Immediate session revocation and "Log out from all devices"
- Re-authentication for high-security actions
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Body, Header, Cookie
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import get_current_user, CurrentUser, require_role
from app.core.security import (
    verify_password,
    hash_password,
    validate_password_strength,
    create_access_token,
    decode_access_token,
    TokenError,
)
from app.db.session import get_db
from app.models.user import User
from app.models.rbac import AccessRequest, UserSession
from app.models.audit import AuditLogEntry
from app.services.audit_service import log_audit_event, log_login_event
from app.services.session_service import (
    create_session,
    revoke_session,
    revoke_all_user_sessions,
    list_user_sessions,
    touch_session_reauth,
)
from app.services.mfa_service import (
    setup_mfa,
    confirm_mfa_setup,
    verify_login_mfa,
)
from app.services.user_service import (
    is_account_locked,
    handle_failed_login,
    reset_failed_logins,
    change_user_password,
)
from app.services.approval_service import submit_access_request, ApprovalError

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class MfaVerifyRequest(BaseModel):
    mfa_ticket: Optional[str] = None
    temp_token: Optional[str] = None
    code: str  # 6-digit TOTP code or 9-char backup recovery code


class MfaConfirmRequest(BaseModel):
    code: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    username: Optional[str] = None
    temp_token: Optional[str] = None


class AccessRegistrationRequest(BaseModel):
    username: str
    password: str
    requested_role: str = "tester"  # tester | admin
    reason: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters.")
        return v

    @field_validator("requested_role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("tester", "admin"):
            raise ValueError("Requested role must be 'tester' or 'admin'.")
        return v


class ReauthRequest(BaseModel):
    password: str


def _set_session_cookie(response: Response, session_token: str) -> None:
    """Sets a secure, HttpOnly, SameSite cookie containing the session token."""
    response.set_cookie(
        key="session_id",
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in HTTPS/production deployments
        max_age=settings.SESSION_LIFETIME_TESTER_SECONDS,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    """Clears the session cookie."""
    response.delete_cookie(key="session_id", path="/")


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Step 1 of login:
    - Verifies credentials
    - Checks for lockout
    - Routes to MUST_CHANGE_PASSWORD, MFA_REQUIRED, MFA_SETUP_REQUIRED, or SUCCESS
    """
    generic_error = HTTPException(status_code=401, detail="Invalid username or password.")

    ip = request.client.host if request.client else "127.0.0.1"
    ua = request.headers.get("user-agent", "Unknown")

    user = db.query(User).filter(User.username == payload.username.strip()).first()
    if not user:
        # Record failed attempt to audit log
        log_audit_event(db, actor_username=payload.username, actor_role="unknown", action="LOGIN_FAILED", success=False, ip_address=ip, user_agent=ua)
        log_login_event(db, username=payload.username, success=False, ip_address=ip, user_agent=ua, failure_reason="User not found")
        raise generic_error

    # Check account lockout
    locked, remaining_minutes = is_account_locked(user)
    if locked:
        log_audit_event(db, actor_username=user.username, actor_role=user.role, action="LOGIN_FAILED", success=False, ip_address=ip, user_agent=ua, details={"reason": "locked"})
        log_login_event(db, username=user.username, success=False, user_id=user.id, ip_address=ip, user_agent=ua, failure_reason="Account locked")
        raise HTTPException(
            status_code=403,
            detail=f"Account is temporarily locked due to repeated failed login attempts. Please try again in {remaining_minutes} minute(s).",
        )

    # Verify password
    if not verify_password(payload.password, str(user.hashed_password)):
        is_locked_now = handle_failed_login(db, user)
        log_audit_event(db, actor_username=user.username, actor_role=user.role, action="LOGIN_FAILED", success=False, ip_address=ip, user_agent=ua, actor_user_id=user.id)
        log_login_event(db, username=user.username, success=False, user_id=user.id, ip_address=ip, user_agent=ua, failure_reason="Invalid credentials")
        if is_locked_now:
            raise HTTPException(
                status_code=403,
                detail=f"Account has been locked for {settings.ACCOUNT_LOCKOUT_MINUTES} minutes due to repeated failed login attempts.",
            )
        raise generic_error

    # Credentials valid -> reset failed attempts
    reset_failed_logins(db, user)

    # Check status
    if not user.is_active or user.status == "SUSPENDED":
        raise HTTPException(status_code=403, detail="Account has been suspended. Please contact an administrator.")
    if user.status == "REVOKED":
        raise HTTPException(status_code=403, detail="Account has been revoked.")

    user_info = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "status": user.status,
        "must_change_password": user.must_change_password,
        "mfa_enabled": user.mfa_enabled,
    }

    # Case 1: First login password change required
    if user.must_change_password:
        temp_token = create_access_token(
            subject=str(user.username),
            role=str(user.role),
            expires_seconds=900,  # 15 minutes to change password
        )
        return {
            "status": "MUST_CHANGE_PASSWORD",
            "temp_token": temp_token,
            "message": "Password change required before accessing the application.",
            "user": user_info,
        }

    # Case 2: Pending access approval
    if user.status == "PENDING" or user.role == "pending":
        temp_token = create_access_token(
            subject=str(user.username),
            role="pending",
            expires_seconds=7200,
        )
        return {
            "status": "PENDING_APPROVAL",
            "temp_token": temp_token,
            "message": "Your access request is currently pending administrative approval.",
            "user": user_info,
        }

    # Case 3: MFA is enabled -> require 6-digit TOTP code
    if settings.MFA_ENABLED and user.mfa_enabled:
        mfa_ticket = create_access_token(
            subject=str(user.username),
            role="mfa_pending",
            expires_seconds=300,  # 5 minutes to submit code
        )
        return {
            "status": "MFA_REQUIRED",
            "mfa_ticket": mfa_ticket,
            "temp_token": mfa_ticket,
            "message": "Please enter the 6-digit verification code from your authenticator app.",
            "user": {"username": user.username},
        }

    # Case 4: Admin account without MFA -> require MFA setup
    if settings.MFA_ENABLED and user.role in ("standard_admin", "admin") and not user.mfa_enabled:
        mfa_ticket = create_access_token(
            subject=str(user.username),
            role="mfa_pending",
            expires_seconds=600,
        )
        return {
            "status": "MFA_SETUP_REQUIRED",
            "mfa_ticket": mfa_ticket,
            "temp_token": mfa_ticket,
            "message": "Multi-factor authentication is mandatory for administrative accounts. Please configure MFA.",
            "user": {"username": user.username},
        }

    # Case 5: Standard login success -> create session
    ip = request.client.host if request.client else "127.0.0.1"
    ua = request.headers.get("user-agent", "Unknown")
    session = create_session(db, user, ip_address=ip, user_agent=ua)
    _set_session_cookie(response, str(session.session_id))

    log_audit_event(
        db,
        actor_username=user.username,
        actor_role=user.role,
        action="LOGIN_SUCCESS",
        success=True,
        ip_address=ip,
        user_agent=ua,
        actor_user_id=user.id
    )
    log_login_event(db, username=user.username, success=True, user_id=user.id, ip_address=ip, user_agent=ua)

    return {
        "status": "SUCCESS",
        "access_token": session.session_id,
        "token_type": "bearer",
        "role": user.role,
        "user": user_info,
    }


def _resolve_target_user(
    db: Session,
    request: Optional[Request] = None,
    mfa_ticket: Optional[str] = None,
    authorization: Optional[str] = None,
    session_id: Optional[str] = None,
    username: Optional[str] = None,
    temp_token: Optional[str] = None,
) -> User:
    """Resolves target user from ticket, Bearer token (JWT or session), session cookie, or username/temp_token."""
    raw_token = temp_token or mfa_ticket
    if raw_token:
        try:
            payload = decode_access_token(raw_token)
            u = db.query(User).filter(User.username == payload.get("sub")).first()
            if u:
                return u
        except TokenError:
            pass

    auth = authorization or (request.headers.get("authorization") if request else None)
    if auth and auth.startswith("Bearer "):
        token = auth[len("Bearer ") :].strip()
        try:
            payload = decode_access_token(token)
            u = db.query(User).filter(User.username == payload.get("sub")).first()
            if u:
                return u
        except TokenError:
            pass
        active_sess = db.query(UserSession).filter(UserSession.session_id == token, UserSession.is_active == True).first()  # noqa: E712
        if active_sess:
            u = db.query(User).filter(User.id == active_sess.user_id).first()
            if u:
                return u

    s_id = session_id or (request.cookies.get("session_id") if request else None)
    if s_id:
        active_sess = db.query(UserSession).filter(UserSession.session_id == s_id, UserSession.is_active == True).first()  # noqa: E712
        if active_sess:
            u = db.query(User).filter(User.id == active_sess.user_id).first()
            if u:
                return u

    if username:
        u = db.query(User).filter(User.username == username.strip()).first()
        if u:
            return u

    raise HTTPException(status_code=401, detail="Authentication required. Please log in again.")


@router.post("/mfa/verify")
@router.post("/verify-mfa")
def verify_mfa(payload: MfaVerifyRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Validates 6-digit TOTP code or single-use recovery code and creates session."""
    raw_ticket = payload.temp_token or payload.mfa_ticket
    if not raw_ticket:
        raise HTTPException(status_code=400, detail="MFA verification ticket is required.")

    try:
        token_data = decode_access_token(raw_ticket)
    except TokenError:
        raise HTTPException(status_code=401, detail="Verification session expired. Please log in again.")

    username = token_data.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User account not found.")

    if not verify_login_mfa(db, user, payload.code):
        db.add(AuditLogEntry(user_id=user.username, event_type="MFA_VERIFY_FAILED", detail=None))
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid verification code or backup code.")

    ip = request.client.host if request.client else "127.0.0.1"
    ua = request.headers.get("user-agent", "Unknown")
    session = create_session(db, user, ip_address=ip, user_agent=ua)
    _set_session_cookie(response, str(session.session_id))

    db.add(AuditLogEntry(user_id=user.username, event_type="MFA_VERIFY_SUCCEEDED", detail=None))
    db.commit()

    return {
        "status": "SUCCESS",
        "access_token": session.session_id,
        "token_type": "bearer",
        "role": user.role,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "status": user.status,
            "must_change_password": user.must_change_password,
            "mfa_enabled": user.mfa_enabled,
        },
    }


@router.post("/mfa/setup")
def initiate_mfa(
    request: Request,
    mfa_ticket: Optional[str] = Header(None, alias="X-MFA-Ticket"),
    authorization: Optional[str] = Header(None),
    session_id: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    """Generates a new TOTP secret, otpauth URI, and emergency backup codes."""
    target_user = _resolve_target_user(db, request, mfa_ticket, authorization, session_id)
    return setup_mfa(db, target_user)


@router.post("/mfa/confirm")
def confirm_mfa(
    payload: MfaConfirmRequest,
    request: Request,
    response: Response,
    mfa_ticket: Optional[str] = Header(None, alias="X-MFA-Ticket"),
    authorization: Optional[str] = Header(None),
    session_id: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    """Validates the first code to formally activate MFA on the account."""
    target_user = _resolve_target_user(db, request, mfa_ticket, authorization, session_id)

    if not confirm_mfa_setup(db, target_user, payload.code):
        raise HTTPException(status_code=400, detail="Invalid verification code. Please check your authenticator clock.")

    # Create active session
    ip = request.client.host if request.client else "127.0.0.1"
    ua = request.headers.get("user-agent", "Unknown")
    session = create_session(db, target_user, ip_address=ip, user_agent=ua)
    _set_session_cookie(response, str(session.session_id))

    db.add(AuditLogEntry(user_id=target_user.username, event_type="MFA_ACTIVATED", detail=None))
    db.commit()

    return {
        "status": "SUCCESS",
        "message": "Multi-factor authentication activated successfully.",
        "access_token": session.session_id,
        "token_type": "bearer",
        "role": target_user.role,
        "user": {
            "id": target_user.id,
            "username": target_user.username,
            "role": target_user.role,
            "status": target_user.status,
            "must_change_password": target_user.must_change_password,
            "mfa_enabled": target_user.mfa_enabled,
        },
    }


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    authorization: Optional[str] = Header(None),
    session_id: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    """Changes password, clears first-login flag, revokes previous sessions, and issues a fresh session."""
    user = _resolve_target_user(
        db=db,
        request=request,
        mfa_ticket=None,
        authorization=authorization,
        session_id=session_id,
        username=payload.username,
        temp_token=payload.temp_token,
    )

    try:
        change_user_password(db, user, payload.current_password, payload.new_password)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Issue fresh active session
    ip = request.client.host if request and request.client else "127.0.0.1"
    ua = request.headers.get("user-agent", "Unknown") if request else "Unknown"
    new_session = create_session(db, user, ip_address=ip, user_agent=ua)
    _set_session_cookie(response, str(new_session.session_id))

    return {
        "status": "SUCCESS",
        "message": "Password changed successfully.",
        "access_token": new_session.session_id,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "status": user.status,
            "must_change_password": user.must_change_password,
            "mfa_enabled": user.mfa_enabled,
        },
    }


@router.post("/access-request")
def request_access(payload: AccessRegistrationRequest, db: Session = Depends(get_db)):
    """Self-service registration: creates an account in PENDING status and logs access request."""
    # Check if username exists
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Username '{payload.username}' is already taken.")

    # Validate password strength
    is_strong, err = validate_password_strength(payload.password, payload.username)
    if not is_strong:
        raise HTTPException(status_code=400, detail=err)

    now = datetime.now(timezone.utc)
    new_user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role="pending",
        status="PENDING",
        is_active=True,
        must_change_password=False,
        mfa_enabled=False,
        failed_login_attempts=0,
        created_at=now,
    )
    db.add(new_user)
    db.flush()

    try:
        req = submit_access_request(
            db=db,
            user_id=cast(int, new_user.id),
            requested_role=payload.requested_role,
            reason=payload.reason,
        )
    except ApprovalError as ae:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(ae))

    return {
        "status": "PENDING",
        "request_id": req.id,
        "username": new_user.username,
        "requested_role": req.requested_role,
        "message": f"Your request for '{req.requested_role}' access has been submitted for administrative review.",
    }


@router.get("/access-request/status")
def get_request_status(
    username: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns access request status for the logged-in user."""
    lookup_name = username if (current_user.is_admin_or_higher and username) else current_user.username
    user = db.query(User).filter(User.username == lookup_name).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    req = (
        db.query(AccessRequest)
        .filter(AccessRequest.user_id == user.id)
        .order_by(AccessRequest.created_at.desc())
        .first()
    )
    if not req:
        return {"has_request": False, "status": user.status, "role": user.role}

    return {
        "has_request": True,
        "request_id": req.id,
        "requested_role": req.requested_role,
        "status": req.status,
        "reason": req.request_reason,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "review_reason": req.review_reason,
        "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
    }


@router.post("/logout")
def logout(
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revokes the active server-side session and clears the session cookie."""
    if current_user.session_id:
        revoke_session(db, current_user.session_id, reason="LOGOUT")
    _clear_session_cookie(response)

    db.add(AuditLogEntry(user_id=current_user.username, event_type="LOGOUT", detail=None))
    db.commit()

    return {"status": "SUCCESS", "message": "Successfully logged out."}


@router.post("/logout-all")
def logout_all(
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revokes all active sessions for the caller across all devices."""
    count = revoke_all_user_sessions(db, current_user.id, reason="LOGOUT_ALL")
    _clear_session_cookie(response)

    db.add(AuditLogEntry(
        user_id=current_user.username,
        event_type="LOGOUT_ALL_DEVICES",
        detail=f'{{"revoked_sessions_count": {count}}}',
    ))
    db.commit()

    return {"status": "SUCCESS", "revoked_count": count, "message": "All devices logged out."}


@router.get("/sessions")
def get_sessions(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists active and recent sessions for the current caller."""
    return list_user_sessions(db, current_user.id, current_session_id=current_user.session_id)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revokes a specific session belonging to the caller."""
    session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.user_id != current_user.id and not current_user.is_admin_or_higher:
        raise HTTPException(status_code=403, detail="Cannot revoke another user's session.")

    revoke_session(db, session_id, reason="MANUAL_REVOCATION")
    return {"status": "SUCCESS", "message": "Session terminated."}


@router.post("/reauthenticate")
def reauthenticate(
    payload: ReauthRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verifies password to refresh last_authenticated_at timestamp for sensitive operations."""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user or not verify_password(payload.password, str(user.hashed_password)):
        raise HTTPException(status_code=401, detail="Invalid password.")

    if current_user.session_id:
        touch_session_reauth(db, current_user.session_id)

    db.add(AuditLogEntry(user_id=current_user.username, event_type="REAUTHENTICATION_SUCCEEDED", detail=None))
    db.commit()

    return {"status": "SUCCESS", "message": "Identity re-verified successfully."}


@router.get("/me")
def me(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns profile and permission details for the current user."""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    has_db_read = False
    norm_role = (user.role or "").lower().replace("-", "_")
    if norm_role == "admin":
        has_db_read = True
    elif norm_role == "standard_admin":
        try:
            from app.models.rbac import role_permissions, Permission, Role
            has_db_read = bool(
                db.query(Permission.id)
                .join(role_permissions, Permission.id == role_permissions.c.permission_id)
                .join(Role, role_permissions.c.role_id == Role.id)
                .filter(Role.name == "standard_admin", Permission.code == "database:read")
                .first()
            )
        except Exception:
            has_db_read = False

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "status": user.status,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "mfa_enabled": user.mfa_enabled,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "has_database_read": has_db_read,
    }
