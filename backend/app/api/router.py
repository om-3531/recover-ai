"""
Aggregates all `/api/v1` routes.

Includes payment, revenue, recovery, audit, and status domain routers.
"""

from fastapi import APIRouter

from app.api.routes import audit, payments, recovery, revenue, status

api_router = APIRouter()
api_router.include_router(payments.router)
api_router.include_router(revenue.router)
api_router.include_router(recovery.router)
api_router.include_router(audit.router)
api_router.include_router(status.router)
