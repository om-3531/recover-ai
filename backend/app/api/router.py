"""
Aggregates all `/api/v1` routes.

As new domains are built (payments, recovery queue, AI decisions, audit
trail, analytics) their routers should be created under
`app/api/routes/` and included here — keeping `main.py` free of route
wiring details.
"""

from fastapi import APIRouter

from app.api.routes import status

api_router = APIRouter()
api_router.include_router(status.router)
