"""
Reusable SQLAlchemy model mixins.

Provides common column definitions such as timezone-aware audit timestamps
across all domain entities.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """
    Mixin providing timezone-aware created_at and updated_at timestamps.

    Both fields are non-nullable and default to UTC now at creation time.
    `updated_at` automatically updates on row modification.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
