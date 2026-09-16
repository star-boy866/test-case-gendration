"""
Role-Based Access Control (RBAC) ORM Models.

Entities:
- Role & Permission & RolePermission: Granular role-to-permission mapping
- AccessRequest & ApprovalHistory: Access requests, approvals, and immutable audit history
- UserSession: Active server-side sessions, device tracking, and revocation
- MfaConfiguration: TOTP secrets (AES-encrypted) and hashed backup codes
- PasswordResetToken: Cryptographically hashed single-use reset tokens
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, Table
)
from sqlalchemy.orm import relationship, Mapped, mapped_column, backref

from app.db.session import Base

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)  # standard_admin, admin, tester, pending
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_system_role: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    permissions = relationship("Permission", secondary=role_permissions, backref="roles")


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)  # e.g. test:read, user:manage
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    module: Mapped[str] = mapped_column(String, nullable=False)  # test, user, approval, audit, session
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_role: Mapped[str] = mapped_column(String, nullable=False)  # tester | admin
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING", index=True)  # PENDING | APPROVED | REJECTED | CANCELLED
    request_reason: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", foreign_keys=[user_id], backref="access_requests")
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class ApprovalHistory(Base):
    __tablename__ = "approval_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("access_requests.id", ondelete="SET NULL"), nullable=True)
    target_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)  # REQUESTED | APPROVED | REJECTED | CANCELLED | ROLE_CHANGED | STATUS_CHANGED
    previous_role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    new_role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    previous_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    target_user = relationship("User", foreign_keys=[target_user_id])
    actor = relationship("User", foreign_keys=[actor_id])


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)  # Secure random 256-bit token
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    device_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_authenticated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # LOGOUT | LOGOUT_ALL | SUSPENDED | IDLE_TIMEOUT | PASSWORD_RESET

    user = relationship("User", backref="sessions")


class MfaConfiguration(Base):
    __tablename__ = "mfa_configurations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # AES-256-GCM encrypted TOTP base32 secret
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    backup_codes_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of hashed recovery codes
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user = relationship("User", backref="mfa_config", uselist=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User")


class TestCaseAssignment(Base):
    """
    Secure association mapping an authoritative Cognos Test Case file / run
    to a specific authorized Tester.
    Enforces IDOR defense and role-scoped access control.
    """
    __tablename__ = "test_case_assignments"
    __test__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)  # Secure random UUID token
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("cognos_generation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String, default="ASSIGNED", nullable=False)  # ASSIGNED, COMPLETED, REVOKED
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    run = relationship("CognosGenerationRun", backref=backref("assignments", cascade="all, delete-orphan", passive_deletes=True))
    user = relationship("User", foreign_keys=[user_id], backref="assigned_test_cases")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])
