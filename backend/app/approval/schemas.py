"""
Pydantic schemas for Recovery Approval layer.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ApprovalStatus,
    RecoveryActionChannel,
    RecoveryActionType,
)


class ApprovalCreateRequest(BaseModel):
    """Request schema for creating a new recovery action approval request."""

    recovery_case_id: int = Field(..., description="ID of the associated RecoveryCase")
    action_type: RecoveryActionType
    channel: RecoveryActionChannel
    recommendation_id: Optional[str] = Field(default=None, max_length=255)
    requires_human_review: bool = False
    expires_in_hours: Optional[int] = Field(default=24, ge=1, le=168)


class ApprovalDecisionRequest(BaseModel):
    """Request schema for approving or rejecting an approval request."""

    approved_by: Optional[str] = Field(default="human_operator", max_length=128)
    rejection_reason: Optional[str] = Field(default=None, max_length=255)


class ApprovalResponse(BaseModel):
    """Response schema representing an authoritative recovery approval record."""

    id: int
    recovery_case_id: int
    recovery_action_id: Optional[int] = None
    recommendation_id: Optional[str] = None
    action_type: RecoveryActionType
    channel: RecoveryActionChannel
    status: ApprovalStatus
    requires_human_review: bool
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    requested_at: datetime
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    execution_result: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalListResponse(BaseModel):
    """Paginated list response for recovery approvals."""

    items: list[ApprovalResponse]
    total: int
