"""Pydantic schemas for the health and readiness check endpoints."""

from typing import Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    service: str


class ReadinessResponse(BaseModel):
    """Response body for GET /ready."""

    status: str
    service: str
    database: str
    environment: str
    demo_mode: bool
