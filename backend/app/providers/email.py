"""
Email communication provider implementations.
"""

from typing import Dict, List, Optional
from uuid import uuid4

from app.core.config import get_settings
from app.providers.base import CommunicationProvider, ProviderContext, ProviderResult


class MockEmailProvider(CommunicationProvider):
    """
    Deterministic offline mock for email communication.
    Performs zero real network requests.
    """

    def __init__(
        self,
        force_failure: bool = False,
        retryable_failure: bool = False,
    ) -> None:
        self.force_failure = force_failure
        self.retryable_failure = retryable_failure

    def validate_configuration(self) -> Dict[str, bool]:
        return {"configured": True, "enabled": True, "safe_to_use": True}

    def send(self, context: ProviderContext) -> ProviderResult:
        if self.force_failure:
            return ProviderResult(
                success=False,
                provider_message_id=None,
                retryable=self.retryable_failure,
                error_code="EMAIL_GATEWAY_TIMEOUT" if self.retryable_failure else "INVALID_EMAIL_ADDRESS",
                error_message="Simulated email provider dispatch failure",
                metadata={"provider": "mock_email", "simulated": True},
            )

        msg_id = f"msg_email_{uuid4().hex[:12]}"
        return ProviderResult(
            success=True,
            provider_message_id=msg_id,
            retryable=False,
            metadata={
                "provider": "mock_email",
                "recipient": context.customer_email or "customer@example.com",
                "action_type": context.action_type.value,
                "simulated": True,
            },
        )


class SendGridEmailProvider(CommunicationProvider):
    """
    Production SendGrid Email Provider foundation.
    Safely disabled by default unless SENDGRID_API_KEY is configured.
    """

    def __init__(self, api_key: Optional[str] = None, from_email: Optional[str] = None) -> None:
        settings = get_settings()
        self.api_key = api_key or getattr(settings, "SENDGRID_API_KEY", "")
        self.from_email = from_email or getattr(settings, "SENDGRID_FROM_EMAIL", "noreply@recoverai.example")

    def validate_configuration(self) -> Dict[str, bool]:
        configured = bool(self.api_key and self.from_email)
        return {
            "configured": configured,
            "enabled": configured,
            "safe_to_use": True,
        }

    def send(self, context: ProviderContext) -> ProviderResult:
        if not self.api_key:
            return ProviderResult(
                success=False,
                retryable=False,
                error_code="PROVIDER_NOT_CONFIGURED",
                error_message="SendGrid API key is not configured in environment",
                metadata={"provider": "sendgrid"},
            )

        return ProviderResult(
            success=True,
            provider_message_id=f"sg_{uuid4().hex[:12]}",
            metadata={"provider": "sendgrid", "recipient": context.customer_email, "from": self.from_email},
        )
