"""
Pydantic schemas for Merchant Policy configuration and evaluation.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MerchantPolicyBase(BaseModel):
    """Base fields for merchant policy configuration."""

    high_risk_threshold_paise: int = Field(
        default=1000000,
        ge=0,
        description="Threshold above which cases are classified as high risk in integer paise (₹10,000 = 1000000)",
    )
    critical_risk_threshold_paise: int = Field(
        default=5000000,
        ge=0,
        description="Threshold above which cases are classified as critical risk in integer paise (₹50,000 = 5000000)",
    )
    human_review_threshold_paise: int = Field(
        default=1000000,
        ge=0,
        description="Transactions at or above this amount strictly require human review in integer paise",
    )
    auto_execute_low_risk: bool = Field(
        default=True,
        description="Whether low-risk cases below human review threshold may be auto-executed",
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum recovery attempts allowed per case (1 to 10)",
    )
    backoff_base_seconds: int = Field(
        default=30,
        ge=1,
        le=3600,
        description="Base delay in seconds for exponential backoff retries",
    )
    allowed_channels: List[str] = Field(
        default_factory=lambda: ["email", "sms", "whatsapp", "webhook"],
        description="List of allowed communication channels",
    )
    preferred_channel: str = Field(
        default="email",
        description="Primary fallback channel for recovery communications",
    )
    min_recovery_amount_paise: int = Field(
        default=10000,
        ge=0,
        description="Minimum payment failure amount to initiate recovery for (₹100 = 10000)",
    )
    max_recovery_amount_paise: int = Field(
        default=100000000,
        ge=0,
        description="Maximum payment failure amount permitted for recovery workflows (₹10,00,000 = 100000000)",
    )
    require_approval_for_high_risk: bool = Field(
        default=True,
        description="Whether high-risk cases strictly require human approval before execution",
    )
    require_approval_for_critical_risk: bool = Field(
        default=True,
        description="Whether critical-risk cases strictly require human approval before execution",
    )
    webhook_enabled: bool = Field(
        default=True,
        description="Whether partner webhook pings are allowed",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this policy is active",
    )


class MerchantPolicyCreate(MerchantPolicyBase):
    """Schema for creating a merchant policy."""

    merchant_id: str = Field(
        default="merchant_default",
        description="Merchant identifier",
    )


class MerchantPolicyUpdate(BaseModel):
    """Schema for updating a merchant policy."""

    high_risk_threshold_paise: Optional[int] = Field(None, ge=0)
    critical_risk_threshold_paise: Optional[int] = Field(None, ge=0)
    human_review_threshold_paise: Optional[int] = Field(None, ge=0)
    auto_execute_low_risk: Optional[bool] = None
    max_attempts: Optional[int] = Field(None, ge=1, le=10)
    backoff_base_seconds: Optional[int] = Field(None, ge=1, le=3600)
    allowed_channels: Optional[List[str]] = None
    preferred_channel: Optional[str] = None
    min_recovery_amount_paise: Optional[int] = Field(None, ge=0)
    max_recovery_amount_paise: Optional[int] = Field(None, ge=0)
    require_approval_for_high_risk: Optional[bool] = None
    require_approval_for_critical_risk: Optional[bool] = None
    webhook_enabled: Optional[bool] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")


class MerchantPolicyResponse(MerchantPolicyBase):
    """Schema for returning merchant policy data."""

    id: int
    merchant_id: str
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PolicyValidationResult(BaseModel):
    """Result of validating a merchant policy configuration."""

    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    summary: Optional[str] = None


class PolicyEvaluationContext(BaseModel):
    """Context provided to evaluate recovery actions against a merchant policy."""

    amount_paise: int
    channel: str
    risk_status: str
    attempt_count: int = 0
    current_state: str = "open"


class PolicyEvaluationResult(BaseModel):
    """Result of evaluating a specific recovery action against a merchant policy."""

    allowed: bool
    requires_human_review: bool
    reason: str
    effective_channel: str
    is_auto_executable: bool
    policy_override_applied: bool = False
    blocked_actions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class PolicyPreviewRequest(BaseModel):
    """Request body for policy preview — hypothetical recovery scenario."""

    amount_paise: int = Field(
        ...,
        ge=0,
        description="Hypothetical recovery amount in integer paise",
    )
    risk_status: str = Field(
        default="low",
        description="Risk level: low, medium, high, critical",
    )
    channel: str = Field(
        default="email",
        description="Proposed communication channel",
    )
    attempt_count: int = Field(
        default=0,
        ge=0,
        description="Current attempt count for the case",
    )
    current_state: str = Field(
        default="open",
        description="Current recovery case state",
    )


class PolicyPreviewResponse(BaseModel):
    """Informational preview of what a policy decision would be — executes nothing."""

    evaluation: PolicyEvaluationResult
    summary: Optional[str] = None
