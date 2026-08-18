"""
User management — Phase 9.

This is the service layer api/auth.py's endpoints delegate to, following
the same api/ (thin route handlers) vs services/ (business logic)
separation used everywhere else in this codebase.

Note on bootstrap strategy: an earlier draft of this module also had a
`seed_default_admin()` that auto-created an admin account with a
hardcoded default password (from settings) at every app startup if the
users table was empty. That's removed — it directly conflicted with
api/auth.py's `POST /api/auth/register` bootstrap (self-service, only
while the table is empty, operator chooses real credentials immediately)
and is also a strictly weaker security pattern: shipping ANY default
password, even with a "change this immediately" warning, is worse than
requiring a real credential to be chosen at setup time with no insecure
window in between. Kept only one bootstrap path, not two.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User

_VALID_ROLES = {"tester", "approver", "admin"}
_MIN_PASSWORD_LENGTH = 12  # kept in sync with api/auth.py's RegisterRequest validator


class UserError(Exception):
    """Raised for invalid user operations (duplicate username, bad role, etc.)."""


def create_user(db: Session, *, username: str, password: str, role: str = "tester") -> User:
    if role not in _VALID_ROLES:
        raise UserError(f"Invalid role '{role}'. Must be one of: {sorted(_VALID_ROLES)}.")
    if not username or not username.strip():
        raise UserError("Username cannot be empty.")
    if not password or len(password) < _MIN_PASSWORD_LENGTH:
        raise UserError(f"Password must be at least {_MIN_PASSWORD_LENGTH} characters.")

    existing = db.query(User).filter(User.username == username).first()
    if existing is not None:
        raise UserError(f"Username '{username}' already exists.")

    user = User(username=username, hashed_password=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, username: str, password: str) -> User | None:
    """Returns the User on success, None on failure. Deliberately does not
    distinguish "user doesn't exist" from "wrong password" in its return
    value or in any message the caller surfaces — that distinction is a
    well-known username-enumeration side channel."""
    user = db.query(User).filter(User.username == username, User.is_active == True).first()  # noqa: E712
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
