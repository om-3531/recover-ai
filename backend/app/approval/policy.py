"""
Approval Policy validation rules.
"""

from datetime import datetime, timezone

from app.approval.exceptions import ApprovalPolicyBlockedError, ApprovalStateError
from app.models.approval import RecoveryApproval
from app.models.enums import ApprovalStatus, RecoveryCaseState
from app.models.recovery import RecoveryCase


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class ApprovalPolicy:
    """Deterministic validation rules for recovery approvals."""

    @staticmethod
    def validate_approval_creation(case: RecoveryCase) -> None:
        """
        Validate whether an approval request can be created for a recovery case.

        Rejects terminal states (recovered, closed) and cases with zero recoverable balance.
        """
        if case.current_state in (
            RecoveryCaseState.recovered,
            RecoveryCaseState.closed,
        ):
            raise ApprovalPolicyBlockedError(
                f"Cannot create approval request for case in '{case.current_state.value}' state"
            )

        if case.revenue_record and case.revenue_record.recoverable_amount <= 0:
            raise ApprovalPolicyBlockedError(
                "Cannot create approval request when recoverable amount is 0 paise"
            )

    @staticmethod
    def validate_approval_decision(
        approval: RecoveryApproval, decision_action: str
    ) -> None:
        """
        Validate whether a pending approval can be approved or rejected.

        Rejects non-pending statuses and expired requests.
        """
        now = datetime.now(timezone.utc)
        if approval.expires_at and _ensure_utc(approval.expires_at) < now:
            approval.status = ApprovalStatus.expired
            raise ApprovalStateError("Approval request has expired")

        if approval.status != ApprovalStatus.pending:
            raise ApprovalStateError(
                f"Cannot {decision_action} approval in '{approval.status.value}' status"
            )
