"""
Mock Recovery Executor for deterministic testing and local execution.
"""

from typing import Any, Optional

from app.execution.executor import RecoveryExecutor
from app.execution.schemas import ExecutionResult
from app.models.enums import (
    RecoveryActionChannel,
    RecoveryActionStatus,
    RecoveryActionType,
)


class MockRecoveryExecutor(RecoveryExecutor):
    """
    Deterministic mock executor simulating channel interventions.
    Does NOT make live network calls or perform real financial transactions.
    """

    def __init__(
        self,
        force_failure: bool = False,
        retryable_failure: bool = False,
        custom_message: Optional[str] = None,
    ) -> None:
        self.force_failure = force_failure
        self.retryable_failure = retryable_failure
        self.custom_message = custom_message

    def execute(
        self,
        action_type: RecoveryActionType,
        channel: RecoveryActionChannel,
        context: dict[str, Any],
    ) -> ExecutionResult:
        """Simulate channel execution with mock result."""
        if self.force_failure:
            return ExecutionResult(
                success=False,
                action_type=action_type,
                channel=channel,
                status=RecoveryActionStatus.failed,
                message=self.custom_message or f"Mock execution failed for {channel.value}",
                retryable=self.retryable_failure,
                error_code="PROVIDER_ERROR" if self.retryable_failure else "PERMANENT_ERROR",
                metadata={"context_case_id": context.get("recovery_case_id")},
            )

        return ExecutionResult(
            success=True,
            action_type=action_type,
            channel=channel,
            status=RecoveryActionStatus.executed,
            message=(
                self.custom_message
                or f"Mock {action_type.value} successfully dispatched via {channel.value}"
            ),
            retryable=False,
            metadata={
                "context_case_id": context.get("recovery_case_id"),
                "simulated_channel": channel.value,
            },
        )
