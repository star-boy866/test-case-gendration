"""
Database initialization and schema upgrade entry point.

Executed sequentially during pre-flight container startup before multi-worker
processes are forked, ensuring idempotent schema creation and zero DDL race conditions.
"""

from __future__ import annotations

import logging
import sys

from app.db.session import Base, engine, SessionLocal
from app import models  # noqa: F401  ensures all ORM tables register on Base.metadata
from app.db.migrations import ensure_rbac_schema, ensure_governance_schema
from app.services.user_service import bootstrap_standard_admin, ensure_tester_account

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("init_db")


def init_db() -> None:
    """
    Initializes database schema and bootstraps baseline administrative accounts.
    Idempotent: safe to run multiple times against existing databases without data loss.
    """
    from app.core.config import settings
    url = engine.url
    is_postgres = "postgresql" in str(url.drivername).lower() or "postgres" in str(url.drivername).lower()
    masked_host = "local_embedded"
    if is_postgres:
        raw_h = url.host or ""
        masked_host = raw_h[:4] + "***" + raw_h[-4:] if len(raw_h) > 8 else "masked"
    db_name = str(url.database or "app_metadata.db")
    masked_db = (db_name[:3] + "***" + db_name[-3:]) if len(db_name) > 8 else db_name

    logger.info(
        f"DATABASE_RUNTIME_DIAGNOSTIC: "
        f"environment={'production' if settings.is_production else 'development'}, "
        f"database_backend={'postgresql' if is_postgres else 'sqlite'}, "
        f"database_driver={url.drivername}, "
        f"host={masked_host}, "
        f"database_name={masked_db}, "
        f"persistence_mode={'external_persistent' if is_postgres else 'local_ephemeral'}, "
        f"sqlalchemy_url_scheme={url.drivername}"
    )

    if settings.is_production and not is_postgres:
        raise RuntimeError(
            "PRODUCTION PERSISTENCE FAILURE: init_db refusing to run against local SQLite database in production."
        )

    logger.info("Starting database schema initialization...")

    # 1. Create tables if they do not already exist (never drops or recreates existing tables)
    Base.metadata.create_all(bind=engine)
    logger.info("Base.metadata.create_all completed successfully.")

    # 2. Run lightweight column migrations and governance schema setup
    ensure_rbac_schema(engine)
    ensure_governance_schema(engine)
    logger.info("ensure_rbac_schema and ensure_governance_schema completed successfully.")

    # 3. Bootstrap standard admin and tester accounts (idempotent, checks for existing rows)
    db = SessionLocal()
    try:
        bootstrap_standard_admin(db)
        ensure_tester_account(db)
        logger.info("Standard admin and tester accounts verified/bootstrapped.")
    finally:
        db.close()

    logger.info("Database initialization completed successfully.")


if __name__ == "__main__":
    try:
        init_db()
    except Exception as exc:
        logger.error(f"Database initialization failed: {exc}", exc_info=True)
        sys.exit(1)
