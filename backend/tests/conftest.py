"""
Pytest Test Fixtures and Database Isolation.

Ensures that automated tests run in a completely isolated SQLite test database,
preventing any mutation, credential wiping, or data loss in the live application
database (app_metadata.db).
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import Base, get_db
from app.db.migrations import ensure_rbac_schema
from app.services.user_service import bootstrap_standard_admin
from app.main import app

TEST_DB_PATH = BACKEND_DIR / "database" / "test_isolated_runner.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH.as_posix()}"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initializes isolated test database schema and bootstraps clean test data."""
    orig_initial_admin_pass = settings.INITIAL_ADMIN_PASSWORD
    settings.INITIAL_ADMIN_PASSWORD = ""

    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except Exception:
            pass

    Base.metadata.create_all(bind=test_engine)
    ensure_rbac_schema(test_engine)

    init_session = TestSessionLocal()
    try:
        bootstrap_standard_admin(init_session)
    finally:
        init_session.close()

    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    yield

    app.dependency_overrides.clear()
    settings.INITIAL_ADMIN_PASSWORD = orig_initial_admin_pass
    test_engine.dispose()
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except Exception:
            pass


@pytest.fixture
def db():
    """Provides an isolated database session for individual test cases."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """Provides a TestClient wired to the isolated test database."""
    with TestClient(app) as c:
        yield c
