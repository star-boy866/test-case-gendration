from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import Base, engine, SessionLocal
from app import models  # noqa: F401  ensures all ORM tables register before create_all
from app.db.migrations import ensure_rbac_schema
from app.services.user_service import bootstrap_standard_admin, ensure_tester_account
from app.core.immutable_audit import register_immutability_guards
from app.api import (
    health, ingestion, gatekeeper, generation,
    export, refinement, auth, cognos_api, jobs, admin_rbac
)

# Create SQLite tables and perform lightweight schema upgrades on startup
Base.metadata.create_all(bind=engine)
ensure_rbac_schema(engine)

# Bootstrap the initial Standard Administrator account ('obuli') and Tester account
_init_db = SessionLocal()
try:
    bootstrap_standard_admin(_init_db)
    ensure_tester_account(_init_db)
finally:
    _init_db.close()

# Phase 9: register immutable audit listeners
register_immutability_guards()

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
