from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import Base, engine
from app import models  # noqa: F401  ensures all ORM tables register before create_all
from app.core.immutable_audit import register_immutability_guards
from app.api import health, ingestion, gatekeeper, generation, export, refinement, auth, cognos_api, jobs

# Create SQLite tables on startup (Phase 0/1: simple create_all; Phase 9 adds
# proper migrations via Alembic).
Base.metadata.create_all(bind=engine)

# Phase 9: must run before any AuditLogEntry is ever inserted/updated/deleted
# — this is what actually activates the ORM-level immutability guards and
# hash-chaining described in app/core/immutable_audit.py. Registering it
# here, once, at import time (not per-request) is deliberate: SQLAlchemy
# event listeners are process-global, so registering per-request would just
# re-register the same no-op every time (register_immutability_guards() is
# idempotent) while adding needless overhead.
# Production security check
if settings.APP_ENV != "development" and settings.SECRET_KEY == "dev-only-change-me":
    raise RuntimeError(
        "SECRET_KEY must be set to a secure random value in non-development environments."
    )

app = FastAPI(
    title=settings.APP_NAME,
    description="Zero-trust, open-source AI agent platform for healthcare "
    "SIT/QA test case generation. No direct database access; all "
    "verification SQL is generated for manual analyst execution.",
    version="1.1.0-phase9.5",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Needed so the frontend's authenticated blob-download (Phase 9 — a
    # plain <a href> can't carry the Bearer token, so exports are fetched
    # via axios and saved client-side instead) can read the real filename
    # FastAPI's FileResponse sets via Content-Disposition. Only matters for
    # deployments where frontend/backend aren't same-origin via a dev
    # proxy — harmless to expose either way.
    expose_headers=["Content-Disposition"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(ingestion.router)
app.include_router(gatekeeper.router)
app.include_router(generation.router)
app.include_router(export.router)
app.include_router(refinement.router)
app.include_router(cognos_api.router)
app.include_router(jobs.router)

@app.get("/")
def root():
    return {
        "message": settings.APP_NAME,
        "phase": "9 - RBAC + immutable audit + encryption at rest + prompt-injection defenses + malware scanning",
        "docs": "/docs",
    }
