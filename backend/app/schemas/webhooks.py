"""
Pydantic schemas for Razorpay webhook endpoints.
"""

from typing import Optional

from pydantic import BaseModel


class WebhookResponse(BaseModel):
    """Response schema for webhook processing."""

    status: str
    event_id: str
    event_type: Optional[str] = None
    message: str = "Webhook received and processed"
