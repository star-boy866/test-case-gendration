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

import jwt

from app.core.config import settings

_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16


def hash_password(plain_password: str) -> str:
    """Returns 'pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>'."""
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Constant-time comparison — never short-circuit on the derived hash itself."""
    try:
        algo, iterations_str, salt_hex, hash_hex = stored_hash.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False

    iterations = int(iterations_str)
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(hash_hex)
    derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(derived, expected)


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
