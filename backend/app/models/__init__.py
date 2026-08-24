"""
SQLAlchemy models registration for RecoverAI.

Importing all models here ensures they are discovered and registered
with `Base.metadata` for migrations and database operations.
"""

from app.models.audit import AuditLog
from app.models.enums import (
    PaymentEventProcessingStatus,
    PaymentMethod,
    PaymentStatus,
    RecoveryActionChannel,
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryCaseState,
    RecoveryPriority,
    RevenueStatus,
    RiskStatus,
)
from app.models.mixins import TimestampMixin
from app.models.payment import Payment, PaymentEvent
from app.models.recovery import RecoveryAction, RecoveryCase
from app.models.revenue import RevenueRecord
from app.models.system import SystemHealthCheck

__all__ = [
    "SystemHealthCheck",
    "Payment",
    "PaymentEvent",
    "RevenueRecord",
    "RecoveryCase",
    "RecoveryAction",
    "AuditLog",
    "PaymentStatus",
    "PaymentMethod",
    "PaymentEventProcessingStatus",
    "RevenueStatus",
    "RiskStatus",
    "RecoveryPriority",
    "RecoveryCaseState",
    "RecoveryActionStatus",
    "RecoveryActionType",
    "RecoveryActionChannel",
    "TimestampMixin",
]
