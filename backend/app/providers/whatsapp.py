"""
WhatsApp communication provider implementations.
"""

from typing import Dict, Optional
from uuid import uuid4

from app.core.config import get_settings
from app.providers.base import CommunicationProvider, ProviderContext, ProviderResult


class MockWhatsAppProvider(CommunicationProvider):
    """
    Deterministic offline mock for WhatsApp communication.
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
                error_code="WHATSAPP_SERVER_BUSY" if self.retryable_failure else "UNREGISTERED_WHATSAPP_USER",
                error_message="Simulated WhatsApp provider dispatch failure",
                metadata={"provider": "mock_whatsapp", "simulated": True},
            )

        msg_id = f"msg_wa_{uuid4().hex[:12]}"
        return ProviderResult(
            success=True,
            provider_message_id=msg_id,
            retryable=False,
            metadata={
                "provider": "mock_whatsapp",
                "phone": context.customer_phone or "+919876543210",
                "action_type": context.action_type.value,
                "simulated": True,
            },
        )


class MetaWhatsAppProvider(CommunicationProvider):
    """
    Production Meta WhatsApp Business Cloud API foundation.
    Safely disabled by default unless WHATSAPP credentials are configured.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.access_token = access_token or getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or getattr(settings, "META_WHATSAPP_TOKEN", "")
        self.phone_number_id = phone_number_id or getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")

    def validate_configuration(self) -> Dict[str, bool]:
        configured = bool(self.access_token and self.phone_number_id)
        return {
            "configured": configured,
            "enabled": configured,
            "safe_to_use": True,
        }

    def send(self, context: ProviderContext) -> ProviderResult:
        if not (self.access_token and self.phone_number_id):
            return ProviderResult(
                success=False,
                retryable=False,
                error_code="PROVIDER_NOT_CONFIGURED",
                error_message="Meta WhatsApp credentials are not configured in environment",
                metadata={"provider": "meta_whatsapp"},
            )

        return ProviderResult(
            success=True,
            provider_message_id=f"wamid_{uuid4().hex[:12]}",
            metadata={"provider": "meta_whatsapp", "phone": context.customer_phone},
        )
