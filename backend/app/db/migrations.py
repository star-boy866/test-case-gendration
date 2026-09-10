"""
Lightweight schema migration helper for SQLite / PostgreSQL development.

Ensures that new columns added to existing tables (such as RBAC attributes on `users`)
are created safely on startup without data loss.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
import logging

logger = logging.getLogger(__name__)


def ensure_rbac_schema(engine: Engine) -> None:
    """Checks and adds missing columns to the `users` table if not already present."""
    with engine.connect() as conn:
        inspector = inspect(conn)
        existing_tables = inspector.get_table_names()

        if "users" in existing_tables:
            columns = {col["name"] for col in inspector.get_columns("users")}
            
            new_columns = [
                ("status", "VARCHAR DEFAULT 'ACTIVE' NOT NULL"),
                ("must_change_password", "BOOLEAN DEFAULT 0 NOT NULL"),
                ("mfa_enabled", "BOOLEAN DEFAULT 0 NOT NULL"),
                ("failed_login_attempts", "INTEGER DEFAULT 0 NOT NULL"),
                ("locked_until", "TIMESTAMP NULL"),
                ("last_login_at", "TIMESTAMP NULL"),
                ("last_password_change_at", "TIMESTAMP NULL"),
            ]
            
            for col_name, col_def in new_columns:
                if col_name not in columns:
                    try:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"))
                        conn.commit()
                        logger.info(f"Added column users.{col_name} via schema migration.")
                    except Exception as e:
                        logger.warning(f"Could not add column users.{col_name}: {e}")
