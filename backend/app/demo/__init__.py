"""
RecoverAI Demo and Synthetic Dataset Generation Package.
"""

from app.demo.exceptions import DemoError, DemoModeDisabledError
from app.demo.generator import generate_synthetic_dataset, reset_database_records
from app.demo.scenarios import list_available_scenarios, run_scenario
from app.demo.schemas import (
    DemoResetResponse,
    DemoScenarioInfo,
    DemoScenarioListResponse,
    DemoScenarioRunResponse,
    DemoSeedRequest,
    DemoSeedResponse,
)
from app.demo.service import DemoService

__all__ = [
    "DemoError",
    "DemoModeDisabledError",
    "DemoService",
    "DemoSeedRequest",
    "DemoSeedResponse",
    "DemoResetResponse",
    "DemoScenarioInfo",
    "DemoScenarioListResponse",
    "DemoScenarioRunResponse",
    "generate_synthetic_dataset",
    "reset_database_records",
    "list_available_scenarios",
    "run_scenario",
]
