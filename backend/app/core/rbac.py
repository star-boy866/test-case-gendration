"""
RBAC — Phase 9.

Three roles, mapped to the workflow's actual trust boundaries rather than
a generic admin/user split:

  - "tester"   — day-to-day work: upload documents, generate/edit/refine
                 scenarios. Cannot confirm Gatekeeper scope or export.
  - "approver" — everything a tester can do, PLUS confirming Gatekeeper
                 scope and running Excel/SharePoint/email export. This
                 maps directly onto the Master System Prompt's Gatekeeper
                 step being a human SIGN-OFF, not just a tester's own
                 self-confirmation — a second, higher-trust role approving
                 scope before generation runs, and approving the final
                 artifact before it leaves the system, is a meaningfully
                 stronger control than "whoever uploaded the file also
                 confirms and exports it."
  - "admin"    — everything an approver can do, plus user management.

Role checks are additive/hierarchical (admin > approver > tester), not a
flat per-endpoint allowlist, since that's both simpler to reason about and
matches how the roles were designed above.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.core.security import decode_access_token, TokenError
from app.db.session import get_db
from app.models.user import User

ROLE_HIERARCHY = {"tester": 0, "approver": 1, "admin": 2}


class CurrentUser:
    """Lightweight, DB-independent representation of the authenticated
    caller — deliberately NOT the SQLAlchemy User model itself, so route
    handlers and tests don't need a live DB session just to check `role`."""

    def __init__(self, username: str, role: str):
        self.username = username
        self.role = role

    def has_at_least(self, minimum_role: str) -> bool:
        return ROLE_HIERARCHY.get(self.role, -1) >= ROLE_HIERARCHY.get(minimum_role, 999)


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header (expected 'Bearer <token>').")
    return authorization[len("Bearer "):].strip()


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    token = _extract_bearer_token(authorization)
    try:
        payload = decode_access_token(token)
    except TokenError as e:
        raise HTTPException(status_code=401, detail=str(e))

    username = payload.get("sub")
    user = db.query(User).filter(User.username == username, User.is_active == True).first()  # noqa: E712
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists or has been deactivated.")

    # Role comes from the DB at request time, not just the token's claim —
    # if an admin demotes a user mid-day, already-issued tokens shouldn't
    # keep granting the old role until they expire.
    return CurrentUser(username=user.username, role=user.role)


def require_role(minimum_role: str):
    """FastAPI dependency factory: `Depends(require_role("approver"))`."""

    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not current_user.has_at_least(minimum_role):
            raise HTTPException(
                status_code=403,
                detail=f"This action requires '{minimum_role}' role or higher; "
                       f"you are '{current_user.role}'.",
            )
        return current_user

    return _dependency
