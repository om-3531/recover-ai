"""
Demo REST API endpoints.

Provides safe demo dataset seeding, scenario execution, and environment reset.
Guarded by DEMO_MODE configuration (returns HTTP 403 when disabled).
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.demo.schemas import (
    DemoResetResponse,
    DemoScenarioInfo,
    DemoScenarioListResponse,
    DemoScenarioRunResponse,
    DemoSeedRequest,
    DemoSeedResponse,
)
from app.demo.service import DemoService

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post(
    "/seed",
    response_model=DemoSeedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Seed deterministic synthetic dataset",
    description="Populates payments, revenue records, cases, approvals, and execution jobs across the last 30 days.",
)
def seed_demo_dataset(
    request: DemoSeedRequest = DemoSeedRequest(),
    db: Session = Depends(get_db),
) -> DemoSeedResponse:
    """Seed synthetic recovery data."""
    return DemoService.seed_data(
        db=db,
        count=request.count,
        seed=request.seed,
        scenario=request.scenario,
        reset=request.reset,
    )


@router.post(
    "/reset",
    response_model=DemoResetResponse,
    summary="Reset and purge demo dataset",
    description="Purges synthetic records to reset the environment for testing or fresh demonstrations.",
)
def reset_demo_dataset(db: Session = Depends(get_db)) -> DemoResetResponse:
    """Purge demo records."""
    return DemoService.reset_data(db)


@router.get(
    "/scenarios",
    response_model=DemoScenarioListResponse,
    summary="List available demo scenarios",
    description="Returns interactive recovery scenarios available for live demonstration.",
)
def get_demo_scenarios(db: Session = Depends(get_db)) -> DemoScenarioListResponse:
    """List demo scenarios."""
    scenarios = DemoService.get_scenarios()
    return DemoScenarioListResponse(scenarios=scenarios)


@router.post(
    "/scenarios/{scenario_id}/run",
    response_model=DemoScenarioRunResponse,
    summary="Run an individual demo scenario",
    description="Executes a specific scenario (e.g. success, human_review, retry, failure, blocked, multi_channel).",
)
def run_demo_scenario(
    scenario_id: str,
    seed: int = Query(42, description="Random seed for deterministic scenario execution"),
    db: Session = Depends(get_db),
) -> DemoScenarioRunResponse:
    """Execute demo scenario."""
    return DemoService.run_scenario(db=db, scenario_id=scenario_id, seed=seed)
