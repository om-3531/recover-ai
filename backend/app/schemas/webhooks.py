"""
Pydantic schemas for Razorpay webhook endpoints, developer simulation, fixtures, and tunnel guide.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WebhookResponse(BaseModel):
    """Response schema for webhook processing."""

    status: str
    event_id: str
    event_type: Optional[str] = None
    message: str = "Webhook received and processed"
    recovery_case_id: Optional[int] = None
    orchestration_status: Optional[str] = None
    orchestration_message: Optional[str] = None
    approval_id: Optional[int] = None


class WebhookTestRequest(BaseModel):
    """Schema for submitting a synthetic Razorpay webhook via the developer console."""

    event_type: str = Field(..., description="Razorpay event type (e.g. payment.failed, payment.captured)")
    payload: Dict[str, Any] = Field(..., description="Complete synthetic event payload dictionary")


class WebhookTestResponse(BaseModel):
    """Schema for test webhook execution results."""

    status: str
    event_id: str
    event_type: str
    message: str
    is_duplicate: bool = False
    payment_id: Optional[int] = None
    revenue_record_id: Optional[int] = None
    recovery_case_id: Optional[int] = None
    orchestration_status: Optional[str] = None
    orchestration_message: Optional[str] = None
    approval_id: Optional[int] = None
    request_id: Optional[str] = None
    audit_action: str = "razorpay_webhook_processed"


class WebhookFixture(BaseModel):
    """Schema for predefined synthetic test fixtures."""

    key: str
    title: str
    event_type: str
    description: str
    payload: Dict[str, Any]


class WebhookTunnelGuide(BaseModel):
    """Developer guide for local tunnel forwarding."""

    service_name: str = "RecoverAI Local Webhook Gateway"
    target_url: str = "http://localhost:8000/api/v1/webhooks/razorpay"
    security_notice: str
    tunnel_options: List[Dict[str, str]]
    razorpay_configured: bool = False
    test_mode_only: bool = True


class RazorpayConfigStatus(BaseModel):
    """Safe Razorpay configuration status (no secrets exposed)."""

    configured: bool
    key_id_present: bool
    key_secret_present: bool
    webhook_secret_present: bool
    test_mode: bool
    status_message: str


class WebhookRecentEvent(BaseModel):
    """A single recent webhook event entry for the live monitor."""

    id: int
    event_type: str
    event_id: Optional[str] = None
    status: str
    recovery_case_id: Optional[int] = None
    payment_id: Optional[int] = None
    orchestration_status: Optional[str] = None
    message: Optional[str] = None
    timestamp: datetime
    is_duplicate: bool = False


class WebhookRecentEventsResponse(BaseModel):
    """Paginated response of recent webhook events."""

    items: list[WebhookRecentEvent]
    total: int


class RecoveryTimelineEvent(BaseModel):
    """A single timeline event for a recovery case."""

    id: int
    action: str
    actor: str
    entity_type: str
    entity_id: str
    event_metadata: Optional[dict[str, Any]] = None
    timestamp: datetime


class RecoveryTimelineResponse(BaseModel):
    """Full timeline of audit events for a recovery case."""

    recovery_case_id: int
    events: list[RecoveryTimelineEvent]
    total_events: int
