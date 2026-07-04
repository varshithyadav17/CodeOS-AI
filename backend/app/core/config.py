"""Centralised configuration. Read once at import-time from env."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _bool(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # Mongo
    MONGO_URL: str = os.environ["MONGO_URL"]
    DB_NAME: str = os.environ["DB_NAME"]

    # Auth (JWT)
    ENV: str = os.environ.get("ENV", "development").strip().lower()
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
    JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
    JWT_EXPIRY_HOURS: int = int(os.environ.get("JWT_EXPIRY_HOURS", "168"))

    # Session cookie. Auth tokens are issued as HttpOnly cookies so they
    # cannot be read by JS (XSS-resistant). The Authorization header path
    # is still accepted (for curl / tests / programmatic clients).
    COOKIE_NAME: str = os.environ.get("AUTH_COOKIE_NAME", "codeos_token")
    COOKIE_SECURE: bool = _bool("AUTH_COOKIE_SECURE", "0")
    COOKIE_SAMESITE: str = os.environ.get("AUTH_COOKIE_SAMESITE", "lax").lower()
    COOKIE_DOMAIN: str | None = os.environ.get("AUTH_COOKIE_DOMAIN") or None

    # LLM (Gemini via google-genai).
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "gemini")
    LLM_MODEL: str = os.environ.get("LLM_MODEL") or os.environ.get(
        "GEMINI_MODEL", "gemini-2.5-pro"
    )

    # Google OAuth (placeholder — populated when user provides creds)
    GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_OAUTH_REDIRECT_URI: str = os.environ.get(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://localhost:8001/api/auth/google/callback",
    )

    # Storage — defaults OUTSIDE backend/ so uvicorn --reload's file-watcher
    # (which watches the backend/ tree) doesn't fire constant reloads while a
    # large ingestion is writing thousands of files mid-pipeline.
    STORAGE_PATH: str = os.environ.get("STORAGE_PATH", str(ROOT.parent / "codeos_uploads"))

    # CORS — defaults to the local Vite dev origin. A "*" wildcard combined
    # with allow_credentials=True is both a security hole and non-functional
    # in browsers (they refuse to send credentials to a wildcard origin), so
    # it must be explicitly opted into rather than being the default.
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
        if o.strip()
    ] or ["http://localhost:5173"]


settings = Settings()
Path(settings.STORAGE_PATH).mkdir(parents=True, exist_ok=True)


def validate_startup_config() -> None:
    """Fail loudly at startup rather than silently running insecurely.

    Called from main.py before the app starts serving requests.
    """
    errors: list[str] = []

    if not settings.JWT_SECRET:
        if settings.ENV in {"production", "prod"}:
            errors.append(
                "JWT_SECRET is not set. Refusing to start in production with an "
                "unset signing key — set JWT_SECRET in your environment/.env."
            )
        else:
            # Non-production: generate a random ephemeral secret so the app
            # still runs, but tokens won't survive a restart and this is
            # loudly logged so it's never mistaken for a real deployment.
            import secrets
            settings.JWT_SECRET = secrets.token_urlsafe(48)
            import logging
            logging.getLogger(__name__).warning(
                "JWT_SECRET is not set — using a random ephemeral secret for this "
                "process only. All existing sessions will be invalidated on restart. "
                "Set JWT_SECRET explicitly before deploying."
            )

    if settings.CORS_ORIGINS == ["*"] and settings.ENV in {"production", "prod"}:
        errors.append(
            "CORS_ORIGINS is '*' in production, which is incompatible with "
            "credentialed (cookie-based) requests. Set CORS_ORIGINS to your "
            "real frontend origin(s)."
        )

    if not settings.GEMINI_API_KEY:
        import logging
        logging.getLogger(__name__).warning(
            "GEMINI_API_KEY is not set — chat, reviews, and docs generation "
            "will fail until it is configured."
        )

    if errors:
        raise RuntimeError(
            "Startup configuration validation failed:\n- " + "\n- ".join(errors)
        )
