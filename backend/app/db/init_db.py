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
from app.db.migrations import ensure_rbac_schema
from app.services.user_service import bootstrap_standard_admin, ensure_tester_account

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("init_db")


def init_db() -> None:
    """
    Initializes database schema and bootstraps baseline administrative accounts.
    Idempotent: safe to run multiple times against existing databases without data loss.
    """
    logger.info("Starting database schema initialization...")

    # 1. Create tables if they do not already exist (never drops or recreates existing tables)
    Base.metadata.create_all(bind=engine)
    logger.info("Base.metadata.create_all completed successfully.")

    # 2. Run lightweight column migrations (e.g. RBAC attributes)
    ensure_rbac_schema(engine)
    logger.info("ensure_rbac_schema completed successfully.")

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
