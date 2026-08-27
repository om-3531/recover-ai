"""
Communication provider domain exceptions.
"""

from typing import Any, Optional

from app.core.exceptions import AppException


class ProviderError(AppException):
    """Base exception for communication provider errors."""

    def __init__(
        self,
        message: str = "A provider error occurred",
        status_code: int = 502,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=status_code, details=details)


class ProviderConfigurationError(ProviderError):
    """Raised when a communication provider is missing required credentials/configuration."""

    def __init__(
        self,
        message: str = "Provider is not configured properly",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=500, details=details)


class ProviderDispatchError(ProviderError):
    """Raised when a communication provider fails to dispatch a message."""

    def __init__(
        self,
        message: str = "Failed to dispatch recovery message via provider",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message=message, status_code=502, details=details)
