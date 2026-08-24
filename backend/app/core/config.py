"""
Application configuration.

All configuration is loaded from environment variables. Nothing sensitive
is ever hard-coded here. See `.env.example` in the project root for the
list of variables this application expects.
"""

from functools import lru_cache

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
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    # --- Database ---
    # Default points at a local dev Postgres instance (see docker-compose.yml).
    # Not a secret — override via .env for any real credentials.
    DATABASE_URL: str = "postgresql://recoverai:recoverai@localhost:5432/recoverai"

    # --- AI (used in a later milestone, not Day 1) ---
    GEMINI_API_KEY: str = ""

    # --- Razorpay (used in a later milestone, not Day 1) ---
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # --- CORS ---
    FRONTEND_ORIGIN: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    Using lru_cache means the environment is only parsed once per process,
    which keeps configuration access cheap and consistent across the app.
    """
    return Settings()
