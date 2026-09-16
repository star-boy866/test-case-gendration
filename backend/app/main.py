from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from app.core.config import settings
from app.db.session import engine
from app.db.init_db import init_db
from app.core.immutable_audit import register_immutability_guards
from app.api import (
    health, ingestion, gatekeeper, generation,
    export, refinement, auth, cognos_api, jobs, admin_rbac, admin_database
)

# Phase 9: register immutable audit listeners (in-memory ORM event listeners)
register_immutability_guards()

# Ensure schema exists for standalone single-process local development (e.g. `uvicorn app.main:app`).
# In production Docker, pre-flight `python -m app.db.init_db` executes sequentially before Gunicorn
# forks workers, so inspector.has_table("users") returns True and worker imports bypass schema DDL entirely.
try:
    _inspector = inspect(engine)
    if not _inspector.has_table("users"):
        init_db()
except Exception as _e:
    _inspector = inspect(engine)
    if not _inspector.has_table("users"):
        raise RuntimeError(f"Database schema initialization failed on startup: {_e}") from _e

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

cors_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
for default_origin in ("http://localhost:5173", "https://cognos-test-case-frontend.onrender.com"):
    if default_origin not in cors_origins:
        cors_origins.append(default_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.onrender\.com",
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
app.include_router(admin_rbac.router)
app.include_router(ingestion.router)
app.include_router(gatekeeper.router)
app.include_router(generation.router)
app.include_router(export.router)
app.include_router(refinement.router)
app.include_router(cognos_api.router)
app.include_router(jobs.router)
app.include_router(admin_database.router)



@app.middleware("http")
async def add_security_and_cache_headers(request, call_next):
    response = await call_next(request)
    # Prevent browser caching of protected healthcare and RBAC endpoints
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/")
def root():
    return {
        "message": settings.APP_NAME,
        "phase": "9 - RBAC + immutable audit + encryption at rest + prompt-injection defenses + malware scanning",
        "docs": "/docs",
    }
