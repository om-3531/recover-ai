"""
Database initialization.

Provides helper methods to initialize or reflect database tables.
In production/staging, Alembic migrations are the preferred mechanism.
"""

from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401


def init_db() -> None:
    """Create all tables that don't already exist."""
    Base.metadata.create_all(bind=engine)

