# Healthcare NL-to-Test-Case: Enterprise Deployment Guide

## Overview
This platform has been hardened for Fortune 500 Enterprise deployment. It utilizes a containerized microservice architecture orchestrated via Docker Compose (or Kubernetes), backed by PostgreSQL and Redis.

## Prerequisites
- Docker Engine & Docker Compose
- PostgreSQL 15+ (if managed externally)
- Redis 7+ (if managed externally)
- Valid API keys for Groq/Ollama, SharePoint, and SMTP.

## Configuration & Environment Variables
The application strictly enforces production safety boundaries.
If `APP_ENV=production` is set, the application **WILL CRASH ON STARTUP** if:
1. `SECRET_KEY` is not cryptographically rotated from the default.
2. `DATABASE_URL` is pointing to SQLite instead of PostgreSQL.
3. `CELERY_BROKER_URL` is missing.

Copy `.env.example` to `.env` and supply your enterprise values.

## Deployment Strategy
```bash
# 1. Build and Start the full infrastructure
docker-compose up -d --build

# 2. Verify Health
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Database Migrations
Migrations are managed by Alembic. In a CI/CD environment, never run `create_all()`.
Instead, execute:
```bash
docker-compose exec api alembic upgrade head
```

## Rollback Procedure
**Application Artifact Rollback:**
1. Pin the previous Docker image digest in `docker-compose.yml`.
2. `docker-compose up -d api worker`

**Database Rollback:**
Database migrations are strictly designed as Expand/Contract. Destructive schema changes are banned. Thus, deploying an older application artifact is immediately compatible with the newer database schema. Downgrading the database itself (`alembic downgrade`) is generally avoided in production to prevent data loss.

## Worker Process & Job Versioning
Durable jobs (Phase 9.5) are processed by Celery.
When deploying a new version that alters job schemas, the new worker code maintains backward-compatibility routes for old job JSON payloads. Never forcefully purge the Redis queue during an upgrade.
Scale workers horizontally by replicating the `worker` service.

## Observability & Logging
All logs are emitted to standard output (STDOUT). Use your platform's log router (e.g. FluentBit, Datadog) to capture and index these logs.
Sensitive fields (JWTs, Document contents) are automatically redacted at the application boundary.

## Secrets Management
Never commit `.env`. In staging/production, inject variables securely through your orchestrator's native secret manager (e.g. AWS Secrets Manager, HashiCorp Vault, K8s Secrets).
