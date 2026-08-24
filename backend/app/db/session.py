"""
Database engine and session management.

This module is intentionally minimal for Day 1: it wires up SQLAlchemy's
engine and a session factory. The full payment/revenue schema is a Day 2
task and is deliberately NOT implemented here.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# `pool_pre_ping` keeps the pool honest about dropped connections, which
# matters for long-lived dev/hackathon sessions against a local Postgres.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session and guarantees
    it is closed after the request, even if an exception is raised.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
