"""
Pydantic schemas for Analytics and Dashboard Metrics.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RecoveryActionChannel


class OverviewMetrics(BaseModel):
    """High-level summary of recovery cases, revenue, approvals, and execution metrics."""

    total_cases: int
    open_cases: int
    action_pending_cases: int
    recovering_cases: int
    recovered_cases: int
    closed_cases: int
    failed_cases: int = 0

    total_recoverable_amount: int = Field(
        ..., description="Total recoverable amount in paise"
    )
    total_recovered_amount: int = Field(
        ..., description="Total recovered amount in paise"
    )
    recovery_rate: float = Field(
        ..., description="Ratio of recovered to recoverable amount (0.0 to 1.0)"
    )
    case_recovery_rate: float = Field(
        ..., description="Ratio of recovered cases to total cases (0.0 to 1.0)"
    )

    total_approvals: int
    pending_approvals: int
    approved_approvals: int
    rejected_approvals: int

    total_execution_jobs: int
    successful_jobs: int
    failed_jobs: int
    retry_scheduled_jobs: int
    execution_success_rate: float = Field(
        ..., description="Ratio of successful jobs to finished jobs (0.0 to 1.0)"
    )

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class RevenueAnalytics(BaseModel):
    """Financial recovery metrics and averages."""

    total_recoverable_amount: int
    total_recovered_amount: int
    recovery_rate: float
    average_recovery_amount: int
    recovered_case_count: int
    currency: str = "INR"

    model_config = ConfigDict(from_attributes=True)


class ChannelAnalytics(BaseModel):
    """Per-communication-channel execution metrics."""

    channel: RecoveryActionChannel
    total: int
    successful: int
    failed: int
    success_rate: float

    model_config = ConfigDict(from_attributes=True)


class ExecutionAnalytics(BaseModel):
    """Job execution lifecycle metrics, retries, and channel distribution."""

    total_jobs: int
    queued: int
    running: int
    succeeded: int
    failed: int
    retry_scheduled: int
    cancelled: int
    success_rate: float
    total_retries: int
    jobs_with_retries: int
    average_attempt_count: float
    max_attempt_count: int
    channels: list[ChannelAnalytics]

    model_config = ConfigDict(from_attributes=True)


class ApprovalAnalytics(BaseModel):
    """Human and automated approval decision metrics."""

    total: int
    pending: int
    approved: int
    rejected: int
    expired: int
    cancelled: int
    approval_rate: float

    model_config = ConfigDict(from_attributes=True)


class ErrorBreakdownItem(BaseModel):
    """Grouped error code count."""

    error_code: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class FailureAnalytics(BaseModel):
    """Execution failure analysis and error breakdown."""

    failure_count: int
    retryable_failure_count: int
    non_retryable_failure_count: int
    error_breakdown: list[ErrorBreakdownItem]

    model_config = ConfigDict(from_attributes=True)


class TimelinePoint(BaseModel):
    """Daily time-series bucket of recovery events."""

    date: str = Field(..., description="Date formatted as YYYY-MM-DD")
    cases_created: int = 0
    cases_recovered: int = 0
    recoverable_amount: int = 0
    recovered_amount: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    recovery_rate: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class RecentActivityItem(BaseModel):
    """Recent event log for dashboard activity feeds."""

    id: int
    event: str
    entity_type: str
    entity_id: str
    case_id: Optional[int] = None
    timestamp: datetime
    status: str
    actor: Optional[str] = None
    details: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RecentActivityResponse(BaseModel):
    """List of recent audit and execution activities."""

    items: list[RecentActivityItem]
    total: int

    model_config = ConfigDict(from_attributes=True)
