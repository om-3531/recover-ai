"""
Background job execution domain exceptions.
"""

from typing import Any, Optional

from app.core.exceptions import AppException


class JobError(AppException):
    """Base exception for execution job errors."""

    def __init__(
        self,
        message: str = "An error occurred during job execution",
        status_code: int = 500,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=status_code, details=details)


class JobNotFoundError(JobError):
    """Raised when a requested execution job is not found."""

    def __init__(
        self,
        message: str = "Execution job not found",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=404, details=details)


class JobStateError(JobError):
    """Raised when an invalid operation is attempted on a job's current state."""

    def __init__(
        self,
        message: str = "Invalid job state transition",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=400, details=details)


class JobExecutionError(JobError):
    """Raised when job execution fails permanently."""

    def __init__(
        self,
        message: str = "Execution job failed",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=502, details=details)
