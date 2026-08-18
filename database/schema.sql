-- Local application metadata/audit schema (SQLite).
-- This is a reference copy of the schema defined via SQLAlchemy in
-- backend/app/models/audit.py. It is created automatically on backend
-- startup; this file exists for review and for standing up the DB manually
-- if needed.
--
-- IMPORTANT: This database NEVER stores production healthcare data and is
-- NEVER queried against enterprise systems. It only tracks this
-- application's own sessions, audit trail, and cache pointers.

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    cr_id TEXT,
    cr_description TEXT,
    report_id TEXT,
    status TEXT DEFAULT 'ingestion',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_cr_id ON sessions(cr_id);
CREATE INDEX IF NOT EXISTS idx_sessions_report_id ON sessions(report_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT NOT NULL,
    session_id INTEGER,
    event_type TEXT NOT NULL,   -- UPLOAD, CONFIRM_GATEKEEPER, EXPORT, EMAIL_SENT, etc.
    detail TEXT,
    file_sha256 TEXT
);

CREATE TABLE IF NOT EXISTS cache_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL,
    source_file_hash TEXT NOT NULL,
    faiss_vector_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cache_report_id ON cache_metadata(report_id);
