"""
Pure functional rules engine for Merchant Policy validation and evaluation.
"""

from typing import List, Tuple
from app.policy.schemas import (
    MerchantPolicyBase,
    PolicyEvaluationContext,
    PolicyEvaluationResult,
    PolicyValidationResult,
)

VALID_CHANNELS = {"email", "sms", "whatsapp", "webhook"}


def format_rupees(paise: int) -> str:
    """Format integer paise to human-readable Indian Rupee string."""
    rupees = paise / 100
    return f"₹{rupees:,.2f}"


def generate_policy_summary(policy: MerchantPolicyBase) -> str:
    """Generate a clean, professional human-readable summary of merchant policy rules."""
    channels_str = ", ".join([c.capitalize() for c in policy.allowed_channels]) or "None"
    auto_str = (
        f"Recoveries below {format_rupees(policy.human_review_threshold_paise)} may be auto-executed."
        if policy.auto_execute_low_risk
        else "Autonomous execution is disabled; all cases require approval."
    )
    return (
        f"{auto_str} "
        f"Transactions at or above {format_rupees(policy.human_review_threshold_paise)} require human review. "
        f"Active channels: {channels_str} (Default: {policy.preferred_channel.capitalize()}). "
        f"Max recovery attempts: {policy.max_attempts} with {policy.backoff_base_seconds}s backoff base. "
        f"Valid amount range: {format_rupees(policy.min_recovery_amount_paise)} to {format_rupees(policy.max_recovery_amount_paise)}."
    )


def validate_policy_rules(policy: MerchantPolicyBase) -> PolicyValidationResult:
    """
    Validates logical, financial, and relational consistency of policy rules.
    Returns structured errors and warnings.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Financial Boundaries
    if policy.min_recovery_amount_paise > policy.max_recovery_amount_paise:
        errors.append(
            f"Minimum recovery amount ({format_rupees(policy.min_recovery_amount_paise)}) "
            f"cannot exceed maximum recovery amount ({format_rupees(policy.max_recovery_amount_paise)})."
        )

    if policy.high_risk_threshold_paise > policy.critical_risk_threshold_paise:
        errors.append(
            f"High-risk threshold ({format_rupees(policy.high_risk_threshold_paise)}) "
            f"cannot exceed critical-risk threshold ({format_rupees(policy.critical_risk_threshold_paise)})."
        )

    # Channels Validation
    if not policy.allowed_channels:
        errors.append("At least one communication channel must be enabled.")

    for ch in policy.allowed_channels:
        if ch.lower() not in VALID_CHANNELS:
            errors.append(f"Invalid communication channel '{ch}'. Supported: {', '.join(VALID_CHANNELS)}.")

    if policy.allowed_channels and policy.preferred_channel.lower() not in [c.lower() for c in policy.allowed_channels]:
        errors.append(
            f"Preferred channel '{policy.preferred_channel}' must be included in the allowed channels list."
        )

    # Attempt & Backoff Boundaries
    if policy.max_attempts < 1 or policy.max_attempts > 10:
        errors.append("Max attempts must be between 1 and 10.")

    if policy.backoff_base_seconds < 1 or policy.backoff_base_seconds > 3600:
        errors.append("Backoff base seconds must be between 1 and 3600.")

    # Practical Warnings
    if policy.human_review_threshold_paise > policy.critical_risk_threshold_paise:
        warnings.append(
            "Human review threshold is higher than critical risk threshold. Critical cases will bypass human review."
        )

    summary = generate_policy_summary(policy) if not errors else None
    return PolicyValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        summary=summary,
    )


def evaluate_policy_against_context(
    policy: MerchantPolicyBase,
    context: PolicyEvaluationContext,
) -> PolicyEvaluationResult:
    """
    Evaluates a proposed recovery action against the merchant's configured policy.
    Ensures deterministic policy supremacy over AI recommendations.
    """
    warnings: List[str] = []
    blocked_actions: List[str] = []
    override_applied = False

    # 1. Check Amount Limits
    if context.amount_paise < policy.min_recovery_amount_paise:
        return PolicyEvaluationResult(
            allowed=False,
            requires_human_review=False,
            reason=f"Payment amount ({format_rupees(context.amount_paise)}) is below merchant minimum recovery threshold ({format_rupees(policy.min_recovery_amount_paise)}).",
            effective_channel=policy.preferred_channel,
            is_auto_executable=False,
            policy_override_applied=True,
            blocked_actions=["all"],
            warnings=[f"Amount below {format_rupees(policy.min_recovery_amount_paise)}"],
        )

    if context.amount_paise > policy.max_recovery_amount_paise:
        return PolicyEvaluationResult(
            allowed=False,
            requires_human_review=False,
            reason=f"Payment amount ({format_rupees(context.amount_paise)}) exceeds merchant maximum recovery limit ({format_rupees(policy.max_recovery_amount_paise)}).",
            effective_channel=policy.preferred_channel,
            is_auto_executable=False,
            policy_override_applied=True,
            blocked_actions=["all"],
            warnings=[f"Amount exceeds {format_rupees(policy.max_recovery_amount_paise)}"],
        )

    # 2. Check Attempt Limits
    if context.attempt_count >= policy.max_attempts:
        return PolicyEvaluationResult(
            allowed=False,
            requires_human_review=False,
            reason=f"Maximum recovery attempts reached ({context.attempt_count}/{policy.max_attempts}).",
            effective_channel=policy.preferred_channel,
            is_auto_executable=False,
            policy_override_applied=True,
            blocked_actions=["retry_payment", "all"],
            warnings=["Max attempt limit reached"],
        )

    # 3. Channel Validation & Fallback
    proposed_channel = context.channel.lower()
    allowed_channels_lower = [c.lower() for c in policy.allowed_channels]
    effective_channel = proposed_channel

    if proposed_channel not in allowed_channels_lower:
        override_applied = True
        effective_channel = policy.preferred_channel
        warnings.append(
            f"Proposed channel '{proposed_channel}' is disabled by merchant policy. Falling back to preferred channel '{effective_channel}'."
        )

    # 4. Human Review & Auto-Execution Determination
    requires_human_review = False
    if context.amount_paise >= policy.human_review_threshold_paise:
        requires_human_review = True
        warnings.append(
            f"Transaction amount ({format_rupees(context.amount_paise)}) meets or exceeds human review threshold ({format_rupees(policy.human_review_threshold_paise)})."
        )

    if context.risk_status.lower() in ("high", "critical"):
        requires_human_review = True
        warnings.append(f"High/Critical risk status ({context.risk_status}) mandates human review.")

    is_auto_executable = policy.auto_execute_low_risk and not requires_human_review

    return PolicyEvaluationResult(
        allowed=True,
        requires_human_review=requires_human_review,
        reason="Merchant policy checks passed.",
        effective_channel=effective_channel,
        is_auto_executable=is_auto_executable,
        policy_override_applied=override_applied,
        blocked_actions=blocked_actions,
        warnings=warnings,
    )
