# Phase 9.7 Current Deployment Inventory

## 1. Startup Commands
- **Backend Current**: `python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- **Frontend Current**: `npm run dev` (Vite dev server)
- **Gap**: Both are using development servers. No production WSGI/ASGI server (e.g. `gunicorn`) or frontend static asset server (e.g. `nginx`) is configured.

## 2. Process Model
- **Backend Process**: Single synchronous Uvicorn process (no parallel workers).
- **Database Dependency**: SQLite locally (`./database/app_metadata.db`), with Postgres configs (`DATABASE_URL`) available but not strictly enforced.
- **Broker Dependency**: Celery/Redis (`redis://localhost:6379/0`).
- **Worker Dependency**: No explicit production worker startup command documented.
- **External Dependencies**: Ollama (local LLM), Groq (remote LLM), SharePoint, SMTP.

## 3. Configuration & Environment Variables
- Configuration is centralized in `app/core/config.py` using `pydantic_settings`.
- Loads from `.env`. Contains categories for Application, Server, CORS, Database, Background Jobs, LLM, External Integrations, Security.
- **Gap**: Startup does not explicitly fail if `DATABASE_URL` or `CELERY_BROKER_URL` are missing in a `PRODUCTION` environment.
- **Secrets Check**: `SECRET_KEY = "dev-only-change-me"`. `ENCRYPTION_KEY` is empty. `GROQ_API_KEY`, `SHAREPOINT_*`, `SMTP_PASSWORD` exist.

## 4. Dockerization
- **Backend**: **DOCUMENTATION_DRIFT**. No `Dockerfile` exists.
- **Frontend**: **DOCUMENTATION_DRIFT**. No `Dockerfile` exists.
- **Compose**: Only a `docker-compose.test.yml` exists (likely containing just Redis/Postgres test dependencies).

## 5. Dependency Reproducibility
- **Backend**: Uses `requirements.txt`. Hashes or exact pins are not strictly enforced or checked via CI.
- **Frontend**: Uses `package-json` and `package-lock.json`. Reproducible via `npm ci`, but not automated.

## 6. Health Endpoints
- **Health**: `GET /health` exists and returns basic status.
- **Readiness**: **DOCUMENTATION_DRIFT**. No `/ready` endpoint checks DB/Broker connectivity.

## 7. CI/CD & Security Scanning
- **CI/CD Pipeline**: **DOCUMENTATION_DRIFT**. No `.github/workflows/` or equivalent exists.
- **Test Commands**: `pytest tests/` exists but is manually executed.
- **Lint/Format/SAST**: None configured in CI.
- **Migration Commands**: Alembic is configured, but no automated migration strategy.

## 8. Deployment Gaps
1. No production-ready Dockerfiles (multi-stage frontend, hardened backend).
2. No automated CI pipeline to gate PRs (Tests, AST, Golden Regression, Lint, SAST).
3. No configuration validation enforcing `APP_ENV=production` safety.
4. No `/ready` endpoint checking Postgres/Redis.
5. No Gunicorn startup script or Celery worker startup wrapper.
6. Missing Security headers (CORS allows specific origins, but CSP/HSTS are absent).
