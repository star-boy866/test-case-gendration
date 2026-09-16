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


def ensure_governance_schema(engine: Engine) -> None:
    """Checks and creates baseline roles and governance permissions if not present."""
    with engine.connect() as conn:
        insp = inspect(conn)
        existing_tables = set(insp.get_table_names())

        if "roles" in existing_tables:
            try:
                # Seed system roles
                for role_name, desc in [
                    ("standard_admin", "Primary bootstrap and security administrator"),
                    ("admin", "Governance administrator with full Database Explorer & audit access"),
                    ("tester", "SIT/QA test case engineer"),
                ]:
                    check = conn.execute(text("SELECT id FROM roles WHERE name = :name"), {"name": role_name}).first()
                    if not check:
                        conn.execute(
                            text("INSERT INTO roles (name, description, is_system_role) VALUES (:name, :desc, :is_sys)"),
                            {"name": role_name, "desc": desc, "is_sys": True}
                        )
                conn.commit()
            except Exception as e:
                logger.warning(f"Could not seed default roles: {e}")

        if "permissions" in existing_tables:
            try:
                # Seed governance permissions
                for code, name, desc, mod in [
                    ("database:read", "Database Explorer Read", "Read-only access to application database tables", "governance"),
                    ("audit:read", "Audit Trail Read", "Access to system-wide audit events", "governance"),
                    ("learning:view", "Scenario Learning View", "Access to scenario evaluation dataset", "governance"),
                ]:
                    check = conn.execute(text("SELECT id FROM permissions WHERE code = :code"), {"code": code}).first()
                    if not check:
                        conn.execute(
                            text("INSERT INTO permissions (code, name, description, module) VALUES (:code, :name, :desc, :mod)"),
                            {"code": code, "name": name, "desc": desc, "mod": mod}
                        )
                conn.commit()
            except Exception as e:
                logger.warning(f"Could not seed default permissions: {e}")

