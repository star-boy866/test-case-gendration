"""
Auth endpoints — Phase 9.

Bootstrap story: user creation normally requires 'admin' role (see
require_role below), which is a chicken-and-egg problem for the very first
account. Resolved the same way many self-hosted apps do it (Gitea,
Django's createsuperuser being the notable exception that needs a CLI
instead) — if the `users` table is completely empty, the next
registration is automatically granted 'admin' with no auth required.
Once at least one user exists, every subsequent registration requires an
authenticated admin (via POST /users instead). This means the window
where an unauthenticated request can create an admin account is exactly
"before anyone has ever registered" — normal deployment practice is to do
this once, immediately after first startup, before exposing the port
publicly.

Also exposes admin-only visibility into the audit trail
(GET /audit-log, GET /audit-log/verify) — before this phase, audit log
rows existed in the database but there was no way to actually view them
through the API at all, which undermines the Explainability requirement
in practice even though the rows were being written correctly.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.rbac import require_role, get_current_user, CurrentUser
from app.core.security import hash_password, create_access_token
from app.core.immutable_audit import verify_audit_chain
from app.services.user_service import authenticate_user
from app.db.session import get_db
from app.models.user import User
from app.models.audit import AuditLogEntry

router = APIRouter(prefix="/api/auth", tags=["auth"])

_VALID_ROLES = {"tester", "approver", "admin"}


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "tester"

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("username must be at least 3 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_minimum_length(cls, v: str) -> str:
        # 12 chars, not full NIST 800-63B entropy scoring — enterprise
        # deployments should layer on their own SSO/password policy in
        # front of this if stronger requirements are needed.
        if len(v) < 12:
            raise ValueError("password must be at least 12 characters")
        return v

    @field_validator("role")
    @classmethod
    def role_must_be_known(cls, v: str) -> str:
        if v not in _VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(_VALID_ROLES)}")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


@router.post("/register", response_model=UserResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Unauthenticated ONLY while the users table is empty (bootstrap). Once
    any user exists, this always refuses — subsequent accounts are created
    via the authenticated POST /users below instead.
    """
    if db.query(User).count() > 0:
        raise HTTPException(
            status_code=403,
            detail="Registration is closed — an account already exists. "
                   "An admin must create additional accounts via POST /api/auth/users.",
        )

    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role="admin",  # the bootstrap account is always admin, regardless of the requested role
        is_active=True,
    )
    db.add(user)
    db.flush()

    db.add(AuditLogEntry(
        user_id=payload.username,
        event_type="USER_CREATED",
        detail=f'{{"username": "{payload.username}", "role": "admin", "bootstrap": true}}',
    ))
    db.commit()
    db.refresh(user)

    return UserResponse(id=user.id, username=user.username, role=user.role, is_active=user.is_active)


@router.post("/users", response_model=UserResponse)
def create_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Admin-only account creation, once the bootstrap account exists."""
    if db.query(User).filter(User.username == payload.username).first() is not None:
        raise HTTPException(status_code=409, detail=f"Username '{payload.username}' already exists.")

    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.flush()

    db.add(AuditLogEntry(
        user_id=current_user.username,
        event_type="USER_CREATED",
        detail=f'{{"username": "{payload.username}", "role": "{payload.role}", "created_by": "{current_user.username}"}}',
    ))
    db.commit()
    db.refresh(user)

    return UserResponse(id=user.id, username=user.username, role=user.role, is_active=user.is_active)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    # Deliberately identical error for "no such user" and "wrong password" —
    # distinguishing them lets an attacker enumerate valid usernames.
    # authenticate_user() itself already preserves that property; this
    # endpoint just adds the audit trail on top.
    invalid_credentials = HTTPException(status_code=401, detail="Invalid username or password.")

    user = authenticate_user(db, username=payload.username, password=payload.password)
    if user is None:
        db.add(AuditLogEntry(user_id=payload.username, event_type="LOGIN_FAILED", detail=None))
        db.commit()
        raise invalid_credentials

    token = create_access_token(subject=user.username, role=user.role)
    db.add(AuditLogEntry(user_id=user.username, event_type="LOGIN_SUCCEEDED", detail=None))
    db.commit()

    return LoginResponse(access_token=token, role=user.role)


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == current_user.username).first()
    return UserResponse(id=user.id, username=user.username, role=user.role, is_active=user.is_active)


@router.get("/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("admin")),
):
    users = db.query(User).order_by(User.id.asc()).all()
    return [UserResponse(id=u.id, username=u.username, role=u.role, is_active=u.is_active) for u in users]


@router.get("/audit-log")
def get_audit_log(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """Admin-only. Most recent `limit` audit entries, newest first."""
    rows = (
        db.query(AuditLogEntry)
        .order_by(AuditLogEntry.id.desc())
        .limit(min(limit, 1000))
        .all()
    )
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "user_id": r.user_id,
            "session_id": r.session_id,
            "event_type": r.event_type,
            "detail": r.detail,
            "file_sha256": r.file_sha256,
            "chain_hash": r.chain_hash,
        }
        for r in rows
    ]


@router.get("/audit-log/verify")
def verify_audit_log(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("admin")),
):
    """
    Admin-only. Walks the entire hash chain (see core/immutable_audit.py)
    and reports whether it's intact, and exactly where it breaks if not —
    a concrete, checkable demonstration of the tamper-evidence guarantee,
    not just a claim in a docstring.
    """
    is_intact, problems = verify_audit_chain(db)
    return {"is_intact": is_intact, "problems": problems}
