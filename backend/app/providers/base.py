"""
Base models and abstract interface for communication providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RecoveryActionChannel, RecoveryActionType


class ProviderContext(BaseModel):
    """Sanitized context passed to a communication provider for dispatch."""

    recovery_case_id: int
    revenue_record_id: Optional[int] = None
    payment_id: Optional[int] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    amount: Optional[int] = None  # in paise
    currency: Optional[str] = "INR"
    action_type: RecoveryActionType
    channel: RecoveryActionChannel
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore", protected_namespaces=())


class ProviderResult(BaseModel):
    """Structured execution output returned by a communication provider."""

    success: bool
    provider_message_id: Optional[str] = None
    retryable: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore", protected_namespaces=())


class CommunicationProvider(ABC):
    """Abstract base class for all external communication providers."""

    @abstractmethod
    def send(self, context: ProviderContext) -> ProviderResult:
        """
        Dispatch a recovery intervention through this provider channel.

        Must return a structured ProviderResult and never raise unhandled exceptions.
        """
        pass
