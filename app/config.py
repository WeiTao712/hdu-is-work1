"""Application configuration.

All security-relevant settings are read from environment variables so that
no secret is ever hard-coded in the repository.  ``Config.validate()`` fails
fast when a production deployment forgets to provide them.
"""

from __future__ import annotations

import os
import secrets


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Base configuration (development defaults, safe by construction)."""

    # --- Flask -----------------------------------------------------------
    ENV = os.environ.get("APP_ENV", "development")
    DEBUG = _env_bool("FLASK_DEBUG", False)
    TESTING = False
    MAX_CONTENT_LENGTH = 64 * 1024  # 64 KiB request body limit
    JSON_SORT_KEYS = False

    # --- Secrets ---------------------------------------------------------
    # A throw-away secret is generated at import time only so that the
    # development server can start.  Production MUST provide both values.
    JWT_SECRET = os.environ.get("JWT_SECRET") or secrets.token_urlsafe(48)
    JWT_ALGORITHM = "HS256"
    JWT_ISSUER = "hdu-is-work1"
    JWT_AUDIENCE = "hdu-is-work1-api"
    ACCESS_TOKEN_TTL = int(os.environ.get("ACCESS_TOKEN_TTL", "900"))  # 15 min

    # --- Passwords -------------------------------------------------------
    BCRYPT_ROUNDS = int(os.environ.get("BCRYPT_ROUNDS", "12"))
    PASSWORD_MIN_LENGTH = 12

    # --- Storage ---------------------------------------------------------
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "app.db"),
    )

    # --- Brute-force protection -----------------------------------------
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "300"))

    @classmethod
    def validate(cls) -> None:
        """Refuse to run in production with development secrets."""
        if cls.DEBUG:
            # Debug mode leaks stack traces over HTTP -> never in production.
            raise RuntimeError("FLASK_DEBUG must be disabled for this application")
        if os.environ.get("APP_ENV") == "production":
            missing = [k for k in ("JWT_SECRET", "DATABASE_PATH") if not os.environ.get(k)]
            if missing:
                raise RuntimeError("Missing required environment variables: " + ", ".join(missing))


class TestConfig(Config):
    TESTING = True
    JWT_SECRET = "test-secret-key-not-for-production-0123456789"
    BCRYPT_ROUNDS = 4  # keep the test suite fast
    ACCESS_TOKEN_TTL = 900
    DATABASE_PATH = ":memory:"
