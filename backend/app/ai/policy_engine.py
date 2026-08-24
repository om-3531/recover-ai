"""
Deterministic Policy Engine for AI Recovery Decisions.

Executes safety, business, and compliance checks before and after AI recommendation generation.
Guarantees that AI recommendations cannot bypass business limits or terminal states.
"""

from app.ai.schemas import PolicyDecision, RawRecommendation, RecoveryContext
from app.models.enums import (
    RecoveryActionType,
    RecoveryCaseState,
    RevenueStatus,
    RiskStatus,
)


class PolicyEngine:
    """Deterministic policy rules evaluator."""

    @staticmethod
    def evaluate_pre_policy(context: RecoveryContext) -> PolicyDecision:
        """
        Evaluate deterministic policies BEFORE calling the AI provider.

        Blocks evaluation for terminal states, zero recoverable balances, or resolved revenue.
        """
        # Rule 1: Terminal case states
        if context.recovery_case_current_state in (
            RecoveryCaseState.recovered,
            RecoveryCaseState.closed,
        ):
            return PolicyDecision(
                allowed=False,
                requires_human_review=False,
                reason=f"RecoveryCase is in '{context.recovery_case_current_state.value}' state. No recovery action permitted.",
                blocked_actions=list(RecoveryActionType),
                warnings=[],
            )

        # Rule 2: Zero recoverable balance
        if context.recoverable_amount <= 0:
            return PolicyDecision(
                allowed=False,
                requires_human_review=False,
                reason="Recoverable amount is 0 paise. No revenue is currently at risk.",
                blocked_actions=list(RecoveryActionType),
                warnings=[],
            )

        # Rule 3: Revenue record already recognized or recovered
        if context.revenue_status in (
            RevenueStatus.recognized,
            RevenueStatus.recovered,
        ):
            return PolicyDecision(
                allowed=False,
                requires_human_review=False,
                reason=f"RevenueRecord status is '{context.revenue_status.value}'. No recovery required.",
                blocked_actions=list(RecoveryActionType),
                warnings=[],
            )

        # Base allowed decision
        requires_human_review = context.recovery_case_risk_status in (
            RiskStatus.high,
            RiskStatus.critical,
        )
        warnings: list[str] = []
        if requires_human_review:
            warnings.append(
                f"Case has {context.recovery_case_risk_status.value} risk status. Supervisor approval required before execution."
            )

        return PolicyDecision(
            allowed=True,
            requires_human_review=requires_human_review,
            reason="Pre-policy checks passed.",
            blocked_actions=[],
            warnings=warnings,
        )

    @staticmethod
    def evaluate_post_policy(
        context: RecoveryContext,
        raw_rec: RawRecommendation,
        pre_policy: PolicyDecision,
    ) -> PolicyDecision:
        """
        Evaluate deterministic safety rules on the raw AI recommendation.

        Enforces mandatory human review for high-risk cases and blocks excessive retries.
        """
        blocked_actions = list(pre_policy.blocked_actions)
        warnings = list(pre_policy.warnings)
        requires_human_review = (
            pre_policy.requires_human_review or raw_rec.requires_human_review
        )

        # Rule 4: Mandatory human review on high/critical risk cases
        if context.recovery_case_risk_status in (
            RiskStatus.high,
            RiskStatus.critical,
        ):
            requires_human_review = True
            if "Supervisor approval required before execution." not in warnings:
                warnings.append(
                    "High/Critical risk case requires human supervisor authorization."
                )

        # Rule 5: Limit repeated automated payment retries
        if (
            raw_rec.recommended_action_type == RecoveryActionType.retry_payment
            and context.action_count >= 3
        ):
            blocked_actions.append(RecoveryActionType.retry_payment)
            warnings.append(
                "Automated retry limit reached (>=3 attempts). Direct retries are blocked."
            )

        return PolicyDecision(
            allowed=pre_policy.allowed,
            requires_human_review=requires_human_review,
            reason="Policy evaluation completed successfully.",
            blocked_actions=blocked_actions,
            warnings=warnings,
        )
