"""
Zero-dependency RFC 6238 Time-Based One-Time Password (TOTP) implementation.

Complies with RFC 6238 and RFC 4226 (HOTP). Compatible with Google Authenticator,
Microsoft Authenticator, 1Password, Bitwarden, and Apple Keychain.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from typing import List, Tuple
import urllib.parse


def generate_totp_secret() -> str:
    """Generates a secure 160-bit (20-byte) Base32 secret string (RFC 4226 recommendation)."""
    random_bytes = secrets.token_bytes(20)
    return base64.b32encode(random_bytes).decode("utf-8").rstrip("=")


def generate_totp_uri(secret: str, username: str, issuer: str = "Healthcare-NL-TestGen") -> str:
    """Generates an otpauth:// URL suitable for QR codes and authenticator apps."""
    account = urllib.parse.quote(username)
    iss = urllib.parse.quote(issuer)
    return f"otpauth://totp/{iss}:{account}?secret={secret}&issuer={iss}&algorithm=SHA1&digits=6&period=30"


def get_totp_code(secret: str, timestamp: float | None = None) -> str:
    """Computes 6-digit TOTP code for the given timestamp (defaults to current time)."""
    if timestamp is None:
        timestamp = time.time()
    counter = int(timestamp // 30)

    # Pad secret with '=' to reach multiple of 8 if stripped
    padded_secret = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded_secret, casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()

    offset = digest[-1] & 0x0F
    code_int = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code_int:06d}"


def verify_totp_code(secret: str, code: str, drift_steps: int = 1) -> bool:
    """
    Validates a 6-digit TOTP code with time drift tolerance (+/- drift_steps of 30s).
    Uses constant-time comparison to protect against timing attacks.
    """
    cleaned_code = str(code).strip().replace(" ", "").replace("-", "")
    if len(cleaned_code) != 6 or not cleaned_code.isdigit():
        return False

    now = time.time()
    for step in range(-drift_steps, drift_steps + 1):
        candidate = get_totp_code(secret, timestamp=now + (step * 30))
        if hmac.compare_digest(candidate, cleaned_code):
            return True
    return False


def generate_backup_codes(count: int = 8) -> Tuple[List[str], List[str]]:
    """
    Generates single-use backup recovery codes.
    Returns: (plain_codes, hashed_codes)
    """
    plain_codes = []
    hashed_codes = []
    for _ in range(count):
        part1 = secrets.token_hex(2).upper()
        part2 = secrets.token_hex(2).upper()
        code = f"{part1}-{part2}"
        plain_codes.append(code)
        hashed_codes.append(hash_backup_code(code))
    return plain_codes, hashed_codes


def hash_backup_code(code: str) -> str:
    """Computes SHA-256 hash of normalized recovery code for secure database storage."""
    normalized = code.strip().upper().replace(" ", "").replace("-", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify_backup_code(code: str, hashed_codes: List[str]) -> Tuple[bool, List[str]]:
    """
    Verifies a backup code against list of hashed codes.
    If match found, returns (True, updated_hashed_codes_without_used_code).
    Otherwise returns (False, unchanged_hashed_codes).
    """
    input_hash = hash_backup_code(code)
    for i, h in enumerate(hashed_codes):
        if hmac.compare_digest(h, input_hash):
            remaining = [x for idx, x in enumerate(hashed_codes) if idx != i]
            return True, remaining
    return False, hashed_codes
