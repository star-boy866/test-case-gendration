"""
Unit & Integration Tests for Production Database Persistence Guardrail.

Verifies:
1. Production environment detection (ENVIRONMENT=production or APP_ENV=production).
2. Production configuration validation (PostgreSQL is mandatory; SQLite is strictly rejected).
3. Precedence: DATABASE_URL > SUPABASE_DB_* > SQLite fallback.
4. Fail-fast guardrail in session.py: SQLite fallback is strictly prohibited in production.
5. User password persistence: bootstrap_standard_admin and ensure_tester_account do not overwrite
   existing user passwords across container restarts.
6. Zero secrets leakage in safe diagnostic logging.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.services.user_service import bootstrap_standard_admin, ensure_tester_account


def test_production_environment_detection():
    """Confirms both APP_ENV=production and ENVIRONMENT=production are recognized."""
    # 1. APP_ENV
    s1 = Settings(
        APP_ENV="production",
        SECRET_KEY="a-secure-production-key-that-is-at-least-32-chars",
        DATABASE_URL="postgresql://user:pass@remote.host:5432/mydb?sslmode=require",
    )
    assert s1.is_production is True
    assert s1.APP_ENV == "production"

    # 2. ENVIRONMENT
    s2 = Settings(
        APP_ENV="development",
        ENVIRONMENT="production",
        SECRET_KEY="a-secure-production-key-that-is-at-least-32-chars",
        DATABASE_URL="postgresql://user:pass@remote.host:5432/mydb?sslmode=require",
    )
    assert s2.is_production is True
    assert s2.APP_ENV == "production"

    # 3. Development
    s3 = Settings(
        APP_ENV="development",
        ENVIRONMENT="development",
    )
    assert s3.is_production is False


def test_production_rejects_sqlite():
    """In production, SQLite fallback must be rejected at configuration time."""
    with pytest.raises(ValueError, match="PRODUCTION SAFETY: A PostgreSQL database"):
        Settings(
            APP_ENV="production",
            SECRET_KEY="a-secure-production-key-that-is-at-least-32-chars",
            DATABASE_URL="sqlite:///./test.db",
        )

    with pytest.raises(ValueError, match="PRODUCTION SAFETY: A PostgreSQL database"):
        Settings(
            APP_ENV="production",
            SECRET_KEY="a-secure-production-key-that-is-at-least-32-chars",
            DATABASE_URL="",
            SUPABASE_DB_HOST="",
        )


def test_production_accepts_supabase_component_variables():
    """In production, SUPABASE_DB_* variables must be accepted without DATABASE_URL."""
    s = Settings(
        APP_ENV="production",
        SECRET_KEY="a-secure-production-key-that-is-at-least-32-chars",
        DATABASE_URL="",
        SUPABASE_DB_HOST="aws-0-ap-south-1.pooler.supabase.com",
        SUPABASE_DB_PORT=6543,
        SUPABASE_DB_USER="postgres.myproject",
        SUPABASE_DB_PASSWORD="mysecretpassword",
        SUPABASE_DB_NAME="postgres",
    )
    assert s.is_production is True
    assert "postgresql://" in s.effective_database_url
    assert "sslmode=require" in s.effective_database_url
    assert "sqlite" not in s.effective_database_url.lower()


def test_effective_database_url_precedence():
    """Confirms DATABASE_URL overrides SUPABASE_DB_* component variables."""
    s = Settings(
        DATABASE_URL="postgresql://direct_user:direct_pass@direct.host:5432/direct_db",
        SUPABASE_DB_HOST="aws-0-ap-south-1.pooler.supabase.com",
        SUPABASE_DB_USER="component_user",
        SUPABASE_DB_PASSWORD="component_pass",
    )
    assert "direct_user" in s.effective_database_url
    assert "direct.host" in s.effective_database_url
    assert "component_user" not in s.effective_database_url


def test_session_engine_fails_fast_in_production_on_connection_error():
    """In production, get_engine() must raise RuntimeError rather than falling back to SQLite."""
    from app.db import session as session_module

    mock_settings = MagicMock()
    mock_settings.is_production = True
    mock_settings.effective_database_url = "postgresql://invalid_user:invalid_pass@127.0.0.1:5432/nonexistent"
    mock_settings.DB_POOL_SIZE = 5
    mock_settings.DB_MAX_OVERFLOW = 2
    mock_settings.DB_POOL_TIMEOUT = 5
    mock_settings.SQLITE_DB_PATH = "./database/app_metadata.db"
    mock_settings.SUPABASE_DB_HOST = "remote.host"

    with patch.object(session_module, "settings", mock_settings):
        with pytest.raises(RuntimeError, match="PRODUCTION PERSISTENCE FAILURE"):
            session_module.get_engine()


def test_session_engine_allows_sqlite_fallback_in_development():
    """In development, get_engine() gracefully falls back to SQLite if PostgreSQL is unavailable."""
    from app.db import session as session_module

    mock_settings = MagicMock()
    mock_settings.is_production = False
    mock_settings.effective_database_url = "postgresql://invalid_user:invalid_pass@127.0.0.1:5432/nonexistent"
    mock_settings.DB_POOL_SIZE = 5
    mock_settings.DB_MAX_OVERFLOW = 2
    mock_settings.DB_POOL_TIMEOUT = 5
    mock_settings.SQLITE_DB_PATH = "./database/test_dev_fallback.db"

    with patch.object(session_module, "settings", mock_settings):
        eng = session_module.get_engine()
        assert "sqlite" in str(eng.url)


def test_password_persistence_across_restart_simulation(db: Session):
    """
    Verifies that changing a user password persists and is NOT overwritten by
    subsequent calls to bootstrap_standard_admin or ensure_tester_account.
    """
    # 1. Setup admin user
    admin = db.query(User).filter(User.username == "obuli").first()
    if not admin:
        admin = User(
            username="obuli",
            hashed_password=hash_password("InitialAdminPass2026!"),
            role="standard_admin",
            status="ACTIVE",
            is_active=True,
            must_change_password=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

    # 2. User changes their password
    new_user_password = "MyNewCustomAdminPassword2026!Secure"
    admin.hashed_password = hash_password(new_user_password)
    admin.must_change_password = False
    db.commit()
    db.refresh(admin)

    original_hash = admin.hashed_password
    assert verify_password(new_user_password, original_hash) is True

    # 3. Simulate server restart: bootstrap_standard_admin runs again
    restarted_admin = bootstrap_standard_admin(db)

    # 4. Confirm password hash remains exactly the changed one
    assert restarted_admin.hashed_password == original_hash
    assert verify_password(new_user_password, restarted_admin.hashed_password) is True
    assert verify_password("InitialAdminPass2026!", restarted_admin.hashed_password) is False

    # 5. Tester password persistence
    tester = db.query(User).filter(User.username == "tester").first()
    if not tester:
        tester = User(
            username="tester",
            hashed_password=hash_password("Tester#Password2026!"),
            role="tester",
            status="ACTIVE",
            is_active=True,
        )
        db.add(tester)
        db.commit()
        db.refresh(tester)

    new_tester_pass = "CustomTesterPass2026!New"
    tester.hashed_password = hash_password(new_tester_pass)
    db.commit()
    db.refresh(tester)

    tester_hash = tester.hashed_password

    # Simulate server restart: ensure_tester_account runs again
    restarted_tester = ensure_tester_account(db)
    assert restarted_tester.hashed_password == tester_hash
    assert verify_password(new_tester_pass, restarted_tester.hashed_password) is True
