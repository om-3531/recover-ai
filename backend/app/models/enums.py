"""
Domain enumerations for RecoverAI.

All enums inherit from `str, Enum` so that they serialize smoothly
to string values and integrate cleanly with SQLAlchemy column definitions.
"""

from enum import Enum


class PaymentStatus(str, Enum):
    """Lifecycle status of a payment."""

    created = "created"
    authorized = "authorized"
    captured = "captured"
    failed = "failed"
    refunded = "refunded"


class PaymentMethod(str, Enum):
    """Payment method/channel used by the customer."""

    card = "card"
    upi = "upi"
    netbanking = "netbanking"
    wallet = "wallet"
    emi = "emi"
    other = "other"


class PaymentEventProcessingStatus(str, Enum):
    """Processing state for ingested webhook/event payloads."""

    pending = "pending"
    processed = "processed"
    failed = "failed"


class RevenueStatus(str, Enum):
    """Financial tracking status of a revenue record."""

    pending = "pending"
    recognized = "recognized"
    at_risk = "at_risk"
    recovered = "recovered"
    lost = "lost"


class RiskStatus(str, Enum):
    """Assessed risk level for failed or at-risk revenue."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RecoveryPriority(str, Enum):
    """Operational priority assigned to a recovery case."""

    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class RecoveryCaseState(str, Enum):
    """Workflow state of an active or resolved recovery case."""

    open = "open"
    investigating = "investigating"
    action_pending = "action_pending"
    recovering = "recovering"
    recovered = "recovered"
    closed = "closed"
    failed = "failed"


class RecoveryActionStatus(str, Enum):
    """Execution status of a specific recovery intervention."""

    pending = "pending"
    scheduled = "scheduled"
    executed = "executed"
    failed = "failed"
    cancelled = "cancelled"


class RecoveryActionType(str, Enum):
    """Type of recovery intervention recommended/scheduled."""

    payment_link = "payment_link"
    email_reminder = "email_reminder"
    sms_reminder = "sms_reminder"
    whatsapp_reminder = "whatsapp_reminder"
    retry_payment = "retry_payment"
    webhook_ping = "webhook_ping"
    discount_offer = "discount_offer"
    custom = "custom"


class RecoveryActionChannel(str, Enum):
    """Communication/execution channel used for recovery."""

    email = "email"
    sms = "sms"
    whatsapp = "whatsapp"
    webhook = "webhook"
    in_app = "in_app"
    system = "system"


class ApprovalStatus(str, Enum):
    """Status of a recovery intervention approval request."""

    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    cancelled = "cancelled"


class JobStatus(str, Enum):
    """Lifecycle status of a recovery execution job."""

    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    retry_scheduled = "retry_scheduled"
    cancelled = "cancelled"


