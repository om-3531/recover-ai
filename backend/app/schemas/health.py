"""Pydantic schemas for the health check endpoint."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    service: str
