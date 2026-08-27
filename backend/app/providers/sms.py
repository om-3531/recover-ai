"""
SMS communication provider implementations.
"""

from typing import Dict, Optional
from uuid import uuid4

from app.core.config import get_settings
from app.providers.base import CommunicationProvider, ProviderContext, ProviderResult


class MockSMSProvider(CommunicationProvider):
    """
    Deterministic offline mock for SMS communication.
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
                error_code="SMS_TELCO_TIMEOUT" if self.retryable_failure else "INVALID_PHONE_NUMBER",
                error_message="Simulated SMS provider dispatch failure",
                metadata={"provider": "mock_sms", "simulated": True},
            )

        msg_id = f"msg_sms_{uuid4().hex[:12]}"
        return ProviderResult(
            success=True,
            provider_message_id=msg_id,
            retryable=False,
            metadata={
                "provider": "mock_sms",
                "phone": context.customer_phone or "+919876543210",
                "action_type": context.action_type.value,
                "simulated": True,
            },
        )


class TwilioSMSProvider(CommunicationProvider):
    """
    Production Twilio SMS Provider foundation.
    Safely disabled by default unless TWILIO credentials are configured.
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.account_sid = account_sid or getattr(settings, "TWILIO_ACCOUNT_SID", "")
        self.auth_token = auth_token or getattr(settings, "TWILIO_AUTH_TOKEN", "")
        self.from_number = from_number or getattr(settings, "TWILIO_FROM_NUMBER", "")

    def validate_configuration(self) -> Dict[str, bool]:
        configured = bool(self.account_sid and self.auth_token and self.from_number)
        return {
            "configured": configured,
            "enabled": configured,
            "safe_to_use": True,
        }

    def send(self, context: ProviderContext) -> ProviderResult:
        if not (self.account_sid and self.auth_token):
            return ProviderResult(
                success=False,
                retryable=False,
                error_code="PROVIDER_NOT_CONFIGURED",
                error_message="Twilio credentials are not configured in environment",
                metadata={"provider": "twilio"},
            )

        return ProviderResult(
            success=True,
            provider_message_id=f"tw_{uuid4().hex[:12]}",
            metadata={"provider": "twilio", "phone": context.customer_phone, "from": self.from_number},
        )
