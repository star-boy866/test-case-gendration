"""
Local SQLite session management.

Per the Zero-Trust Database Policy: this database stores ONLY application
metadata (sessions, audit logs, cache pointers, confirmed CR/Report IDs).
It never stores production healthcare data and is never used to run
verification SQL — verification SQL is generated for the analyst to run
manually against the enterprise DB, never executed by this system.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

import logging
from app.core.config import settings

logger = logging.getLogger("session")


def _classify_postgres_error(exc: Exception) -> str:
    err_str = str(exc)
    err_lower = err_str.lower()
    if "tenant" in err_lower and "not found" in err_lower:
        return "TENANT_NOT_FOUND (verify project reference / AWS region in SUPABASE_DB_HOST or username format postgres.<project-ref>)"
    if "password authentication failed" in err_lower or "authentication failed" in err_lower:
        return "AUTHENTICATION_FAILED (verify database password or user credentials)"
    if "could not translate host name" in err_lower or "nodename nor servname provided" in err_lower or "11001" in err_lower or "name resolution" in err_lower:
        return "DNS_HOST_RESOLUTION_FAILURE (unable to resolve database hostname; verify host string)"
    if "timeout" in err_lower or "timed out" in err_lower:
        return "CONNECTION_TIMEOUT (database server did not respond within connect_timeout)"
    if "ssl" in err_lower:
        return "SSL_NEGOTIATION_FAILURE (verify sslmode=require and port)"
    if "connection refused" in err_lower or "111" in err_lower:
        return "CONNECTION_REFUSED (port may be incorrect or server not accepting connections)"
    clean_first_line = err_str.split("\n")[0][:120]
    return f"{type(exc).__name__}: {clean_first_line}"


def get_engine():
    db_url = settings.effective_database_url
    if db_url and "postgresql" in db_url:
        # Extract safe metadata for diagnostics
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        raw_host = parsed.hostname or getattr(settings, "SUPABASE_DB_HOST", "") or "remote_postgres_host"
        masked_host = (raw_host[:4] + "***" + raw_host[-4:]) if len(raw_host) > 8 else raw_host
        port = parsed.port or getattr(settings, "SUPABASE_DB_PORT", 5432)
        raw_db = (parsed.path or "").lstrip("/") or getattr(settings, "SUPABASE_DB_NAME", "postgres")
        masked_db = (raw_db[:3] + "***" + raw_db[-3:]) if len(raw_db) > 8 else raw_db
        driver_name = parsed.scheme or "postgresql"

        try:
            pg_engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=settings.DB_POOL_TIMEOUT,
                connect_args={"connect_timeout": 15},
            )
            with pg_engine.connect() as conn:
                pass
            logger.info(
                f"DATABASE_CONNECTION_DIAGNOSTIC: "
                f"database_backend=postgresql, "
                f"postgres_driver={driver_name}, "
                f"host={masked_host}, "
                f"port={port}, "
                f"database={masked_db}, "
                f"connection_status=SUCCESS, "
                f"environment={'production' if settings.is_production else 'development'}"
            )
            return pg_engine
        except Exception as exc:
            err_category = _classify_postgres_error(exc)
            logger.error(
                f"DATABASE_CONNECTION_DIAGNOSTIC: "
                f"database_backend=postgresql, "
                f"postgres_driver={driver_name}, "
                f"host={masked_host}, "
                f"port={port}, "
                f"database={masked_db}, "
                f"connection_status=FAILED, "
                f"environment={'production' if settings.is_production else 'development'}, "
                f"error_category={err_category}"
            )
            if settings.is_production:
                err_msg = (
                    f"PRODUCTION PERSISTENCE FAILURE: Cannot connect to PostgreSQL database "
                    f"(host={masked_host}, port={port}, reason={err_category}). "
                    f"Silent fallback to ephemeral SQLite is strictly prohibited in production."
                )
                logger.critical(err_msg)
                raise RuntimeError(err_msg) from exc
            logger.warning(
                f"PostgreSQL connection could not be established ({err_category}). "
                f"Falling back to local SQLite at {settings.SQLITE_DB_PATH}."
            )
            return create_engine(
                f"sqlite:///{settings.SQLITE_DB_PATH}",
                connect_args={"check_same_thread": False, "timeout": 30.0},
            )
    else:
        if settings.is_production:
            err_msg = (
                "PRODUCTION PERSISTENCE FAILURE: No PostgreSQL database configured in production "
                "(DATABASE_URL or SUPABASE_DB_* is required). "
                "Silent fallback to ephemeral SQLite is strictly prohibited in production."
            )
            logger.critical(err_msg)
            raise RuntimeError(err_msg)
        # Local Development / SQLite (hardened for multi-worker concurrency)
        return create_engine(
            f"sqlite:///{settings.SQLITE_DB_PATH}",
            connect_args={"check_same_thread": False, "timeout": 30.0},
        )


engine = get_engine()

# SQLite-specific connection listener: enable WAL mode and 30s busy timeout
# Only attaches if SQLite is being used; PostgreSQL connections are unaffected
if "sqlite" in str(engine.url):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
