"""
Tests for app.core.rbac.

get_current_user()/require_role() as FastAPI dependencies need a live DB
session and an actual request context to test end-to-end (consistent with
every other FastAPI-dependency-based auth check in this project). What's
tested here for real is CurrentUser.has_at_least() — the actual role-
hierarchy comparison logic, and the one piece of this module with no
FastAPI/DB dependency at all.
"""

from app.core.rbac import CurrentUser, ROLE_HIERARCHY


def test_admin_has_at_least_every_role():
    user = CurrentUser(username="alice", role="admin")
    assert user.has_at_least("tester") is True
    assert user.has_at_least("approver") is True
    assert user.has_at_least("admin") is True


def test_approver_has_at_least_tester_and_approver_not_admin():
    user = CurrentUser(username="bob", role="approver")
    assert user.has_at_least("tester") is True
    assert user.has_at_least("approver") is True
    assert user.has_at_least("admin") is False


def test_tester_has_at_least_tester_only():
    user = CurrentUser(username="carol", role="tester")
    assert user.has_at_least("tester") is True
    assert user.has_at_least("approver") is False
    assert user.has_at_least("admin") is False


def test_unknown_role_is_never_sufficient():
    # Defensive case: a role string that isn't in ROLE_HIERARCHY at all
    # (e.g. data corruption, or a future role removed from the app but
    # still present on an old User row) must never grant access.
    user = CurrentUser(username="mallory", role="totally-made-up-role")
    assert user.has_at_least("tester") is False


def test_role_hierarchy_ordering_is_as_documented():
    assert ROLE_HIERARCHY["tester"] < ROLE_HIERARCHY["approver"] < ROLE_HIERARCHY["admin"]
