"""
Authentication primitives — Phase 9.

Password hashing uses stdlib `hashlib.pbkdf2_hmac` rather than adding
`passlib`/`bcrypt` as a dependency — PBKDF2-HMAC-SHA256 is a NIST-approved
(SP 800-132) password hashing scheme, it's already in the Python standard
library, and it's exactly the kind of "free, open-source, zero extra
dependency" choice this project has favored throughout (see bm25.py,
embeddings.py from Phase 3). 200,000 iterations follows OWASP's current
minimum recommendation for PBKDF2-SHA256.

JWTs use `pyjwt` (already available; the original Phase 0 scaffold notes
mentioned `python-jose` as a placeholder, but that package isn't
maintained as actively — `pyjwt` is the more standard, equally-free
choice and is what's actually used here).

SECRET_KEY comes from settings (app/core/config.py) — the Phase 0 scaffold
already flagged `SECRET_KEY=dev-only-change-me` as something to replace in
production; that warning is more load-bearing now that it's actually used
to sign tokens.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time

import re
import secrets
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.core.config import settings

_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)
_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16


def validate_password_strength(password: str, username: str = "") -> tuple[bool, str]:
    """
    Enforces strong password policy:
    - Minimum 12 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character
    - Cannot match username
    """
    if not password or len(password) < 12:
        return False, "Password must be at least 12 characters long."
    if username and password.strip().lower() == username.strip().lower():
        return False, "Password cannot be identical to your username."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit (0-9)."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+[\]/\\]", password):
        return False, "Password must contain at least one special character (!@#$%^&* etc.)."
    return True, ""


def hash_password(plain_password: str) -> str:
    """Hashes password using Argon2id (SP 800-63B / OWASP recommended)."""
    return _ph.hash(plain_password)


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """
    Verifies password against stored hash.
    Supports Argon2id (default) and legacy PBKDF2-HMAC-SHA256 for smooth backward compatibility.
    """
    if not stored_hash or not plain_password:
        return False

    # Check for legacy PBKDF2 hash
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            algo, iterations_str, salt_hex, hash_hex = stored_hash.split("$")
            if algo != "pbkdf2_sha256":
                return False
            iterations = int(iterations_str)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(hash_hex)
            derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(derived, expected)
        except Exception:
            return False

    # Standard Argon2 verification
    try:
        return _ph.verify(stored_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_session_token() -> str:
    """Generates a high-entropy 256-bit URL-safe session token."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """Returns SHA-256 hash of a session/reset token for safe storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()



class TokenError(Exception):
    """Raised for any invalid/expired/malformed JWT."""


def create_access_token(*, subject: str, role: str, expires_seconds: int | None = None) -> str:
    now = int(time.time())
    exp_seconds = expires_seconds if expires_seconds is not None else settings.ACCESS_TOKEN_EXPIRES_SECONDS
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + exp_seconds,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise TokenError("Token has expired.") from e
    except jwt.InvalidTokenError as e:
        raise TokenError(f"Invalid token: {e}") from e
