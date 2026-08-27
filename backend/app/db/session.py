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

# SQLite requires `check_same_thread=False` for use with FastAPI's async thread pool.
# PostgreSQL works fine with or without it, so we always pass it for simplicity.
_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "future": True,
}
if settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

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
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
