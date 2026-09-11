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

from app.core.config import settings


def get_engine():
    if settings.DATABASE_URL:
        # Production / PostgreSQL
        return create_engine(
            settings.DATABASE_URL,
            poolclass=QueuePool,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
        )
    else:
        # Local Development / SQLite (hardened for multi-worker concurrency)
        return create_engine(
            f"sqlite:///{settings.SQLITE_DB_PATH}",
            connect_args={"check_same_thread": False, "timeout": 30.0},
        )


engine = get_engine()

# SQLite-specific connection listener: enable WAL mode and 30s busy timeout
# Only attaches if SQLite is being used; PostgreSQL connections are unaffected
if not settings.DATABASE_URL or "sqlite" in str(engine.url):
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
