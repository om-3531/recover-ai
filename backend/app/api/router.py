"""
Aggregates all `/api/v1` routes.

Includes payment, revenue, recovery, audit, webhook, ai, approval, orchestration, jobs, and status domain routers.
"""

from fastapi import APIRouter

from app.api.routes import (
    ai,
    analytics,
    approvals,
    audit,
    demo,
    jobs,
    orchestration,
    payments,
    policies,
    recovery,
    revenue,
    status,
    system,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(payments.router)
api_router.include_router(revenue.router)
api_router.include_router(recovery.router)
api_router.include_router(audit.router)
api_router.include_router(webhooks.router)
api_router.include_router(ai.router)
api_router.include_router(approvals.router)
api_router.include_router(orchestration.router)
api_router.include_router(jobs.router)
api_router.include_router(analytics.router)
api_router.include_router(demo.router)
api_router.include_router(policies.router)
api_router.include_router(system.router)
api_router.include_router(status.router)




