"""
Pydantic schemas for RecoveryCase and RecoveryAction endpoints.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    RecoveryActionChannel,
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryCaseState,
    RecoveryPriority,
    RiskStatus,
)


class RecoveryActionCreate(BaseModel):
    """Request schema for creating a recovery action on a case."""

    action_type: RecoveryActionType
    channel: RecoveryActionChannel
    status: RecoveryActionStatus = Field(default=RecoveryActionStatus.pending)
    scheduled_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None


class RecoveryActionStatusUpdate(BaseModel):
    """Request schema for updating a recovery action's execution status."""

    status: RecoveryActionStatus
    result: Optional[dict[str, Any]] = None
    executed_at: Optional[datetime] = None


class RecoveryActionResponse(BaseModel):
    """Response schema for a single recovery action."""

    id: int
    recovery_case_id: int
    action_type: RecoveryActionType
    channel: RecoveryActionChannel
    status: RecoveryActionStatus
    scheduled_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecoveryCaseCreate(BaseModel):
    """Request schema for creating a recovery case."""

    revenue_record_id: int = Field(..., gt=0, description="Internal RevenueRecord ID")
    reason: Optional[str] = Field(default=None, max_length=255)
    risk_status: RiskStatus = Field(default=RiskStatus.medium)
    priority: RecoveryPriority = Field(default=RecoveryPriority.medium)
    current_state: RecoveryCaseState = Field(default=RecoveryCaseState.open)


class RecoveryCaseStateUpdate(BaseModel):
    """Request schema for transitioning a recovery case's state."""

    current_state: RecoveryCaseState
    reason: Optional[str] = Field(default=None, max_length=255)


class RecoveryCaseResponse(BaseModel):
    """Response schema for a recovery case including nested actions."""

    id: int
    revenue_record_id: int
    reason: Optional[str] = None
    risk_status: RiskStatus
    priority: RecoveryPriority
    current_state: RecoveryCaseState
    created_at: datetime
    updated_at: datetime
    actions: list[RecoveryActionResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RecoveryCaseListResponse(BaseModel):
    """Paginated response schema for listing recovery cases."""

    items: list[RecoveryCaseResponse]
    total: int
