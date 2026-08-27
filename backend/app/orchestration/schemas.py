"""
Pydantic schemas for Recovery Orchestration.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.ai.schemas import RecoveryRecommendation
from app.execution.schemas import ExecutionResult
from app.models.enums import (
    ApprovalStatus,
    RecoveryActionStatus,
    RecoveryCaseState,
)


class WorkflowStatus(str, Enum):
    """Lifecycle state of an orchestrated recovery workflow."""

    started = "started"
    recommendation_generated = "recommendation_generated"
    policy_blocked = "policy_blocked"
    approval_required = "approval_required"
    approval_created = "approval_created"
    approved = "approved"
    execution_started = "execution_started"
    execution_succeeded = "execution_succeeded"
    execution_failed = "execution_failed"
    completed = "completed"


class OrchestrateRequest(BaseModel):
    """Request payload for triggering recovery orchestration."""

    auto_execute_low_risk: bool = Field(
        default=False,
        description="Whether to automatically approve and execute low/medium-risk recommendations that do not require human review",
    )


class OrchestrationResult(BaseModel):
    """Structured result returned by the RecoveryOrchestrator."""

    workflow_id: str = Field(default_factory=lambda: f"wf_{uuid4().hex[:12]}")
    recovery_case_id: int
    status: WorkflowStatus
    case_state: RecoveryCaseState
    recommendation: Optional[RecoveryRecommendation] = None
    approval_id: Optional[int] = None
    execution_result: Optional[ExecutionResult] = None
    requires_human_review: bool = False
    is_blocked: bool = False
    message: str
    next_action: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(extra="ignore", protected_namespaces=())


class WorkflowStatusResponse(BaseModel):
    """Diagnostic status response for a recovery case workflow."""

    recovery_case_id: int
    case_state: RecoveryCaseState
    current_workflow_status: WorkflowStatus
    latest_approval_id: Optional[int] = None
    latest_approval_status: Optional[ApprovalStatus] = None
    latest_action_id: Optional[int] = None
    latest_action_status: Optional[RecoveryActionStatus] = None
    is_terminal: bool = False
    recoverable_amount: int = 0

    model_config = ConfigDict(extra="ignore", protected_namespaces=())
