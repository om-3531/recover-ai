"""
AI Provider abstraction and implementations.

Provides an abstract base interface and a deterministic MockAIProvider for offline testing.
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.ai.exceptions import AIProviderError
from app.ai.schemas import RawRecommendation, RecoveryContext
from app.core.config import get_settings
from app.models.enums import (
    RecoveryActionChannel,
    RecoveryActionType,
    RecoveryPriority,
    RiskStatus,
)


class AIProvider(ABC):
    """Abstract base class for all AI recommendation providers."""

    @abstractmethod
    def generate_recovery_recommendation(
        self, context: RecoveryContext
    ) -> RawRecommendation:
        """Analyze recovery context and return a structured raw recommendation."""
        raise NotImplementedError


class MockAIProvider(AIProvider):
    """
    Deterministic, offline AI provider implementation for local testing and fallback.
    Produces predictable recommendations based on risk, amount, and attempt history.
    """

    def __init__(
        self,
        force_failure: bool = False,
        override_recommendation: Optional[RawRecommendation] = None,
    ) -> None:
        self.force_failure = force_failure
        self.override_recommendation = override_recommendation

    def generate_recovery_recommendation(
        self, context: RecoveryContext
    ) -> RawRecommendation:
        if self.force_failure:
            raise AIProviderError("Simulated mock provider failure")

        if self.override_recommendation is not None:
            return self.override_recommendation

        # Deterministic heuristic decision tree based on context
        if context.recovery_case_risk_status in (
            RiskStatus.high,
            RiskStatus.critical,
        ):
            return RawRecommendation(
                recommended_action_type=RecoveryActionType.email_reminder,
                recommended_channel=RecoveryActionChannel.email,
                priority=RecoveryPriority.urgent,
                confidence=0.45,
                rationale="High-risk failure detected. Human supervisor review recommended before proceeding.",
                risk_flags=["HIGH_RISK_CASE", "MANUAL_APPROVAL_REQUIRED"],
                requires_human_review=True,
            )

        if context.action_count >= 2:
            return RawRecommendation(
                recommended_action_type=RecoveryActionType.payment_link,
                recommended_channel=RecoveryActionChannel.email,
                priority=RecoveryPriority.high,
                confidence=0.60,
                rationale=f"Multiple prior attempts recorded ({context.action_count}); recommending updated payment link.",
                risk_flags=["MULTIPLE_PRIOR_ATTEMPTS"],
                requires_human_review=False,
            )

        # Standard low / medium risk cases
        if context.payment_amount < 100000:  # < 1,000 INR
            return RawRecommendation(
                recommended_action_type=RecoveryActionType.payment_link,
                recommended_channel=RecoveryActionChannel.whatsapp,
                priority=RecoveryPriority.medium,
                confidence=0.88,
                rationale="Low-value transaction; recommending fast low-friction WhatsApp payment link.",
                risk_flags=[],
                requires_human_review=False,
            )

        return RawRecommendation(
            recommended_action_type=RecoveryActionType.payment_link,
            recommended_channel=RecoveryActionChannel.email,
            priority=RecoveryPriority.medium,
            confidence=0.82,
            rationale="Standard payment failure; recommending email payment link reminder.",
            risk_flags=[],
            requires_human_review=False,
        )


class GeminiAIProvider(AIProvider):
    """
    Provider implementation for Google Gemini API.
    Used when GEMINI_API_KEY is configured.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.GEMINI_API_KEY

    def generate_recovery_recommendation(
        self, context: RecoveryContext
    ) -> RawRecommendation:
        if not self.api_key:
            raise AIProviderError(
                "GEMINI_API_KEY is not configured. Use MockAIProvider for offline testing."
            )
        # Note: In future milestones, live Gemini SDK calls can be executed here.
        # Fallback to Mock provider logic for safety if API key is a test placeholder.
        return MockAIProvider().generate_recovery_recommendation(context)
