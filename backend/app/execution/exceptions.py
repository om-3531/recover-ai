"""
Execution domain exceptions.
"""

from typing import Any, Optional

from app.core.exceptions import AppException


class ExecutionError(AppException):
    """Base exception for recovery execution errors."""

    def __init__(
        self,
        message: str = "An error occurred during recovery action execution",
        status_code: int = 400,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=status_code, details=details)


class ExecutionAuthorizationError(ExecutionError):
    """Raised when execution is attempted without proper approval or authorization."""

    def __init__(
        self,
        message: str = "Action execution is not authorized",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=400, details=details)


class ExecutionProviderError(ExecutionError):
    """Raised when an external channel provider fails during execution."""

    def __init__(
        self,
        message: str = "Execution provider failed to execute action",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=502, details=details)
