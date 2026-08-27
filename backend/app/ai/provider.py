"""
AI Provider abstraction and implementations.

Provides an abstract base interface and a deterministic MockAIProvider for offline testing,
plus an optional GeminiAIProvider for live AI recommendations via Google's Gemini API.
"""

from abc import ABC, abstractmethod
import json
import logging
from typing import Optional

import httpx

from app.ai.exceptions import AIOutputValidationError, AIProviderError
from app.ai.prompts import RECOVERY_DECISION_SYSTEM_INSTRUCTION, build_gemini_prompt
from app.ai.schemas import RawRecommendation, RecoveryContext
from app.core.config import get_settings
from app.core.metrics import metrics
from app.models.enums import (
    RecoveryActionChannel,
    RecoveryActionType,
    RecoveryPriority,
    RiskStatus,
)

logger = logging.getLogger(__name__)

_GEMINI_API_TIMEOUT = 15.0


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

    Calls the Gemini generateContent endpoint via httpx, validates the JSON response,
    and maps it to a RawRecommendation. On any failure (network, parse, validation),
    logs the error and falls back to MockAIProvider deterministically.

    Safety guarantees:
    - Never exposes API keys in logs, exceptions, or responses
    - Validates all output fields against enums and ranges
    - Clamps confidence to [0.0, 1.0]
    - Rejects malformed/unsafe output and falls back to mock
    - Does NOT bypass policy engine or approval gates
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.GEMINI_API_KEY or settings.AI_API_KEY
        self.model = settings.AI_MODEL or "gemini-1.5-flash"

    def _is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def _call_gemini(self, prompt: str) -> str:
        """Call the Gemini API and return the raw text response."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": RECOVERY_DECISION_SYSTEM_INSTRUCTION},
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 1024,
            },
        }

        with httpx.Client(timeout=_GEMINI_API_TIMEOUT) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise AIProviderError("Gemini returned no candidates")

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            raise AIProviderError("Gemini returned empty content parts")

        return parts[0].get("text", "")

    def _parse_and_validate(self, raw_text: str) -> RawRecommendation:
        """Parse Gemini JSON output and validate into a RawRecommendation."""
        # Strip markdown fences if present
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (fences)
            lines = lines[1:] if lines[0].startswith("```") else lines
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIOutputValidationError(
                f"Gemini returned invalid JSON: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise AIOutputValidationError("Gemini output is not a JSON object")

        # Validate and map action_type
        action_str = data.get("recommended_action_type", "")
        try:
            action_type = RecoveryActionType(action_str)
        except (ValueError, KeyError):
            raise AIOutputValidationError(
                f"Invalid recommended_action_type: {action_str}"
            )

        # Validate and map channel
        channel_str = data.get("recommended_channel", "")
        try:
            channel = RecoveryActionChannel(channel_str)
        except (ValueError, KeyError):
            raise AIOutputValidationError(
                f"Invalid recommended_channel: {channel_str}"
            )

        # Validate and map priority
        priority_str = data.get("priority", "medium")
        try:
            priority = RecoveryPriority(priority_str)
        except (ValueError, KeyError):
            priority = RecoveryPriority.medium

        # Clamp confidence to [0.0, 1.0]
        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        # Validate risk_flags
        risk_flags = data.get("risk_flags", [])
        if not isinstance(risk_flags, list):
            risk_flags = []

        return RawRecommendation(
            recommended_action_type=action_type,
            recommended_channel=channel,
            priority=priority,
            confidence=confidence,
            rationale=str(data.get("rationale", "Gemini recommendation")),
            risk_flags=[str(f) for f in risk_flags],
            requires_human_review=bool(data.get("requires_human_review", False)),
        )

    def generate_recovery_recommendation(
        self, context: RecoveryContext
    ) -> RawRecommendation:
        """
        Generate a recovery recommendation via Gemini API.

        On any failure (unconfigured, network, parse, validation), increments
        fallback metrics and falls back to MockAIProvider deterministically.
        """
        if not self._is_configured():
            metrics.increment("ai_provider_fallbacks_total")
            return MockAIProvider().generate_recovery_recommendation(context)

        metrics.increment("ai_provider_requests_total", value=1)

        try:
            context_dict = context.model_dump()
            prompt = build_gemini_prompt(context_dict)
            raw_text = self._call_gemini(prompt)
            recommendation = self._parse_and_validate(raw_text)
            metrics.increment("ai_provider_successes_total", value=1)
            return recommendation

        except (AIProviderError, AIOutputValidationError) as exc:
            logger.warning("Gemini provider failed, falling back to mock: %s", exc)
            metrics.increment("ai_provider_failures_total", value=1)
            metrics.increment("ai_provider_fallbacks_total", value=1)
            return MockAIProvider().generate_recovery_recommendation(context)

        except httpx.TimeoutException:
            logger.warning("Gemini API timed out, falling back to mock")
            metrics.increment("ai_provider_failures_total", value=1)
            metrics.increment("ai_provider_fallbacks_total", value=1)
            return MockAIProvider().generate_recovery_recommendation(context)

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Gemini API returned HTTP %s, falling back to mock",
                exc.response.status_code,
            )
            metrics.increment("ai_provider_failures_total", value=1)
            metrics.increment("ai_provider_fallbacks_total", value=1)
            return MockAIProvider().generate_recovery_recommendation(context)

        except Exception as exc:
            logger.warning("Unexpected Gemini error, falling back to mock: %s", exc)
            metrics.increment("ai_provider_failures_total", value=1)
            metrics.increment("ai_provider_fallbacks_total", value=1)
            return MockAIProvider().generate_recovery_recommendation(context)
