"""
Pydantic schemas for Demo operations, scenario execution, and synthetic data seeding.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DemoSeedRequest(BaseModel):
    """Parameters for synthetic dataset generation."""

    count: int = Field(50, ge=5, le=500, description="Number of synthetic cases to generate")
    seed: int = Field(42, description="Random seed for deterministic generation")
    scenario: Optional[str] = Field("all", description="Specific scenario name or 'all'")
    reset: bool = Field(False, description="Whether to clear existing data before seeding")


class DemoSeedResponse(BaseModel):
    """Summary of created synthetic entities."""

    seed: int
    payments_created: int
    revenue_records_created: int
    cases_created: int
    approvals_created: int
    jobs_created: int
    audit_logs_created: int
    total_recoverable_amount: int = Field(..., description="Total recoverable in paise")
    total_recovered_amount: int = Field(..., description="Total recovered in paise")
    message: str

    model_config = ConfigDict(from_attributes=True)


class DemoResetResponse(BaseModel):
    """Summary of purged records."""

    payments_deleted: int
    cases_deleted: int
    jobs_deleted: int
    audit_logs_deleted: int
    message: str

    model_config = ConfigDict(from_attributes=True)


class DemoScenarioInfo(BaseModel):
    """Metadata describing an interactive demo scenario."""

    id: str
    name: str
    description: str
    risk_level: str
    channel: str
    expected_outcome: str

    model_config = ConfigDict(from_attributes=True)


class DemoScenarioListResponse(BaseModel):
    """List of available demo scenarios."""

    scenarios: List[DemoScenarioInfo]


class DemoScenarioRunResponse(BaseModel):
    """Result of running an individual end-to-end scenario."""

    scenario_id: str
    scenario_name: str
    payment_id: int
    case_id: int
    approval_id: Optional[int] = None
    job_id: Optional[int] = None
    case_state: str
    approval_status: Optional[str] = None
    job_status: Optional[str] = None
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
