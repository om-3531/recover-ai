"""
Pydantic schemas for AI Decision Engine and Policy Engine.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    PaymentStatus,
    RecoveryActionChannel,
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryCaseState,
    RecoveryPriority,
    RevenueStatus,
    RiskStatus,
)


class RecoveryContext(BaseModel):
    """
    Sanitized context representation of a RecoveryCase and linked financial entities.
    Strictly contains zero secrets, passwords, API keys, or raw credential tokens.
    """

    recovery_case_id: int
    revenue_record_id: int
    payment_id: Optional[int] = None
    razorpay_payment_id: Optional[str] = None
    payment_amount: int = Field(..., ge=0, description="Gross amount in paise")
    currency: str = Field(default="INR", max_length=10)
    payment_status: PaymentStatus
    revenue_status: RevenueStatus
    recoverable_amount: int = Field(..., ge=0, description="Recoverable amount in paise")
    recovery_case_reason: Optional[str] = None
    recovery_case_priority: RecoveryPriority
    recovery_case_risk_status: RiskStatus
    recovery_case_current_state: RecoveryCaseState
    action_count: int = Field(default=0, ge=0)
    last_action_type: Optional[RecoveryActionType] = None
    last_action_channel: Optional[RecoveryActionChannel] = None
    last_action_status: Optional[RecoveryActionStatus] = None

    model_config = ConfigDict(extra="ignore")


class RawRecommendation(BaseModel):
    """Raw structured recommendation emitted by an AI provider before policy filtering."""

    recommended_action_type: Optional[RecoveryActionType] = None
    recommended_channel: Optional[RecoveryActionChannel] = None
    priority: RecoveryPriority = RecoveryPriority.medium
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    rationale: str = Field(..., min_length=1, max_length=1000)
    risk_flags: list[str] = Field(default_factory=list)
    requires_human_review: bool = False

    model_config = ConfigDict(extra="ignore")


class PolicyDecision(BaseModel):
    """Evaluation result from the deterministic Policy Engine."""

    allowed: bool
    requires_human_review: bool
    reason: str
    blocked_actions: list[RecoveryActionType] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore", protected_namespaces=())


class RecoveryRecommendation(BaseModel):
    """Final, validated, and policy-checked recovery recommendation."""

    recommendation_id: str = Field(default_factory=lambda: f"rec_{uuid4().hex[:12]}")
    recovery_case_id: int
    recommended_action_type: Optional[RecoveryActionType] = None
    recommended_channel: Optional[RecoveryActionChannel] = None
    priority: RecoveryPriority
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str
    risk_flags: list[str] = Field(default_factory=list)
    requires_human_review: bool
    policy_decision: PolicyDecision
    is_blocked: bool = False
    provider: str = "mock"
    model_name: str = "mock-decision-v1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(extra="ignore", protected_namespaces=())
