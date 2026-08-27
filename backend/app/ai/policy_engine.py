"""
Deterministic Policy Engine for AI Recovery Decisions.

Executes safety, business, and compliance checks before and after AI recommendation generation.
Guarantees that AI recommendations cannot bypass business limits or terminal states.
"""

from typing import Optional

from app.ai.schemas import PolicyDecision, RawRecommendation, RecoveryContext
from app.models.enums import (
    RecoveryActionType,
    RecoveryCaseState,
    RevenueStatus,
    RiskStatus,
)
from app.policy.schemas import MerchantPolicyBase


class PolicyEngine:
    """Deterministic policy rules evaluator with merchant policy support."""

    @staticmethod
    def evaluate_pre_policy(
        context: RecoveryContext,
        merchant_policy: Optional[MerchantPolicyBase] = None,
    ) -> PolicyDecision:
        """
        Evaluate deterministic policies BEFORE calling the AI provider.

        Blocks evaluation for terminal states, zero recoverable balances, resolved revenue,
        or merchant policy boundary violations.
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

        # Rule 4: Merchant Policy Amount Boundaries
        if merchant_policy is not None:
            if context.recoverable_amount < merchant_policy.min_recovery_amount_paise:
                return PolicyDecision(
                    allowed=False,
                    requires_human_review=False,
                    reason=f"Recoverable amount ({context.recoverable_amount} paise) is below merchant minimum threshold ({merchant_policy.min_recovery_amount_paise} paise).",
                    blocked_actions=list(RecoveryActionType),
                    warnings=["Below minimum recovery amount"],
                )
            if context.recoverable_amount > merchant_policy.max_recovery_amount_paise:
                return PolicyDecision(
                    allowed=False,
                    requires_human_review=False,
                    reason=f"Recoverable amount ({context.recoverable_amount} paise) exceeds merchant maximum limit ({merchant_policy.max_recovery_amount_paise} paise).",
                    blocked_actions=list(RecoveryActionType),
                    warnings=["Exceeds maximum recovery amount"],
                )
            if context.action_count >= merchant_policy.max_attempts:
                return PolicyDecision(
                    allowed=False,
                    requires_human_review=False,
                    reason=f"Maximum recovery attempts reached ({context.action_count}/{merchant_policy.max_attempts}).",
                    blocked_actions=list(RecoveryActionType),
                    warnings=["Max attempts reached"],
                )

        # Base allowed decision
        requires_human_review = False
        if merchant_policy:
            if context.recovery_case_risk_status == RiskStatus.high and merchant_policy.require_approval_for_high_risk:
                requires_human_review = True
            if context.recovery_case_risk_status == RiskStatus.critical and merchant_policy.require_approval_for_critical_risk:
                requires_human_review = True
            if context.recoverable_amount >= merchant_policy.human_review_threshold_paise:
                requires_human_review = True
        else:
            if context.recovery_case_risk_status in (RiskStatus.high, RiskStatus.critical):
                requires_human_review = True

        warnings: list[str] = []
        if requires_human_review:
            warnings.append(
                f"Case has {context.recovery_case_risk_status.value} risk status or exceeds human review threshold. Supervisor approval required before execution."
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
        merchant_policy: Optional[MerchantPolicyBase] = None,
    ) -> PolicyDecision:
        """
        Evaluate deterministic safety rules on the raw AI recommendation.

        Enforces mandatory human review for high-risk cases and blocks excessive retries
        or actions forbidden by merchant policy.
        """
        blocked_actions = list(pre_policy.blocked_actions)
        warnings = list(pre_policy.warnings)
        requires_human_review = (
            pre_policy.requires_human_review or raw_rec.requires_human_review
        )

        # Rule 5: Mandatory human review on high/critical risk cases (configurable)
        if merchant_policy:
            if context.recovery_case_risk_status == RiskStatus.high and merchant_policy.require_approval_for_high_risk:
                requires_human_review = True
                if "Supervisor approval required before execution." not in warnings:
                    warnings.append(
                        "High-risk case requires human supervisor authorization (policy: require_approval_for_high_risk)."
                    )
            if context.recovery_case_risk_status == RiskStatus.critical and merchant_policy.require_approval_for_critical_risk:
                requires_human_review = True
                if "Supervisor approval required before execution." not in warnings:
                    warnings.append(
                        "Critical-risk case requires human supervisor authorization (policy: require_approval_for_critical_risk)."
                    )
        else:
            if context.recovery_case_risk_status in (RiskStatus.high, RiskStatus.critical):
                requires_human_review = True
                if "Supervisor approval required before execution." not in warnings:
                    warnings.append(
                        "High/Critical risk case requires human supervisor authorization."
                    )

        # Rule 6: Limit repeated automated payment retries
        max_retries = merchant_policy.max_attempts if merchant_policy else 3
        if (
            raw_rec.recommended_action_type == RecoveryActionType.retry_payment
            and context.action_count >= max_retries
        ):
            if RecoveryActionType.retry_payment not in blocked_actions:
                blocked_actions.append(RecoveryActionType.retry_payment)
            warnings.append(
                f"Automated retry limit reached (>={max_retries} attempts). Direct retries are blocked."
            )

        # Rule 7: Merchant Policy Channel & Review Restrictions
        if merchant_policy is not None:
            if context.recoverable_amount >= merchant_policy.human_review_threshold_paise:
                requires_human_review = True
                warnings.append(
                    f"Recoverable amount ({context.recoverable_amount} paise) meets or exceeds merchant human review threshold ({merchant_policy.human_review_threshold_paise} paise)."
                )

            if raw_rec.recommended_channel:
                allowed_channels = [c.lower() for c in merchant_policy.allowed_channels]
                if raw_rec.recommended_channel.value.lower() not in allowed_channels:
                    if raw_rec.recommended_action_type and raw_rec.recommended_action_type not in blocked_actions:
                        blocked_actions.append(raw_rec.recommended_action_type)
                    warnings.append(
                        f"Recommended channel '{raw_rec.recommended_channel.value}' is disabled by merchant policy."
                    )

            if not merchant_policy.webhook_enabled and raw_rec.recommended_action_type == RecoveryActionType.webhook_ping:
                if RecoveryActionType.webhook_ping not in blocked_actions:
                    blocked_actions.append(RecoveryActionType.webhook_ping)
                warnings.append("Webhook action disabled by merchant policy.")

        return PolicyDecision(
            allowed=pre_policy.allowed,
            requires_human_review=requires_human_review,
            reason="Policy evaluation completed successfully.",
            blocked_actions=blocked_actions,
            warnings=warnings,
        )

