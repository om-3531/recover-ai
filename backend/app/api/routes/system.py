"""
System administrative and operational status endpoints.

Provides sanitized telemetry, provider readiness verification, and metrics inspection.
Zero credentials, passwords, or authorization tokens are ever exposed.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.metrics import metrics
from app.db.session import get_db
from app.jobs.queue import get_default_job_queue
from app.providers.validation import ProviderConfigurationService

from app.schemas.system import (
    SystemMetricsResponse,
    SystemProvidersResponse,
    SystemStatusResponse,
)

router = APIRouter(prefix="/system", tags=["system"])
settings = get_settings()


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    summary="Get system operational status",
    description="Returns high-level application health, database connectivity, and provider readiness summary.",
)
def get_system_status(
    request: Request,
    db: Session = Depends(get_db),
) -> SystemStatusResponse:
    """Operational status overview."""
    # Check DB
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"disconnected: {type(e).__name__}"

    # Check Queue
    queue = get_default_job_queue()
    q_status = "operational" if queue is not None else "unavailable"


    # Provider Summary
    providers = ProviderConfigurationService.get_all_provider_statuses()
    prov_summary = {
        p.provider: ("configured (real)" if p.enabled else ("ready (mock)" if p.safe_to_use else "unconfigured"))
        for p in providers
    }

    req_id = getattr(request.state, "request_id", None)
    overall_status = "operational" if db_status == "connected" else "degraded"

    return SystemStatusResponse(
        status=overall_status,
        service=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        app_version=settings.APP_VERSION,
        demo_mode=settings.DEMO_MODE,
        database=db_status,
        job_queue_status=q_status,
        providers_summary=prov_summary,
        timestamp=datetime.now(timezone.utc),
        request_id=req_id,
    )


@router.get(
    "/providers",
    response_model=SystemProvidersResponse,
    summary="Get provider configuration readiness",
    description="Returns safe readiness states for Gemini, SendGrid, Twilio, Meta WhatsApp, and Webhook providers.",
)
def get_system_providers() -> SystemProvidersResponse:
    """List provider readiness states."""
    providers = ProviderConfigurationService.get_all_provider_statuses()
    return SystemProvidersResponse(providers=providers)


@router.get(
    "/metrics",
    response_model=SystemMetricsResponse,
    summary="Get operational telemetry counters",
    description="Returns lightweight in-memory counters for AI decisions, approvals, and job executions.",
)
def get_system_metrics() -> SystemMetricsResponse:
    """Return runtime metrics."""
    return SystemMetricsResponse(
        metrics=metrics.get_all_metrics(),
        timestamp=datetime.now(timezone.utc),
    )
