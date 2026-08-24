"""
AI Decision Engine and Policy exceptions.
"""

from typing import Any, Optional

from app.core.exceptions import AppException


class AIError(AppException):
    """Base exception for AI-related operations."""

    def __init__(
        self,
        message: str = "An error occurred in the AI decision layer",
        status_code: int = 500,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=status_code, details=details)


class AIProviderError(AIError):
    """Raised when an external or local AI provider fails to generate a response."""

    def __init__(
        self,
        message: str = "AI provider failed to generate recommendation",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=502, details=details)


class AIPolicyBlockedError(AIError):
    """Raised when a recovery case is blocked from AI evaluation by deterministic policy."""

    def __init__(
        self,
        message: str = "Case evaluation blocked by safety policy",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=400, details=details)


class AIOutputValidationError(AIError):
    """Raised when raw AI output violates structural or confidence validation rules."""

    def __init__(
        self,
        message: str = "AI output failed structural validation",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=422, details=details)
