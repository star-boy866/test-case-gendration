from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
    }

@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Checks if critical dependencies (Postgres, Redis) are reachable.
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

    # Check Broker (if in production or celery is configured)
    if settings.CELERY_BROKER_URL and "redis" in settings.CELERY_BROKER_URL:
        try:
            r = redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=2)
            r.ping()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Broker unavailable: {str(e)}")

    return {"status": "ready"}
