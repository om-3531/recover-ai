"""
DemoService application layer.

Guards demo functionality with DEMO_MODE configuration and coordinates synthetic data seeding.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.demo.exceptions import DemoModeDisabledError
from app.demo.generator import generate_synthetic_dataset, reset_database_records
from app.demo.scenarios import list_available_scenarios, run_scenario
from app.demo.schemas import (
    DemoResetResponse,
    DemoScenarioInfo,
    DemoScenarioRunResponse,
    DemoSeedResponse,
)

settings = get_settings()


class DemoService:
    """Service for managing demo data generation, scenarios, and environment resets."""

    @classmethod
    def _verify_demo_mode(cls) -> None:
        """Ensures demo operations cannot be executed when DEMO_MODE is disabled."""
        if not settings.DEMO_MODE:
            raise DemoModeDisabledError()

    @classmethod
    def seed_data(
        cls,
        db: Session,
        count: int = 50,
        seed: int = 42,
        scenario: Optional[str] = "all",
        reset: bool = False,
    ) -> DemoSeedResponse:
        """Seeds a synthetic dataset or runs a specific demo scenario."""
        cls._verify_demo_mode()
        if scenario and scenario != "all":
            run_scenario(db, scenario, seed=seed)
        return generate_synthetic_dataset(db, count=count, seed=seed, reset=reset)

    @classmethod
    def reset_data(cls, db: Session) -> DemoResetResponse:
        """Purges demo database records."""
        cls._verify_demo_mode()
        return reset_database_records(db)

    @classmethod
    def get_scenarios(cls) -> List[DemoScenarioInfo]:
        """Returns the list of available interactive demo scenarios."""
        return list_available_scenarios()

    @classmethod
    def run_scenario(cls, db: Session, scenario_id: str, seed: int = 42) -> DemoScenarioRunResponse:
        """Runs an individual end-to-end recovery scenario."""
        cls._verify_demo_mode()
        return run_scenario(db, scenario_id=scenario_id, seed=seed)
