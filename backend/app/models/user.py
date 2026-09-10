"""
User model — Phase 9.

Stores only what RBAC needs: username, PBKDF2 password hash (see
app/core/security.py — never a plaintext password, never a reversible
encryption of one), role, and active/inactive status. Deactivating a user
(is_active=False) is preferred over deleting them, so historical
audit/session/refinement rows that reference their username remain
meaningful — a deleted user would leave "who did this?" unanswerable,
which directly undermines the Explainability requirement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="tester")  # standard_admin | admin | tester | pending
    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE", index=True)  # ACTIVE | PENDING | SUSPENDED | REVOKED
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_password_change_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

