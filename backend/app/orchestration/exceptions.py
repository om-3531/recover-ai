"""
Orchestration domain exceptions.
"""

from typing import Any, Optional

from app.core.exceptions import AppException


class OrchestrationError(AppException):
    """Base exception for recovery orchestration errors."""

    def __init__(
        self,
        message: str = "An error occurred during recovery orchestration",
        status_code: int = 400,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=status_code, details=details)


class OrchestrationBlockedError(OrchestrationError):
    """Raised when an orchestration workflow is blocked by policy or terminal state."""

    def __init__(
        self,
        message: str = "Recovery orchestration blocked",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=400, details=details)


class OrchestrationStateError(OrchestrationError):
    """Raised when an invalid case state transition occurs during orchestration."""

    def __init__(
        self,
        message: str = "Invalid recovery orchestration state",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=400, details=details)
