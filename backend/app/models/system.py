"""
Minimal system-level model(s).

This is intentionally the ONLY model created on Day 1. It exists to prove
the database layer works end-to-end (engine, session, Base, create_all).
The payment/revenue schema is explicitly out of scope for Day 1.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SystemHealthCheck(Base):
    """
    A tiny table used to verify database connectivity and migrations.

    Not part of the business/payment domain — purely infrastructural.
    """

    __tablename__ = "system_health_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="ok", nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
