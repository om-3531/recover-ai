"""
Application configuration.

All configuration is loaded from environment variables. Nothing sensitive
is ever hard-coded here. See `.env.example` in the project root for the
list of variables this application expects.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application settings.

    Values are read from environment variables (and optionally a local
    `.env` file during development). Keys/secrets are intentionally left
    as empty strings by default so the app fails loudly/explicitly rather
    than silently using a placeholder credential.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General ---
    APP_NAME: str = "recover-ai-backend"
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    APP_VERSION: str = "0.1.0"

    # --- Database ---
    # Default points at a local dev Postgres instance (see docker-compose.yml).
    # Not a secret — override via .env for any real credentials.
    DATABASE_URL: str = "postgresql://recoverai:recoverai@localhost:5432/recoverai"

    # --- AI Recommendation Engine ---
    AI_PROVIDER: str = "mock"  # mock, gemini
    GEMINI_API_KEY: str = ""
    AI_API_KEY: str = ""  # alias
    AI_MODEL: str = "gemini-1.5-flash"

    # --- Razorpay Payments & Webhooks ---
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # --- Communication Providers (optional / safely disabled by default) ---
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@recoverai.example"

    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    META_WHATSAPP_TOKEN: str = ""  # alias

    # --- Webhooks & Execution Jobs ---
    WEBHOOK_TIMEOUT_SECONDS: float = 10.0
    WEBHOOK_ALLOW_INSECURE_HTTP: bool = False  # Set true only in dev to allow http://localhost
    JOB_MAX_ATTEMPTS: int = 3
    JOB_BACKOFF_BASE_SECONDS: int = 30

    # --- CORS ---
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # --- Demo / Buildathon Configuration ---
    DEMO_MODE: bool = True
    DEMO_SEED: int = 42


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    Using lru_cache means the environment is only parsed once per process,
    which keeps configuration access cheap and consistent across the app.
    """
    return Settings()
