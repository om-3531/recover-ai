"""
Pydantic schemas for System Status, Observability, and Provider Configuration endpoints.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.providers.validation import ProviderConfigStatus


class SystemStatusResponse(BaseModel):
    """Safe operational overview of the RecoverAI backend."""

    status: str = Field(..., description="'operational' or 'degraded'")
    service: str
    environment: str
    app_version: str
    demo_mode: bool
    database: str
    job_queue_status: str
    providers_summary: Dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SystemProvidersResponse(BaseModel):
    """Sanitized provider configuration readiness report."""

    providers: List[ProviderConfigStatus]

    model_config = ConfigDict(from_attributes=True)


class SystemMetricsResponse(BaseModel):
    """Operational telemetry counters."""

    metrics: Dict[str, int]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
