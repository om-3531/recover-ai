"""Top-level health check route (not versioned — used by uptime checks)."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Simple liveness check. Does not touch the database."""
    return HealthResponse(status="ok", service=settings.APP_NAME)
