"""
Pydantic schemas for Recovery Execution.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    RecoveryActionChannel,
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryCaseState,
)


class ExecutionResult(BaseModel):
    """Structured result returned by a recovery action executor."""

    success: bool
    execution_id: str = Field(default_factory=lambda: f"exec_{uuid4().hex[:12]}")
    action_type: RecoveryActionType
    channel: RecoveryActionChannel
    status: RecoveryActionStatus
    message: str
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    retryable: bool = False
    error_code: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")


class ExecutionResponse(BaseModel):
    """Response schema returned after executing an approved recovery action."""

    approval_id: int
    recovery_case_id: int
    recovery_action_id: int
    result: ExecutionResult
    case_state: RecoveryCaseState

    model_config = ConfigDict(extra="ignore")
