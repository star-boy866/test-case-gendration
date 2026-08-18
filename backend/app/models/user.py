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

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="tester")  # tester | approver | admin
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
