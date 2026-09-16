from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db, engine

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    url = engine.url
    is_postgres = "postgresql" in str(url.drivername).lower() or "postgres" in str(url.drivername).lower()
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": "production" if settings.is_production else settings.APP_ENV,
        "database_backend": "postgresql" if is_postgres else "sqlite",
        "persistence_mode": "external" if is_postgres else "local",
        "database_driver": str(url.drivername),
    }

@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Checks if critical dependencies (Postgres/DB) are reachable.
    Does NOT check optional integrations like SharePoint or SMTP.
    """
    from sqlalchemy import text
    from fastapi import HTTPException
    import redis

    # Check Database
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {str(e)}")

    # Check Broker if a real external broker is configured
    if settings.CELERY_BROKER_URL and "redis" in settings.CELERY_BROKER_URL and "localhost" not in settings.CELERY_BROKER_URL:
        try:
            r = redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=2)
            r.ping()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Broker unavailable: {str(e)}")

    return {"status": "ready"}
