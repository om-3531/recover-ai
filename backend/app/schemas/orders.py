"""
Pydantic schemas for Razorpay order creation and signature verification.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class RazorpayOrderCreate(BaseModel):
    """Request schema for creating a Razorpay order."""

    amount: int = Field(..., gt=0, description="Amount in paise (e.g. 49900 = 499.00 INR)")
    currency: str = Field(default="INR", max_length=10)
    receipt: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[dict[str, Any]] = None


class RazorpayOrderResponse(BaseModel):
    """Response schema for a created Razorpay order."""

    id: str
    amount: int
    currency: str
    status: str
    receipt: Optional[str] = None
    created_at: Optional[int] = None

    model_config = ConfigDict(extra="ignore")


class PaymentSignatureVerifyRequest(BaseModel):
    """Request schema for verifying customer checkout payment signature."""

    razorpay_order_id: str = Field(..., min_length=1)
    razorpay_payment_id: str = Field(..., min_length=1)
    razorpay_signature: str = Field(..., min_length=1)


class PaymentSignatureVerifyResponse(BaseModel):
    """Response schema for payment signature verification."""

    verified: bool
    message: str = "Payment signature verified successfully"
