"""
Pydantic schemas for RevenueRecord endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RevenueStatus


class RevenueRecordCreate(BaseModel):
    """Request schema for creating a revenue record linked to a payment."""

    payment_id: int = Field(..., gt=0, description="Internal Payment ID")
    gross_amount: Optional[int] = Field(
        default=None,
        gt=0,
        description="Gross revenue amount in paise (defaults to linked payment amount if omitted)",
    )
    recoverable_amount: Optional[int] = Field(
        default=None,
        ge=0,
        description="Recoverable amount in paise",
    )
    currency: str = Field(default="INR", max_length=10)
    status: RevenueStatus = Field(default=RevenueStatus.pending)


class RevenueStatusUpdate(BaseModel):
    """Request schema for updating a revenue record's status and recoverable amount."""

    status: RevenueStatus
    recoverable_amount: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional updated recoverable amount in paise",
    )


class RevenueRecordResponse(BaseModel):
    """Response schema for a revenue record."""

    id: int
    payment_id: int
    gross_amount: int
    recoverable_amount: int
    currency: str
    status: RevenueStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
