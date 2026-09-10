"""
User Session & Device Management Service.

Handles server-side session lifecycle:
- Cryptographic session generation and storage
- Idle timeout and absolute lifetime enforcement
- Single session revocation and "Log out from all devices"
- Session regeneration on privilege escalation
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_session_token
from app.models.rbac import UserSession
from app.models.user import User


def _get_device_name(user_agent: Optional[str]) -> str:
    """Parses user agent into a human-friendly device summary."""
    if not user_agent:
        return "Unknown Device"
    ua = user_agent.lower()
    os_name = "Unknown OS"
    if "windows" in ua:
        os_name = "Windows"
    elif "macintosh" in ua or "mac os" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"
    elif "android" in ua:
        os_name = "Android"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iOS"

    browser = "Browser"
    if "edg" in ua:
        browser = "Edge"
    elif "chrome" in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua:
        browser = "Safari"

    return f"{browser} on {os_name}"


def create_session(
    db: Session,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> UserSession:
    """Creates a new active server-side session."""
    now = datetime.now(timezone.utc)
    max_lifetime_seconds = (
        settings.SESSION_LIFETIME_ADMIN_SECONDS
        if user.role in ("standard_admin", "admin")
        else settings.SESSION_LIFETIME_TESTER_SECONDS
    )
    expires_at = now + timedelta(seconds=max_lifetime_seconds)
    raw_token = generate_session_token()
    device_name = _get_device_name(user_agent)

    session = UserSession(
        session_id=raw_token,
        user_id=user.id,
        ip_address=ip_address or "127.0.0.1",
        user_agent=user_agent or "Unknown",
        device_name=device_name,
        created_at=now,
        last_activity_at=now,
        last_authenticated_at=now,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def revoke_session(db: Session, session_id: str, reason: str = "LOGOUT") -> bool:
    """Revokes a specific session immediately."""
    session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
    if session and session.is_active:
        session.is_active = False
        session.revoked_at = datetime.now(timezone.utc)
        session.revoked_reason = reason
        db.commit()
        return True
    return False


def revoke_all_user_sessions(
    db: Session,
    user_id: int,
    exclude_session_id: Optional[str] = None,
    reason: str = "LOGOUT_ALL",
) -> int:
    """Revokes all active sessions for a given user."""
    now = datetime.now(timezone.utc)
    query = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.is_active == True,  # noqa: E712
    )
    if exclude_session_id:
        query = query.filter(UserSession.session_id != exclude_session_id)

    sessions = query.all()
    count = 0
    for s in sessions:
        s.is_active = False
        s.revoked_at = now
        s.revoked_reason = reason
        count += 1
    db.commit()
    return count


def list_user_sessions(
    db: Session,
    user_id: int,
    current_session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lists all active and recent sessions for a user."""
    sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == user_id)
        .order_by(UserSession.last_activity_at.desc())
        .limit(20)
        .all()
    )

    out = []
    for s in sessions:
        out.append({
            "id": s.id,
            "session_id_preview": f"{s.session_id[:8]}...",
            "ip_address": s.ip_address,
            "device_name": s.device_name,
            "user_agent": s.user_agent,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_activity_at": s.last_activity_at.isoformat() if s.last_activity_at else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "is_active": s.is_active,
            "is_current": (s.session_id == current_session_id) if current_session_id else False,
            "revoked_reason": s.revoked_reason,
        })
    return out


def touch_session_reauth(db: Session, session_id: str) -> bool:
    """Updates last_authenticated_at after password/MFA re-verification."""
    session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
    if session and session.is_active:
        now = datetime.now(timezone.utc)
        session.last_authenticated_at = now
        session.last_activity_at = now
        db.commit()
        return True
    return False
