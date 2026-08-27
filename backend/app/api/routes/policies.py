"""
Merchant Policy REST API routes.

Enables viewing, updating, validating, and resetting merchant-configurable recovery rules.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.policy import MerchantPolicy
from app.policy.rules import generate_policy_summary
from app.policy.schemas import (
    MerchantPolicyBase,
    MerchantPolicyCreate,
    MerchantPolicyResponse,
    MerchantPolicyUpdate,
    PolicyEvaluationContext,
    PolicyPreviewRequest,
    PolicyPreviewResponse,
    PolicyValidationResult,
)
from app.policy.service import PolicyService

router = APIRouter(prefix="/policies", tags=["policies"])


def _to_response(policy: MerchantPolicy) -> MerchantPolicyResponse:
    """Helper to convert MerchantPolicy ORM to response schema with summary."""
    base = MerchantPolicyBase(
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
    summary = generate_policy_summary(base)
    return MerchantPolicyResponse(
        id=policy.id,
        merchant_id=policy.merchant_id,
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
        summary=summary,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.get(
    "",
    response_model=List[MerchantPolicyResponse],
    summary="List merchant policies",
)
def list_policies(
    merchant_id: Optional[str] = Query(None, description="Filter by merchant ID"),
    db: Session = Depends(get_db),
) -> List[MerchantPolicyResponse]:
    """List all merchant policies or filter by merchant ID."""
    query = select(MerchantPolicy)
    if merchant_id:
        query = query.where(MerchantPolicy.merchant_id == merchant_id)
    policies = list(db.scalars(query.order_by(MerchantPolicy.id)).all())
    if not policies:
        default_policy = PolicyService.get_or_create_default_policy(db)
        policies = [default_policy]
    return [_to_response(p) for p in policies]


@router.get(
    "/current",
    response_model=MerchantPolicyResponse,
    summary="Get active merchant policy",
)
def get_current_policy(
    merchant_id: str = Query("merchant_default", description="Merchant ID"),
    db: Session = Depends(get_db),
) -> MerchantPolicyResponse:
    """Get the active policy for the specified or default merchant."""
    policy = PolicyService.get_or_create_default_policy(db, merchant_id=merchant_id)
    return _to_response(policy)


@router.post(
    "",
    response_model=MerchantPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create custom merchant policy",
)
def create_policy(
    payload: MerchantPolicyCreate,
    db: Session = Depends(get_db),
) -> MerchantPolicyResponse:
    """Create a new merchant policy."""
    val = PolicyService.validate_policy_payload(payload)
    if not val.valid:
        from app.policy.exceptions import PolicyValidationError
        raise PolicyValidationError(f"Invalid policy: {'; '.join(val.errors)}", details={"errors": val.errors})

    policy = MerchantPolicy(**payload.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return _to_response(policy)


@router.get(
    "/{policy_id}",
    response_model=MerchantPolicyResponse,
    summary="Get merchant policy by ID",
)
def get_policy(
    policy_id: int,
    db: Session = Depends(get_db),
) -> MerchantPolicyResponse:
    """Retrieve policy by primary ID."""
    policy = PolicyService.get_policy_by_id(db, policy_id)
    return _to_response(policy)


@router.put(
    "/{policy_id}",
    response_model=MerchantPolicyResponse,
    summary="Update merchant policy",
)
def update_policy(
    policy_id: int,
    payload: MerchantPolicyUpdate,
    db: Session = Depends(get_db),
) -> MerchantPolicyResponse:
    """Update policy rules with strict validation."""
    updated = PolicyService.update_policy(db, policy_id, payload)
    return _to_response(updated)


@router.post(
    "/{policy_id}/validate",
    response_model=PolicyValidationResult,
    summary="Validate policy adjustments (Dry Run)",
)
def validate_policy_endpoint(
    policy_id: int,
    payload: MerchantPolicyUpdate,
    db: Session = Depends(get_db),
) -> PolicyValidationResult:
    """Dry-run validation of policy changes without saving."""
    policy = PolicyService.get_policy_by_id(db, policy_id)
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
    current_dict.update(payload.model_dump(exclude_unset=True))
    prospective = MerchantPolicyBase(**current_dict)
    return PolicyService.validate_policy_payload(prospective)


@router.post(
    "/{policy_id}/reset",
    response_model=MerchantPolicyResponse,
    summary="Reset merchant policy to factory defaults",
)
def reset_policy_endpoint(
    policy_id: int,
    db: Session = Depends(get_db),
) -> MerchantPolicyResponse:
    """Reset policy parameters to safe system defaults."""
    reset_pol = PolicyService.reset_policy_to_defaults(db, policy_id)
    return _to_response(reset_pol)


@router.post(
    "/preview",
    response_model=PolicyPreviewResponse,
    summary="Preview policy decision for a hypothetical recovery scenario",
)
def preview_policy(
    payload: PolicyPreviewRequest,
    merchant_id: str = Query("merchant_default", description="Merchant ID"),
    db: Session = Depends(get_db),
) -> PolicyPreviewResponse:
    """
    Informationally evaluate a hypothetical recovery scenario against the active merchant policy.

    This endpoint executes nothing and creates no records.
    It is purely diagnostic — useful for UI previews and policy testing.
    """
    policy = PolicyService.get_or_create_default_policy(db, merchant_id=merchant_id)
    merchant_base = MerchantPolicyBase(
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
    evaluation = PolicyService.evaluate_merchant_policy(
        db=db,
        merchant_id=merchant_id,
        context=PolicyEvaluationContext(
            amount_paise=payload.amount_paise,
            channel=payload.channel,
            risk_status=payload.risk_status,
            attempt_count=payload.attempt_count,
            current_state=payload.current_state,
        ),
    )
    summary = generate_policy_summary(merchant_base)
    return PolicyPreviewResponse(evaluation=evaluation, summary=summary)
