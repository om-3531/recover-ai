"""
Top-level health and readiness check routes (unversioned — used by uptime monitors & probes).
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Simple liveness check. Does not touch the database."""
    return HealthResponse(status="ok", service=settings.APP_NAME)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"description": "Service is unavailable or database disconnected"}},
)
def get_readiness(db: Session = Depends(get_db)) -> ReadinessResponse:
    """Readiness probe checking database connectivity without exposing sensitive credentials."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
        overall_status = "ready"
        http_code = status.HTTP_200_OK
    except Exception as e:
        db_status = f"unhealthy: {type(e).__name__}"
        overall_status = "unhealthy"
        http_code = status.HTTP_503_SERVICE_UNAVAILABLE

    resp = ReadinessResponse(
        status=overall_status,
        service=settings.APP_NAME,
        database=db_status,
        environment=settings.ENVIRONMENT,
        demo_mode=settings.DEMO_MODE,
    )
    if http_code != status.HTTP_200_OK:
        return JSONResponse(status_code=http_code, content=resp.model_dump())
    return resp
