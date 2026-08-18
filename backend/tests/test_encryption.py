"""
Tests for app.core.encryption — AES-256-GCM field encryption via the
`cryptography` library, genuinely installed in the sandbox this was built
in, so these were run for real. Covers the actual authenticated-encryption
guarantee (tamper detection), not just a plain round-trip.
"""

import base64
import os

import pytest

from app.core.encryption import (
    encrypt_field,
    decrypt_field,
    generate_key,
    EncryptionNotConfiguredError,
    DecryptionError,
)


@pytest.fixture()
def configured_key(monkeypatch):
    from app.core.config import settings
    key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", key)
    return key


def test_encrypt_decrypt_round_trip(configured_key):
    ct = encrypt_field("alice@example.com")
    assert ct != "alice@example.com"
    assert decrypt_field(ct) == "alice@example.com"


def test_tampered_ciphertext_is_detected(configured_key):
    ct = encrypt_field("alice@example.com")
    tampered = ct[:-4] + "AAAA"
    with pytest.raises(DecryptionError):
        decrypt_field(tampered)


def test_wrong_key_fails_to_decrypt(configured_key, monkeypatch):
    from app.core.config import settings

    ct = encrypt_field("alice@example.com")
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", generate_key())
    with pytest.raises(DecryptionError):
        decrypt_field(ct)


def test_empty_key_refuses_cleanly(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENCRYPTION_KEY", "")
    with pytest.raises(EncryptionNotConfiguredError):
        encrypt_field("test")


def test_wrong_key_length_rejected(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENCRYPTION_KEY", base64.b64encode(os.urandom(16)).decode())
    with pytest.raises(EncryptionNotConfiguredError):
        encrypt_field("test")


def test_invalid_base64_rejected(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENCRYPTION_KEY", "not valid base64!!!")
    with pytest.raises(EncryptionNotConfiguredError):
        encrypt_field("test")
