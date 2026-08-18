"""
Encryption at rest — Phase 9.

Per the Master System Prompt's Security requirement ("AES-256 encryption
at rest and TLS 1.3 in transit"):

- AES-256-GCM (via the `cryptography` library's AESGCM primitive) for
  encrypting specific sensitive fields before they're written to SQLite —
  applied to ExportRecord.email_sent_to (real recipient email addresses)
  in export_service.py. GCM is an authenticated mode: tampering with
  ciphertext is detected on decrypt, not just silently accepted.
- TLS 1.3 in transit is DELIBERATELY NOT implemented in application code
  here — TLS termination is normally handled by the ASGI server or a
  reverse proxy (uvicorn --ssl-keyfile/--ssl-certfile, or nginx/Caddy in
  front of it), not hand-rolled in Python. Pretending to implement TLS at
  the application layer would be both unnecessary (the server/proxy layer
  already solves this correctly) and a worse security posture than using
  battle-tested infrastructure. See docs/PHASES.md Phase 9 notes for the
  recommended production deployment shape.

ENCRYPTION_KEY (settings) is a base64-encoded 32-byte key. Deliberately
has NO usable default — encrypt_field()/decrypt_field() raise
EncryptionNotConfiguredError rather than silently encrypting real PII with
a placeholder key that ships in version control (the same reasoning
already applied to SECRET_KEY's "dev-only-change-me" placeholder, taken
one step further: that one at least mostly-works insecurely, this one
refuses outright).
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_NONCE_BYTES = 12  # standard for AES-GCM


class EncryptionNotConfiguredError(Exception):
    """Raised when ENCRYPTION_KEY isn't set to a valid base64-encoded 32-byte key."""


class DecryptionError(Exception):
    """Raised when ciphertext fails authentication (wrong key, or tampered data)."""


def _load_key() -> bytes:
    raw = settings.ENCRYPTION_KEY
    if not raw:
        raise EncryptionNotConfiguredError(
            "ENCRYPTION_KEY is not set. Generate one with: "
            "python -c \"import os, base64; print(base64.b64encode(os.urandom(32)).decode())\" "
            "and set it in .env — refusing to encrypt sensitive data with no key "
            "rather than silently using an insecure default."
        )
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as e:
        raise EncryptionNotConfiguredError(f"ENCRYPTION_KEY is not valid base64: {e}") from e
    if len(key) != 32:
        raise EncryptionNotConfiguredError(
            f"ENCRYPTION_KEY must decode to exactly 32 bytes for AES-256 (got {len(key)})."
        )
    return key


def generate_key() -> str:
    """Convenience helper for ops/setup scripts — not used by the app itself at runtime."""
    return base64.b64encode(os.urandom(32)).decode("ascii")


def encrypt_field(plaintext: str) -> str:
    """Returns a single base64-encoded string containing nonce || ciphertext,
    safe to store directly in a String/Text column."""
    key = _load_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), associated_data=None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_field(token: str) -> str:
    key = _load_key()
    aesgcm = AESGCM(key)
    try:
        raw = base64.b64decode(token, validate=True)
        nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
    except Exception as e:
        raise DecryptionError(
            "Could not decrypt field — wrong key, corrupted data, or tampered ciphertext."
        ) from e
    return plaintext.decode("utf-8")
