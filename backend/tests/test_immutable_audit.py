"""
Tests for app.core.immutable_audit.

register_immutability_guards()/_before_update/_before_delete need a live
SQLAlchemy ORM session to test the actual UPDATE/DELETE-blocking behavior
end-to-end (consistent with every other DB-dependent module in this
project). What's tested here for real, with no DB needed at all, is the
hash-chain computation itself: _compute_hash()/_row_payload() are pure
functions of an object's attributes plus a previous-hash string, so a
lightweight stand-in object with the right attributes exercises the exact
same code path as a real AuditLogEntry would.
"""

from app.core.immutable_audit import _compute_hash, _GENESIS_HASH


class _FakeEntry:
    def __init__(self, timestamp, user_id, session_id, event_type, detail, file_sha256):
        self.timestamp = timestamp
        self.user_id = user_id
        self.session_id = session_id
        self.event_type = event_type
        self.detail = detail
        self.file_sha256 = file_sha256


def test_hash_is_deterministic_for_same_input():
    entry = _FakeEntry("2026-01-01T00:00:00", "alice", 1, "LOGIN_SUCCEEDED", None, None)
    h1 = _compute_hash(entry, _GENESIS_HASH)
    h2 = _compute_hash(entry, _GENESIS_HASH)
    assert h1 == h2


def test_hash_depends_on_previous_hash_chain_linkage():
    entry = _FakeEntry("2026-01-01T00:05:00", "alice", 1, "UPLOAD", "some detail", "abc123")
    h_a = _compute_hash(entry, "hash-from-row-1")
    h_b = _compute_hash(entry, "a-completely-different-previous-hash")
    assert h_a != h_b


def test_tampering_with_any_field_changes_the_hash():
    original = _FakeEntry("2026-01-01T00:05:00", "alice", 1, "UPLOAD", "original detail", "abc123")
    tampered = _FakeEntry("2026-01-01T00:05:00", "alice", 1, "UPLOAD", "TAMPERED detail", "abc123")

    h_original = _compute_hash(original, _GENESIS_HASH)
    h_tampered = _compute_hash(tampered, _GENESIS_HASH)
    assert h_original != h_tampered


def test_tampering_with_user_id_changes_the_hash():
    original = _FakeEntry("2026-01-01T00:05:00", "alice", 1, "UPLOAD", "detail", "abc123")
    tampered = _FakeEntry("2026-01-01T00:05:00", "mallory", 1, "UPLOAD", "detail", "abc123")

    assert _compute_hash(original, _GENESIS_HASH) != _compute_hash(tampered, _GENESIS_HASH)


def test_genesis_hash_is_used_for_the_first_row():
    entry = _FakeEntry("2026-01-01T00:00:00", "alice", None, "LOGIN_SUCCEEDED", None, None)
    h_with_genesis = _compute_hash(entry, _GENESIS_HASH)
    h_with_something_else = _compute_hash(entry, "not-genesis")
    assert h_with_genesis != h_with_something_else


def test_hash_output_is_a_valid_sha256_hex_digest():
    entry = _FakeEntry("2026-01-01T00:00:00", "alice", None, "LOGIN_SUCCEEDED", None, None)
    h = _compute_hash(entry, _GENESIS_HASH)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
