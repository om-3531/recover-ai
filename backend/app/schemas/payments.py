"""
Pydantic schemas for Payment endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PaymentMethod, PaymentStatus


class PaymentBase(BaseModel):
    """Base fields for payment definitions."""

    currency: str = Field(default="INR", max_length=10)
    customer_email: Optional[str] = Field(default=None, max_length=255)
    customer_reference: Optional[str] = Field(default=None, max_length=255)


class PaymentCreate(PaymentBase):
    """Request schema for creating a payment record."""

    razorpay_payment_id: str = Field(..., min_length=1, max_length=255)
    razorpay_order_id: Optional[str] = Field(default=None, max_length=255)
    amount: int = Field(..., gt=0, description="Amount in paise (e.g. 50000 = 500.00 INR)")
    status: PaymentStatus = Field(default=PaymentStatus.created)
    method: Optional[PaymentMethod] = None


class PaymentStatusUpdate(BaseModel):
    """Request schema for updating a payment's status."""

    status: PaymentStatus


class PaymentResponse(BaseModel):
    """Response schema for a single payment record."""

    id: int
    razorpay_payment_id: str
    razorpay_order_id: Optional[str] = None
    amount: int
    currency: str
    status: PaymentStatus
    method: Optional[PaymentMethod] = None
    customer_email: Optional[str] = None
    customer_reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentListResponse(BaseModel):
    """Paginated response schema for listing payments."""

    items: list[PaymentResponse]
    total: int
