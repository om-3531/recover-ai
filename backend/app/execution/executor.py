"""
Abstract base class for Recovery Action Executors.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.execution.schemas import ExecutionResult
from app.models.enums import RecoveryActionChannel, RecoveryActionType


class RecoveryExecutor(ABC):
    """Abstract interface for executing approved recovery interventions."""

    @abstractmethod
    def execute(
        self,
        action_type: RecoveryActionType,
        channel: RecoveryActionChannel,
        context: dict[str, Any],
    ) -> ExecutionResult:
        """Execute an approved recovery action across the specified channel."""
        raise NotImplementedError
