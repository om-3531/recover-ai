"""
Pydantic schemas for Recovery Execution Jobs.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import JobStatus


class JobCreateRequest(BaseModel):
    """Payload for creating or scheduling an execution job."""

    max_attempts: int = Field(default=3, ge=1, le=10)
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Optional client-provided idempotency key. Generated deterministically if omitted.",
    )


class JobResponse(BaseModel):
    """Detailed response model for a RecoveryExecutionJob."""

    id: int
    recovery_case_id: int
    recovery_approval_id: int
    recovery_action_id: Optional[int] = None
    status: JobStatus
    attempt_count: int
    max_attempts: int
    idempotency_key: str
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    """Paginated list of execution jobs."""

    items: list[JobResponse]
    total: int
    limit: int
    offset: int


class JobExecutionSummary(BaseModel):
    """High-level summary of job execution dispatch."""

    job_id: int
    approval_id: int
    status: JobStatus
    message: str
    attempt_count: int
    is_terminal: bool

    model_config = ConfigDict(from_attributes=True)
