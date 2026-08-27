"""
Recovery Decision Engine orchestrator.

Coordinates recovery context assembly, deterministic policy evaluation,
AI recommendation generation, safety validation, and audit logging.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.policy_engine import PolicyEngine
from app.ai.provider import AIProvider, MockAIProvider
from app.ai.schemas import RecoveryContext, RecoveryRecommendation
from app.core.exceptions import NotFoundError
from app.core.metrics import metrics
from app.models.payment import Payment
from app.models.recovery import RecoveryCase
from app.models.revenue import RevenueRecord
from app.policy.schemas import MerchantPolicyBase
from app.policy.service import PolicyService
from app.services.audit_service import AuditService




class RecoveryDecisionEngine:
    """Orchestrates AI recovery recommendations with strict policy controls."""

    @classmethod
    def _build_context(cls, db: Session, case: RecoveryCase) -> RecoveryContext:
        """Construct sanitized RecoveryContext from RecoveryCase and linked financial models."""
        revenue: Optional[RevenueRecord] = case.revenue_record
        payment: Optional[Payment] = revenue.payment if revenue else None

        last_action = case.actions[-1] if case.actions else None

        return RecoveryContext(
            recovery_case_id=case.id,
            revenue_record_id=case.revenue_record_id,
            payment_id=payment.id if payment else None,
            razorpay_payment_id=payment.razorpay_payment_id if payment else None,
            payment_amount=payment.amount if payment else (revenue.gross_amount if revenue else 0),
            currency=payment.currency if payment else (revenue.currency if revenue else "INR"),
            payment_status=payment.status if payment else None,
            revenue_status=revenue.status if revenue else None,
            recoverable_amount=revenue.recoverable_amount if revenue else 0,
            recovery_case_reason=case.reason,
            recovery_case_priority=case.priority,
            recovery_case_risk_status=case.risk_status,
            recovery_case_current_state=case.current_state,
            action_count=len(case.actions),
            last_action_type=last_action.action_type if last_action else None,
            last_action_channel=last_action.channel if last_action else None,
            last_action_status=last_action.status if last_action else None,
        )

    @classmethod
    def generate_decision(
        cls,
        db: Session,
        case_id: int,
        provider: Optional[AIProvider] = None,
        actor: str = "ai_decision_engine",
    ) -> RecoveryRecommendation:
        """
        Generate a validated, policy-checked recovery recommendation for a recovery case.

        Guarantees:
        1. Emits audit log before and after evaluation.
        2. Blocks cases in terminal states or with zero recoverable amount.
        3. Never mutates Payment or executes RecoveryAction directly.
        """
        # Step 1: Fetch RecoveryCase with relations
        query = (
            select(RecoveryCase)
            .options(
                selectinload(RecoveryCase.actions),
                selectinload(RecoveryCase.revenue_record).selectinload(RevenueRecord.payment),
            )
            .where(RecoveryCase.id == case_id)
        )
        case = db.scalar(query)
        if case is None:
            raise NotFoundError(f"RecoveryCase with id {case_id} not found")

        # Step 2: Audit request
        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_case",
            entity_id=str(case_id),
            action="ai_recovery_decision_requested",
            actor=actor,
            metadata={"case_id": case_id},
        )

        # Step 3: Build sanitized context & fetch active merchant policy
        context = cls._build_context(db, case)
        merchant_policy_orm = PolicyService.get_or_create_default_policy(db)
        merchant_policy = MerchantPolicyBase(
            high_risk_threshold_paise=merchant_policy_orm.high_risk_threshold_paise,
            critical_risk_threshold_paise=merchant_policy_orm.critical_risk_threshold_paise,
            human_review_threshold_paise=merchant_policy_orm.human_review_threshold_paise,
            auto_execute_low_risk=merchant_policy_orm.auto_execute_low_risk,
            max_attempts=merchant_policy_orm.max_attempts,
            backoff_base_seconds=merchant_policy_orm.backoff_base_seconds,
            allowed_channels=merchant_policy_orm.allowed_channels,
            preferred_channel=merchant_policy_orm.preferred_channel,
            min_recovery_amount_paise=merchant_policy_orm.min_recovery_amount_paise,
            max_recovery_amount_paise=merchant_policy_orm.max_recovery_amount_paise,
            require_approval_for_high_risk=merchant_policy_orm.require_approval_for_high_risk,
            require_approval_for_critical_risk=merchant_policy_orm.require_approval_for_critical_risk,
            webhook_enabled=merchant_policy_orm.webhook_enabled,
            is_active=merchant_policy_orm.is_active,
        )

        # Step 4: Pre-policy evaluation
        pre_policy = PolicyEngine.evaluate_pre_policy(context, merchant_policy=merchant_policy)
        if not pre_policy.allowed:
            metrics.increment("policy_blocks_total")
            rec = RecoveryRecommendation(
                recovery_case_id=case_id,
                recommended_action_type=None,
                recommended_channel=None,
                priority=case.priority,
                confidence=0.0,
                rationale=pre_policy.reason,
                risk_flags=["POLICY_BLOCKED"],
                requires_human_review=False,
                policy_decision=pre_policy,
                is_blocked=True,
                provider="policy_engine",
                model_name="deterministic_rules_v1",
            )
            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_case",
                entity_id=str(case_id),
                action="ai_recovery_decision_blocked",
                actor=actor,
                metadata={"reason": pre_policy.reason, "policy_id": merchant_policy_orm.id},
            )
            db.commit()
            return rec

        # Step 5: Call AI Provider
        metrics.increment("ai_decisions_total")
        ai_provider = provider or MockAIProvider()
        raw_rec = ai_provider.generate_recovery_recommendation(context)

        # Step 6: Post-policy evaluation
        final_policy = PolicyEngine.evaluate_post_policy(
            context=context,
            raw_rec=raw_rec,
            pre_policy=pre_policy,
            merchant_policy=merchant_policy,
        )

        # Step 7: Build final recommendation
        is_action_blocked = (
            raw_rec.recommended_action_type in final_policy.blocked_actions
        )
        if is_action_blocked:
            metrics.increment("policy_blocks_total")
            AuditService.create_audit_log(
                db=db,
                entity_type="recovery_case",
                entity_id=str(case_id),
                action="policy_override_prevented",
                actor="policy_engine",
                metadata={
                    "recommended_action": (
                        raw_rec.recommended_action_type.value
                        if raw_rec.recommended_action_type
                        else None
                    ),
                    "recommended_channel": (
                        raw_rec.recommended_channel.value
                        if raw_rec.recommended_channel
                        else None
                    ),
                    "warnings": final_policy.warnings,
                },
            )

        final_action_type = (
            None if is_action_blocked else raw_rec.recommended_action_type
        )
        final_channel = None if is_action_blocked else raw_rec.recommended_channel

        rec = RecoveryRecommendation(
            recovery_case_id=case_id,
            recommended_action_type=final_action_type,
            recommended_channel=final_channel,
            priority=raw_rec.priority,
            confidence=raw_rec.confidence,
            rationale=raw_rec.rationale,
            risk_flags=raw_rec.risk_flags,
            requires_human_review=final_policy.requires_human_review,
            policy_decision=final_policy,
            is_blocked=is_action_blocked,
            provider="mock" if isinstance(ai_provider, MockAIProvider) else "gemini",
            model_name="mock-decision-v1",
        )

        # Step 8: Audit generated decision
        AuditService.create_audit_log(
            db=db,
            entity_type="recovery_case",
            entity_id=str(case_id),
            action="ai_recovery_decision_generated",
            actor=actor,
            metadata={
                "recommendation_id": rec.recommendation_id,
                "action_type": (
                    rec.recommended_action_type.value
                    if rec.recommended_action_type
                    else None
                ),
                "channel": (
                    rec.recommended_channel.value
                    if rec.recommended_channel
                    else None
                ),
                "confidence": rec.confidence,
                "requires_human_review": rec.requires_human_review,
                "is_blocked": rec.is_blocked,
            },
        )
        db.commit()
        return rec

