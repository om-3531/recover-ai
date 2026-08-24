"""
Database initialization.

For Day 1 this only creates the minimal `system_health` table used by the
health check. The real payment/revenue schema will be designed and
migrated separately on Day 2 (likely with Alembic).
"""

from app.db.base import Base
from app.db.session import engine

# Import models here so they are registered on Base.metadata before
# create_all is called. Kept explicit (no wildcard imports) so it is
# obvious which models exist as the project grows.
from app.models.system import SystemHealthCheck  # noqa: F401


def init_db() -> None:
    """Create all tables that don't already exist."""
    Base.metadata.create_all(bind=engine)
