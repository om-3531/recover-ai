"""
RecoverAI backend entrypoint.

Day 1 scope only: app wiring, health check, versioned API mount, and
CORS. Payment, AI, recovery, and webhook functionality are intentionally
not implemented yet — see CLAUDE.md for the full roadmap.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes import health
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="RecoverAI",
    description="AI-powered autonomous revenue recovery agent.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Unversioned health check (used by uptime monitors / Docker healthcheck)
app.include_router(health.router)

# Versioned application API
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
