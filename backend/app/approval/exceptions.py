"""
Approval domain exceptions.
"""

from typing import Any, Optional

from app.core.exceptions import AppException


class ApprovalError(AppException):
    """Base exception for recovery approval errors."""

    def __init__(
        self,
        message: str = "An error occurred in the recovery approval layer",
        status_code: int = 400,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=status_code, details=details)


class ApprovalPolicyBlockedError(ApprovalError):
    """Raised when an approval request violates safety or business policies."""

    def __init__(
        self,
        message: str = "Approval request blocked by policy",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=400, details=details)


class ApprovalNotFoundError(ApprovalError):
    """Raised when a recovery approval is not found."""

    def __init__(
        self,
        message: str = "Recovery approval not found",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=404, details=details)


class ApprovalStateError(ApprovalError):
    """Raised when attempting an invalid state transition on an approval record."""

    def __init__(
        self,
        message: str = "Invalid approval status transition",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=400, details=details)
