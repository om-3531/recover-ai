"""
PolicyService business logic.

Manages the persistence, logical validation, default initialization,
and runtime evaluation of merchant-configurable recovery policies.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.metrics import metrics
from app.models.policy import MerchantPolicy
from app.policy.exceptions import PolicyNotFoundError, PolicyValidationError
from app.policy.rules import (
    evaluate_policy_against_context,
    generate_policy_summary,
    validate_policy_rules,
)
from app.policy.schemas import (
    MerchantPolicyBase,
    MerchantPolicyCreate,
    MerchantPolicyResponse,
    MerchantPolicyUpdate,
    PolicyEvaluationContext,
    PolicyEvaluationResult,
    PolicyValidationResult,
)
from app.services.audit_service import AuditService


class PolicyService:
    """Service for managing merchant recovery policy configurations."""

    DEFAULT_MERCHANT_ID = "merchant_default"

    @classmethod
    def get_or_create_default_policy(
        cls,
        db: Session,
        merchant_id: str = DEFAULT_MERCHANT_ID,
    ) -> MerchantPolicy:
        """Fetch the active policy for a merchant or create a standard factory default."""
        policy = db.scalar(
            select(MerchantPolicy).where(MerchantPolicy.merchant_id == merchant_id)
        )
        if policy is None:
            policy = MerchantPolicy(
                merchant_id=merchant_id,
                high_risk_threshold_paise=1000000,  # ₹10,000
                critical_risk_threshold_paise=5000000,  # ₹50,000
                human_review_threshold_paise=1000000,  # ₹10,000
                auto_execute_low_risk=True,
                max_attempts=3,
                backoff_base_seconds=30,
                allowed_channels=["email", "sms", "whatsapp", "webhook"],
                preferred_channel="email",
                min_recovery_amount_paise=10000,  # ₹100
                max_recovery_amount_paise=100000000,  # ₹10,00,000
                require_approval_for_high_risk=True,
                require_approval_for_critical_risk=True,
                webhook_enabled=True,
                is_active=True,
            )
            db.add(policy)
            db.flush()

            AuditService.create_audit_log(
                db=db,
                entity_type="merchant_policy",
                entity_id=str(policy.id),
                action="policy_created",
                actor="system",
                metadata={"merchant_id": merchant_id, "default": True},
            )
            db.commit()
            db.refresh(policy)

        return policy

    @classmethod
    def get_policy_by_id(cls, db: Session, policy_id: int) -> MerchantPolicy:
        """Retrieve policy record by primary ID."""
        policy = db.scalar(
            select(MerchantPolicy).where(MerchantPolicy.id == policy_id)
        )
        if policy is None:
            raise PolicyNotFoundError(f"Policy with id {policy_id} not found")
        return policy

    @classmethod
    def validate_policy_payload(
        cls,
        payload: MerchantPolicyBase,
    ) -> PolicyValidationResult:
        """Validate logical and financial boundaries on a policy payload."""
        result = validate_policy_rules(payload)
        if not result.valid:
            metrics.increment("policy_validation_failures_total")
        return result

    @classmethod
    def update_policy(
        cls,
        db: Session,
        policy_id: int,
        update_data: MerchantPolicyUpdate,
        actor: str = "merchant_admin",
    ) -> MerchantPolicy:
        """Update an existing policy with strict validation and audit trail."""
        policy = cls.get_policy_by_id(db, policy_id)

        # Build prospective updated model to validate
        current_dict = {
            "high_risk_threshold_paise": policy.high_risk_threshold_paise,
            "critical_risk_threshold_paise": policy.critical_risk_threshold_paise,
            "human_review_threshold_paise": policy.human_review_threshold_paise,
            "auto_execute_low_risk": policy.auto_execute_low_risk,
            "max_attempts": policy.max_attempts,
            "backoff_base_seconds": policy.backoff_base_seconds,
            "allowed_channels": policy.allowed_channels,
            "preferred_channel": policy.preferred_channel,
            "min_recovery_amount_paise": policy.min_recovery_amount_paise,
            "max_recovery_amount_paise": policy.max_recovery_amount_paise,
            "require_approval_for_high_risk": policy.require_approval_for_high_risk,
            "require_approval_for_critical_risk": policy.require_approval_for_critical_risk,
            "webhook_enabled": policy.webhook_enabled,
            "is_active": policy.is_active,
        }
        update_dict = update_data.model_dump(exclude_unset=True)
        current_dict.update(update_dict)

        prospective = MerchantPolicyBase(**current_dict)
        val_result = validate_policy_rules(prospective)
        if not val_result.valid:
            metrics.increment("policy_validation_failures_total")
            raise PolicyValidationError(
                message=f"Policy validation failed: {'; '.join(val_result.errors)}",
                details={"errors": val_result.errors, "warnings": val_result.warnings},
            )

        # Apply updates
        for key, value in update_dict.items():
            setattr(policy, key, value)

        metrics.increment("policy_updates_total")

        AuditService.create_audit_log(
            db=db,
            entity_type="merchant_policy",
            entity_id=str(policy.id),
            action="policy_updated",
            actor=actor,
            metadata={
                "merchant_id": policy.merchant_id,
                "updated_fields": list(update_dict.keys()),
            },
        )
        db.commit()
        db.refresh(policy)
        return policy

    @classmethod
    def reset_policy_to_defaults(
        cls,
        db: Session,
        policy_id: int,
        actor: str = "merchant_admin",
    ) -> MerchantPolicy:
        """Reset a merchant policy to safe factory defaults."""
        policy = cls.get_policy_by_id(db, policy_id)

        policy.high_risk_threshold_paise = 1000000
        policy.critical_risk_threshold_paise = 5000000
        policy.human_review_threshold_paise = 1000000
        policy.auto_execute_low_risk = True
        policy.max_attempts = 3
        policy.backoff_base_seconds = 30
        policy.allowed_channels = ["email", "sms", "whatsapp", "webhook"]
        policy.preferred_channel = "email"
        policy.min_recovery_amount_paise = 10000
        policy.max_recovery_amount_paise = 100000000
        policy.require_approval_for_high_risk = True
        policy.require_approval_for_critical_risk = True
        policy.webhook_enabled = True
        policy.is_active = True

        metrics.increment("policy_updates_total")

        AuditService.create_audit_log(
            db=db,
            entity_type="merchant_policy",
            entity_id=str(policy.id),
            action="policy_reset",
            actor=actor,
            metadata={"merchant_id": policy.merchant_id, "factory_defaults": True},
        )
        db.commit()
        db.refresh(policy)
        return policy

    @classmethod
    def evaluate_merchant_policy(
        cls,
        db: Session,
        merchant_id: str,
        context: PolicyEvaluationContext,
    ) -> PolicyEvaluationResult:
        """Evaluates active merchant policy against a recovery context."""
        policy = cls.get_or_create_default_policy(db, merchant_id)
        policy_base = MerchantPolicyBase(
            high_risk_threshold_paise=policy.high_risk_threshold_paise,
            critical_risk_threshold_paise=policy.critical_risk_threshold_paise,
            human_review_threshold_paise=policy.human_review_threshold_paise,
            auto_execute_low_risk=policy.auto_execute_low_risk,
            max_attempts=policy.max_attempts,
            backoff_base_seconds=policy.backoff_base_seconds,
            allowed_channels=policy.allowed_channels,
            preferred_channel=policy.preferred_channel,
            min_recovery_amount_paise=policy.min_recovery_amount_paise,
            max_recovery_amount_paise=policy.max_recovery_amount_paise,
            require_approval_for_high_risk=policy.require_approval_for_high_risk,
            require_approval_for_critical_risk=policy.require_approval_for_critical_risk,
            webhook_enabled=policy.webhook_enabled,
            is_active=policy.is_active,
        )
        return evaluate_policy_against_context(policy_base, context)
