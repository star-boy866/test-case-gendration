"""
User Management & Lifecycle Service.

Implements:
- Bootstrap Standard Admin account ('obuli') from secure environment configuration.
- Password change enforcement on first login.
- Failed attempt rate-limiting, progressive delay, and 15-minute temporary lockout.
- User account activation, suspension, and revocation with protection for Standard Admin.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List, Dict, Any, cast

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
)
from app.core.rbac import CurrentUser
from app.models.user import User
from app.models.audit import AuditLogEntry
from app.services.session_service import revoke_all_user_sessions

logger = logging.getLogger(__name__)

_VALID_ROLES = {"standard_admin", "admin", "approver", "tester", "pending"}


class UserError(Exception):
    """Raised for business logic / authorization violations in user management."""


def bootstrap_standard_admin(db: Session) -> User:
    """
    Creates exactly one initial Standard Admin account ('obuli') if it doesn't already exist.
    Loads initial password from environment (never hardcoded in scripts or repo).
    If INITIAL_ADMIN_PASSWORD is set in .env, applies it as permanent password.
    """
    admin_user = (
        db.query(User)
        .filter((User.username == settings.INITIAL_ADMIN_USERNAME) | (User.role == "standard_admin"))
        .first()
    )
    if admin_user:
        # Existing account: ensure account is active and preserve intentional password changes
        if not admin_user.hashed_password:
            admin_pass = settings.INITIAL_ADMIN_PASSWORD or settings.INITIAL_ADMIN_TEMP_PASSWORD
            if admin_pass:
                admin_user.hashed_password = hash_password(admin_pass)
                db.commit()
                db.refresh(admin_user)
        return admin_user

    admin_pass = settings.INITIAL_ADMIN_PASSWORD or settings.INITIAL_ADMIN_TEMP_PASSWORD
    if not admin_pass:
        raise ValueError(
            "INITIAL_ADMIN_TEMP_PASSWORD or INITIAL_ADMIN_PASSWORD is not set in environment. "
            "Please configure INITIAL_ADMIN_TEMP_PASSWORD in backend/.env to bootstrap the Standard Admin."
        )

    must_change = not bool(settings.INITIAL_ADMIN_PASSWORD)
    now = datetime.now(timezone.utc)
    user = User(
        username=settings.INITIAL_ADMIN_USERNAME,
        hashed_password=hash_password(admin_pass),
        role="standard_admin",
        status="ACTIVE",
        is_active=True,
        must_change_password=must_change,
        mfa_enabled=False,
        failed_login_attempts=0,
        created_at=now,
    )
    db.add(user)
    db.flush()

    db.add(AuditLogEntry(
        user_id=settings.INITIAL_ADMIN_USERNAME,
        event_type="BOOTSTRAP_STANDARD_ADMIN_INITIALIZED",
        detail=json.dumps({
            "username": settings.INITIAL_ADMIN_USERNAME,
            "role": "standard_admin",
            "must_change_password": must_change,
        }),
    ))
    db.commit()
    db.refresh(user)
    logger.info(f"Standard Admin '{settings.INITIAL_ADMIN_USERNAME}' initialized successfully.")
    return user


def ensure_tester_account(db: Session) -> User:
    """Ensures a default active tester account ('tester') is available for QA validation."""
    tester = db.query(User).filter(User.username == "tester").first()
    if tester:
        if not tester.hashed_password:
            tester.hashed_password = hash_password("Tester#Password2026!")
        tester.is_active = True
        tester.status = "ACTIVE"
        db.commit()
        db.refresh(tester)
        return tester

    now = datetime.now(timezone.utc)
    user = User(
        username="tester",
        hashed_password=hash_password("Tester#Password2026!"),
        role="tester",
        status="ACTIVE",
        is_active=True,
        must_change_password=False,
        mfa_enabled=False,
        failed_login_attempts=0,
        created_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def is_account_locked(user: User) -> Tuple[bool, Optional[int]]:
    """Checks if user account is currently locked out."""
    if not user.locked_until:
        return False, None
    now = datetime.now(timezone.utc)
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)

    if now < locked_until:
        remaining_minutes = max(1, int((locked_until - now).total_seconds() // 60))
        return True, remaining_minutes
    return False, None


def handle_failed_login(db: Session, user: User) -> bool:
    """
    Increments failed login counter and triggers temporary lockout if threshold reached.
    Returns True if account is now locked.
    """
    now = datetime.now(timezone.utc)
    user.failed_login_attempts += 1
    locked = False

    if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = now + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
        locked = True
        db.add(AuditLogEntry(
            user_id=user.username,
            event_type="ACCOUNT_LOCKED",
            detail=json.dumps({
                "username": user.username,
                "failed_attempts": user.failed_login_attempts,
                "lockout_minutes": settings.ACCOUNT_LOCKOUT_MINUTES,
            }),
        ))

    db.commit()
    return locked


def reset_failed_logins(db: Session, user: User) -> None:
    """Resets failed attempt counter and updates last login timestamp."""
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()


def change_user_password(
    db: Session,
    user: User,
    old_password: str,
    new_password: str,
) -> None:
    """
    Changes a user's password:
    - Verifies old password
    - Validates new password strength
    - Checks that new password is not identical to old password
    - Clears must_change_password flag
    - Revokes all active sessions for security
    """
    if not verify_password(old_password, str(user.hashed_password)):
        raise UserError("Current password entered is incorrect.")

    if old_password == new_password:
        raise UserError("New password cannot be the same as your current password.")

    is_strong, err_msg = validate_password_strength(new_password, str(user.username))
    if not is_strong:
        raise UserError(err_msg)

    now = datetime.now(timezone.utc)
    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    user.last_password_change_at = now

    # Invalidate all active sessions after password change
    revoke_all_user_sessions(db, cast(int, user.id), reason="PASSWORD_RESET")

    db.add(AuditLogEntry(
        user_id=user.username,
        event_type="PASSWORD_CHANGED",
        detail=json.dumps({"username": user.username}),
    ))
    db.commit()


def update_user_status(
    db: Session,
    target_user_id: int,
    new_status: str,
    actor: CurrentUser,
    reason: str,
) -> User:
    """
    Updates user account status (ACTIVE, SUSPENDED, REVOKED).
    - Standard Admin cannot be suspended or revoked.
    - Regular Admin cannot modify Standard Admin or other Admins.
    """
    new_status = new_status.upper().strip()
    if new_status not in ("ACTIVE", "SUSPENDED", "REVOKED"):
        raise UserError(f"Invalid status '{new_status}'. Must be ACTIVE, SUSPENDED, or REVOKED.")

    target = db.query(User).filter(User.id == target_user_id).first()
    if not target:
        raise UserError("User account not found.")

    # Guard: Standard Admin cannot be modified
    if target.role == "standard_admin":
        raise UserError("The Standard Administrator account cannot be suspended or revoked.")

    # Guard: Regular Admin cannot modify other Admins
    if not actor.is_standard_admin and target.role in ("admin", "standard_admin"):
        raise UserError("Only the Standard Administrator can modify Administrator accounts.")

    old_status = target.status
    target.status = new_status
    target.is_active = (new_status == "ACTIVE")

    if new_status in ("SUSPENDED", "REVOKED"):
        revoke_all_user_sessions(db, cast(int, target.id), reason=new_status)

    db.add(AuditLogEntry(
        user_id=actor.username,
        event_type="USER_STATUS_UPDATED",
        detail=json.dumps({
            "target_user": target.username,
            "old_status": old_status,
            "new_status": new_status,
            "changed_by": actor.username,
            "reason": reason,
        }),
    ))
    db.commit()
    db.refresh(target)
    return target


def update_user_role(
    db: Session,
    target_user_id: int,
    new_role: str,
    actor: CurrentUser,
    reason: str,
) -> User:
    """
    Changes user role.
    - Standard Admin cannot be modified or downgraded.
    - Only Standard Admin can grant or remove Admin role.
    """
    new_role = new_role.lower().strip()
    if new_role not in _VALID_ROLES:
        raise UserError(f"Invalid role '{new_role}'. Must be one of: {sorted(_VALID_ROLES)}.")

    target = db.query(User).filter(User.id == target_user_id).first()
    if not target:
        raise UserError("User account not found.")

    if target.role == "standard_admin":
        raise UserError("The Standard Administrator role cannot be changed.")

    if new_role == "standard_admin":
        raise UserError("There can be exactly one Standard Administrator.")

    if not actor.is_standard_admin:
        raise UserError("Only the Standard Administrator can change user roles.")

    old_role = target.role
    target.role = new_role

    # Revoke sessions to force fresh login with new role
    revoke_all_user_sessions(db, cast(int, target.id), reason="ROLE_CHANGE")

    db.add(AuditLogEntry(
        user_id=actor.username,
        event_type="USER_ROLE_UPDATED",
        detail=json.dumps({
            "target_user": target.username,
            "old_role": old_role,
            "new_role": new_role,
            "changed_by": actor.username,
            "reason": reason,
        }),
    ))
    db.commit()
    db.refresh(target)
    return target
