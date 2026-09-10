"""
Role-Based Access Control (RBAC) and Authorization Primitives.

Hierarchy:
  - "pending"        (0)  : Newly registered users awaiting access approval. Zero protected access.
  - "tester"         (10) : Day-to-day SIT/QA testing, scenario generation, refinement, review.
  - "approver"       (20) : Confirming Gatekeeper scope, signing off on test cases, and exporting.
  - "admin"          (30) : Tester approval, user management (excluding Standard Admin). Requires MFA.
  - "standard_admin" (40) : Supreme bootstrap authority. Approves Admins and Testers, manages system roles.
                            Protected against modification or downgrade by regular Admins.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Header, Request, Cookie
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token, TokenError
from app.db.session import get_db
from app.models.user import User
from app.models.rbac import UserSession
from app.models.audit import AuditLogEntry

ROLE_HIERARCHY = {
    "pending": 0,
    "tester": 10,
    "approver": 20,
    "admin": 30,
    "standard_admin": 40,
}


class CurrentUser:
    """
    Caller identity representation, containing verified role, active session,
    and permission evaluation helpers.
    """

    def __init__(
        self,
        username: str,
        role: str,
        user_id: int = 0,
        status: str = "ACTIVE",
        session_id: Optional[str] = None,
        must_change_password: bool = False,
        last_authenticated_at: Optional[datetime] = None,
    ):
        self.id = user_id
        self.username = username
        self.role = role
        self.status = status
        self.session_id = session_id
        self.must_change_password = must_change_password
        self.last_authenticated_at = last_authenticated_at or datetime.now(timezone.utc)

    def has_at_least(self, minimum_role: str) -> bool:
        user_role = (self.role or "").lower().replace("-", "_")
        min_role = (minimum_role or "").lower().replace("-", "_")
        return ROLE_HIERARCHY.get(user_role, -1) >= ROLE_HIERARCHY.get(min_role, 999)

    @property
    def is_standard_admin(self) -> bool:
        return (self.role or "").lower().replace("-", "_") == "standard_admin"

    @property
    def is_admin_or_higher(self) -> bool:
        return self.has_at_least("admin")


def _extract_token(
    request: Request,
    authorization: Optional[str] = None,
    cookie_session: Optional[str] = None,
) -> tuple[str, bool]:
    """
    Extracts authentication token. Checks Authorization Bearer header first,
    then falls back to HttpOnly session cookie.
    Returns: (token, is_session_id)
    """
    if authorization and authorization.startswith("Bearer "):
        return authorization[len("Bearer ") :].strip(), False

    if cookie_session:
        return cookie_session.strip(), True

    # Check cookies directly on request
    cookie_val = request.cookies.get("session_id")
    if cookie_val:
        return cookie_val.strip(), True

    raise HTTPException(
        status_code=401,
        detail="Missing authentication credentials. Please log in.",
    )


def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    auth_session_id: Optional[str] = Cookie(None, alias="session_id"),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """
    Validates caller authentication via server-side session or signed JWT.
    Enforces active user status, session validity, and idle timeouts.
    """
    raw_token, is_session_cookie = _extract_token(request, authorization, auth_session_id)
    now = datetime.now(timezone.utc)

    # 1. Try server-side session lookup first
    active_session = (
        db.query(UserSession)
        .filter(UserSession.session_id == raw_token, UserSession.is_active == True)  # noqa: E712
        .first()
    )

    user: Optional[User] = None
    session_token_used = None
    last_auth = now

    if active_session:
        # Check absolute session expiry
        exp = active_session.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now > exp:
            active_session.is_active = False
            active_session.revoked_reason = "EXPIRED"
            active_session.revoked_at = now
            db.commit()
            raise HTTPException(status_code=401, detail="Session has expired. Please log in again.")

        # Check idle timeout
        user = db.query(User).filter(User.id == active_session.user_id).first()
        if user:
            idle_limit = (
                settings.SESSION_IDLE_TIMEOUT_ADMIN_SECONDS
                if user.role in ("standard_admin", "admin")
                else settings.SESSION_IDLE_TIMEOUT_TESTER_SECONDS
            )
            last_act = active_session.last_activity_at
            if last_act.tzinfo is None:
                last_act = last_act.replace(tzinfo=timezone.utc)
            if (now - last_act).total_seconds() > idle_limit:
                active_session.is_active = False
                active_session.revoked_reason = "IDLE_TIMEOUT"
                active_session.revoked_at = now
                db.commit()
                raise HTTPException(
                    status_code=401,
                    detail="Session timed out due to inactivity. Please log in again.",
                )

            # Touch session
            active_session.last_activity_at = now
            db.commit()
            session_token_used = active_session.session_id
            last_auth = active_session.last_authenticated_at
            if last_auth.tzinfo is None:
                last_auth = last_auth.replace(tzinfo=timezone.utc)

    # 2. If not session cookie or session not found, try JWT validation
    if user is None:
        try:
            payload = decode_access_token(raw_token)
            username = payload.get("sub")
            user = db.query(User).filter(User.username == username).first()
        except TokenError as e:
            raise HTTPException(status_code=401, detail=str(e))

    if user is None:
        raise HTTPException(status_code=401, detail="User account not found.")

    # 3. Account status checks
    if not user.is_active or user.status == "SUSPENDED":
        raise HTTPException(
            status_code=403,
            detail="Account has been suspended. Please contact an administrator.",
        )
    if user.status == "REVOKED":
        raise HTTPException(
            status_code=403,
            detail="Account has been revoked.",
        )

    # 4. First-login password change gate
    # Allow calls only to password change endpoint when must_change_password is true
    path = request.url.path
    if user.must_change_password and not path.endswith("/change-password") and not path.endswith("/logout") and not path.endswith("/me"):
        raise HTTPException(
            status_code=403,
            detail="Password change required on first login before accessing the application.",
        )

    return CurrentUser(
        user_id=user.id,
        username=user.username,
        role=user.role,
        status=user.status,
        session_id=session_token_used,
        must_change_password=user.must_change_password,
        last_authenticated_at=last_auth,
    )


def require_role(minimum_role: str):
    """
    FastAPI dependency factory enforcing minimum hierarchical role.
    Logs ACCESS_DENIED to immutable audit log upon 403 authorization failures.
    Example: Depends(require_role("tester")) or Depends(require_role("admin"))
    """

    def _dependency(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        if current_user.status == "PENDING" or current_user.role == "pending":
            try:
                db.add(AuditLogEntry(
                    user_id=current_user.username,
                    event_type="ACCESS_DENIED",
                    detail=f"Pending user attempted to access {request.url.path}",
                ))
                db.commit()
            except Exception:
                db.rollback()
            raise HTTPException(
                status_code=403,
                detail="Access is pending approval. You do not have permissions for this resource.",
            )
        if not current_user.has_at_least(minimum_role):
            try:
                db.add(AuditLogEntry(
                    user_id=current_user.username,
                    event_type="ACCESS_DENIED",
                    detail=f"User '{current_user.username}' ({current_user.role}) attempted to access restricted endpoint {request.url.path} requiring '{minimum_role}'",
                ))
                db.commit()
            except Exception:
                db.rollback()
            raise HTTPException(
                status_code=403,
                detail=f"This action requires '{minimum_role}' role or higher; you are '{current_user.role}'.",
            )
        return current_user

    return _dependency


def require_standard_admin():
    """Requires caller to be the Standard Admin exclusively."""

    def _dependency(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        if not current_user.is_standard_admin:
            try:
                db.add(AuditLogEntry(
                    user_id=current_user.username,
                    event_type="ACCESS_DENIED",
                    detail=f"Non-standard-admin '{current_user.username}' attempted to access Standard Admin endpoint {request.url.path}",
                ))
                db.commit()
            except Exception:
                db.rollback()
            raise HTTPException(
                status_code=403,
                detail="This action is restricted exclusively to the Standard Administrator.",
            )
        return current_user

    return _dependency


def require_recent_auth(max_age_seconds: int = 300):
    """
    Enforces recent authentication (within max_age_seconds, default 5 mins)
    for high-security administrative operations (e.g. approving Admin requests, role changes).
    """

    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        now = datetime.now(timezone.utc)
        last_auth = current_user.last_authenticated_at
        if last_auth.tzinfo is None:
            last_auth = last_auth.replace(tzinfo=timezone.utc)

        elapsed = (now - last_auth).total_seconds()
        if elapsed > max_age_seconds:
            raise HTTPException(
                status_code=403,
                detail="Security check: Recent re-authentication required. Please confirm your credentials.",
            )
        return current_user

    return _dependency
