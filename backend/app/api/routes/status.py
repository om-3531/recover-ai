"""
Versioned API status route.

This exists to prove the `/api/v1` mount works end-to-end. Domain routes
(payments, recovery, ai-decisions, audit-trail, etc.) will be added as
their own modules under `app/api/routes/` in later milestones and
registered in `app/api/router.py`.
"""

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["status"])
settings = get_settings()


@router.get("/status")
def get_api_status() -> dict:
    """Confirms the versioned API surface is reachable."""
    return {
        "api_version": "v1",
        "environment": settings.ENVIRONMENT,
    }
