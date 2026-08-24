"""
Pydantic schemas for AuditLog endpoints.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    """Response schema for a single audit log entry."""

    id: int
    entity_type: str
    entity_id: str
    action: str
    actor: str
    event_metadata: Optional[dict[str, Any]] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    """Paginated response schema for listing audit logs."""

    items: list[AuditLogResponse]
    total: int
