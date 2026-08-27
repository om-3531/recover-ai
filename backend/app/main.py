"""
RecoverAI backend entrypoint.

Initializes FastAPI application, request correlation middleware, CORS middleware,
exception handlers, unversioned health/readiness checks, and `/api/v1` routes.
"""

import uuid
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.routes import health
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.db.init_db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Create database tables on startup if they don't already exist."""
    init_db()
    yield


app = FastAPI(
    title="RecoverAI",
    description="AI-powered autonomous revenue recovery agent.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration — accept both localhost and 127.0.0.1 variants
_cors_origins = {settings.FRONTEND_ORIGIN}
# Ensure both localhost and 127.0.0.1 forms are allowed
if "localhost" in settings.FRONTEND_ORIGIN:
    _cors_origins.add(settings.FRONTEND_ORIGIN.replace("localhost", "127.0.0.1"))
elif "127.0.0.1" in settings.FRONTEND_ORIGIN:
    _cors_origins.add(settings.FRONTEND_ORIGIN.replace("127.0.0.1", "localhost"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next: Callable) -> Response:
    """Propagate or generate X-Request-ID correlation header for observability."""
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle domain/application exceptions with consistent structured response and correlation ID."""
    req_id = getattr(request.state, "request_id", None)
    content: dict = {
        "detail": exc.message,
        "error": {
            "code": exc.__class__.__name__,
            "message": exc.message,
            "request_id": req_id,
            "details": exc.details,
        },
    }
    if exc.details is not None:
        content["details"] = exc.details

    headers = {}
    if req_id:
        headers["X-Request-ID"] = req_id

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=headers,
    )


# Unversioned health & readiness checks (used by uptime monitors & probes)
app.include_router(health.router)

# Versioned application API
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
