"""
Declarative base for all SQLAlchemy models.

Every model in `app/models` should inherit from `Base`. Keeping the base
in its own module (separate from `session.py`) avoids circular imports
once more models are added in later milestones.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base class for all ORM models."""

    pass
