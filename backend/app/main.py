"""
RecoverAI backend entrypoint.

Initializes FastAPI application, CORS middleware, exception handlers,
unversioned health check, and `/api/v1` routes.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.routes import health
from app.core.config import get_settings
from app.core.exceptions import AppException

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


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle domain/application exceptions with appropriate HTTP status codes."""
    content: dict = {"detail": exc.message}
    if exc.details is not None:
        content["details"] = exc.details
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
    )


# Unversioned health check (used by uptime monitors / Docker healthcheck)
app.include_router(health.router)

# Versioned application API
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
