"""
Tests for the database configuration layer.

These tests verify the SQLAlchemy engine/session are *configured*
correctly. They do not require a running PostgreSQL instance — actually
connecting is exercised manually (see README) since CI/dev environments
may not always have Postgres available.
"""

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine


def test_engine_is_configured():
    assert engine is not None
    assert str(engine.url).startswith("postgresql")


def test_session_factory_creates_session():
    db = SessionLocal()
    try:
        assert isinstance(db, Session)
    finally:
        db.close()


def test_base_metadata_includes_system_health_model():
    from app.db.base import Base
    from app.models.system import SystemHealthCheck  # noqa: F401

    assert "system_health_checks" in Base.metadata.tables
