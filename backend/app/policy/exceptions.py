"""
Domain exceptions for Merchant Policy module.
"""

from app.core.exceptions import AppException


class PolicyError(AppException):
    """Base exception for policy errors."""

    def __init__(self, message: str, status_code: int = 400, details: dict = None) -> None:
        super().__init__(message=message, status_code=status_code, details=details)


class PolicyNotFoundError(PolicyError):
    """Raised when a requested policy is not found."""

    def __init__(self, message: str = "Merchant policy not found") -> None:
        super().__init__(message=message, status_code=404)


class PolicyValidationError(PolicyError):
    """Raised when policy parameters fail logical or financial validation."""

    def __init__(self, message: str, details: dict = None) -> None:
        super().__init__(message=message, status_code=422, details=details)


class PolicyEvaluationError(PolicyError):
    """Raised when an error occurs during policy evaluation."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, status_code=500)
