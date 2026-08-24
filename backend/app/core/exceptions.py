"""
Domain and application exceptions for RecoverAI.

These exceptions represent business logic errors and are translated
into consistent HTTP responses by FastAPI exception handlers.
"""

from typing import Any, Optional


class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, status_code: int = 400, details: Optional[Any] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class NotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None) -> None:
        super().__init__(message=message, status_code=404, details=details)


class ConflictError(AppException):
    """Raised when an operation conflicts with existing resource state (e.g. duplicate key)."""

    def __init__(self, message: str = "Resource conflict", details: Optional[Any] = None) -> None:
        super().__init__(message=message, status_code=409, details=details)


class BadRequestError(AppException):
    """Raised when an operation violates a business rule."""

    def __init__(self, message: str = "Bad request", details: Optional[Any] = None) -> None:
        super().__init__(message=message, status_code=400, details=details)


class InvalidStateTransitionError(BadRequestError):
    """Raised when a recovery case or entity attempts an illegal state transition."""

    def __init__(self, current_state: str, target_state: str, details: Optional[Any] = None) -> None:
        message = f"Cannot transition from '{current_state}' to '{target_state}'"
        super().__init__(message=message, details=details)
