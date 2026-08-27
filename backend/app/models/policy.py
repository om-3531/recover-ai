"""
MerchantPolicy SQLAlchemy model.

Stores merchant-customized recovery rules, risk thresholds, automation toggles,
retry bounds, and channel constraints. Monetary amounts are stored in integer paise.
"""

from typing import List, Optional
from sqlalchemy import Boolean, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class MerchantPolicy(Base, TimestampMixin):
    """
    Merchant policy configuration table.

    Enforces deterministic business rules over AI recovery recommendations.
    All monetary thresholds are stored as integer paise (e.g. 1000000 = ₹10,000.00).
    """

    __tablename__ = "merchant_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    merchant_id: Mapped[str] = mapped_column(
        String(64),
        default="merchant_default",
        unique=True,
        index=True,
        nullable=False,
        comment="Unique merchant identifier",
    )
    high_risk_threshold_paise: Mapped[int] = mapped_column(
        Integer,
        default=1000000,  # ₹10,000
        nullable=False,
        comment="Threshold above which cases are classified as high risk",
    )
    critical_risk_threshold_paise: Mapped[int] = mapped_column(
        Integer,
        default=5000000,  # ₹50,000
        nullable=False,
        comment="Threshold above which cases are classified as critical risk",
    )
    human_review_threshold_paise: Mapped[int] = mapped_column(
        Integer,
        default=1000000,  # ₹10,000
        nullable=False,
        comment="Transactions at or above this amount strictly require human approval",
    )
    auto_execute_low_risk: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Allow autonomous auto-execution for low risk cases below human review threshold",
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
        comment="Maximum recovery attempts allowed per case",
    )
    backoff_base_seconds: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
        comment="Base delay in seconds for exponential backoff retries",
    )
    allowed_channels: Mapped[list] = mapped_column(
        JSON,
        default=lambda: ["email", "sms", "whatsapp", "webhook"],
        nullable=False,
        comment="List of allowed communication channels (email, sms, whatsapp, webhook)",
    )
    preferred_channel: Mapped[str] = mapped_column(
        String(32),
        default="email",
        nullable=False,
        comment="Primary fallback channel for recovery communications",
    )
    min_recovery_amount_paise: Mapped[int] = mapped_column(
        Integer,
        default=10000,  # ₹100
        nullable=False,
        comment="Minimum payment failure amount to initiate recovery for",
    )
    max_recovery_amount_paise: Mapped[int] = mapped_column(
        Integer,
        default=100000000,  # ₹10,00,000
        nullable=False,
        comment="Maximum payment failure amount permitted for recovery workflows",
    )
    require_approval_for_high_risk: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether high-risk cases strictly require human approval before execution",
    )
    require_approval_for_critical_risk: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether critical-risk cases strictly require human approval before execution",
    )
    webhook_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether webhook partner pings are enabled",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this policy is currently active",
    )
