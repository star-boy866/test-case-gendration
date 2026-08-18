"""
Tests for app.core.security — password hashing (stdlib PBKDF2-HMAC-SHA256)
and JWT creation/verification (pyjwt). Both dependencies are genuinely
installed in the sandbox this was built in, so these were run for real,
not just syntax-checked — see docs/PHASES.md Phase 9 notes.
"""

import pytest

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    TokenError,
)


def test_password_hash_verify_round_trip():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong password", h) is False


def test_password_hashing_is_salted():
    h1 = hash_password("same password")
    h2 = hash_password("same password")
    assert h1 != h2  # different random salts each time


def test_verify_password_rejects_malformed_stored_hash():
    assert verify_password("anything", "not-a-valid-hash-format") is False


def test_jwt_create_and_decode_round_trip():
    token = create_access_token(subject="alice", role="tester")
    decoded = decode_access_token(token)
    assert decoded["sub"] == "alice"
    assert decoded["role"] == "tester"


def test_expired_jwt_is_rejected():
    token = create_access_token(subject="bob", role="admin", expires_seconds=-10)
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_tampered_jwt_is_rejected():
    token = create_access_token(subject="alice", role="tester")
    tampered = token[:-5] + "AAAAA"
    with pytest.raises(TokenError):
        decode_access_token(tampered)


def test_garbage_token_is_rejected():
    with pytest.raises(TokenError):
        decode_access_token("not.a.jwt")
