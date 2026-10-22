"""Environment configuration. No network or filesystem side effects at import."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes"}


def async_database_url(url: str) -> str:
    """Accept standard provider PostgreSQL URLs without rewriting credentials."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


class Settings:
    ENV = os.getenv("ENV", "development")
    DATABASE_URL = async_database_url(os.getenv("DATABASE_URL", "postgresql+asyncpg://codeos:codeos@localhost:5432/codeos"))
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
    JWT_SECRET = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    COOKIE_NAME = "codeos_token"
    COOKIE_SECURE = flag("AUTH_COOKIE_SECURE")
    COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax")
    COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN") or None
    CORS_ORIGINS = [x.strip().rstrip("/") for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5000").split(",") if x.strip()]
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
    LLM_REQUESTS_PER_MINUTE = int(os.getenv("LLM_REQUESTS_PER_MINUTE", "5"))
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
    EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))
    AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "90"))
    INTERACTIVE_TIMEOUT_SECONDS = float(os.getenv("INTERACTIVE_TIMEOUT_SECONDS", "105"))
    S3_BUCKET = os.getenv("S3_BUCKET", "codeos-archives")
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL") or None
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID") or None
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY") or None
    S3_ENCRYPTION = os.getenv("S3_ENCRYPTION", "AES256")
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "codeos_gemini_768_v1")
    WORKER_ENABLED = flag("WORKER_ENABLED", "true")
    JOB_POLL_SECONDS = float(os.getenv("JOB_POLL_SECONDS", "2"))
    JOB_MAX_ATTEMPTS = int(os.getenv("JOB_MAX_ATTEMPTS", "3"))
    JOB_LEASE_SECONDS = int(os.getenv("JOB_LEASE_SECONDS", "120"))
    INGEST_TIMEOUT_SECONDS = int(os.getenv("INGEST_TIMEOUT_SECONDS", "1800"))
    MAX_ARCHIVE_BYTES = int(os.getenv("MAX_ARCHIVE_BYTES", str(200 * 1024**2)))
    MAX_EXTRACT_BYTES = int(os.getenv("MAX_EXTRACT_BYTES", str(500 * 1024**2)))
    MAX_FILES = int(os.getenv("MAX_FILES", "20000"))
    MAX_SOURCE_BYTES = int(os.getenv("MAX_SOURCE_BYTES", "500000"))
    MAX_REPOSITORIES_PER_USER = int(os.getenv("MAX_REPOSITORIES_PER_USER", "30"))
    MAX_COMPRESSION_RATIO = int(os.getenv("MAX_COMPRESSION_RATIO", "200"))


settings = Settings()


def validate_startup_config() -> None:
    errors = []
    if len(settings.JWT_SECRET) < 32:
        errors.append("Set JWT_SECRET to a random value of at least 32 characters (see .env.example).")
    if "*" in settings.CORS_ORIGINS:
        errors.append("CORS_ORIGINS must contain explicit frontend origins.")
    if settings.COOKIE_SAMESITE not in {"lax", "strict", "none"}:
        errors.append("AUTH_COOKIE_SAMESITE must be lax, strict, or none.")
    if settings.COOKIE_SAMESITE == "none" and not settings.COOKIE_SECURE:
        errors.append("SameSite=none requires AUTH_COOKIE_SECURE=true.")
    if settings.ENV != "test" and not settings.DATABASE_URL.startswith("postgresql+asyncpg://"):
        errors.append("DATABASE_URL must use PostgreSQL with asyncpg.")
    if settings.ENV == "production" and not settings.COOKIE_SECURE:
        errors.append("Use secure authentication cookies in production.")
    if settings.EMBEDDING_DIMENSIONS < 128 or settings.EMBEDDING_DIMENSIONS > 3072:
        errors.append("EMBEDDING_DIMENSIONS must be between 128 and 3072.")
    if not settings.NEO4J_PASSWORD:
        errors.append("Set NEO4J_PASSWORD.")
    if not 0 < settings.INTERACTIVE_TIMEOUT_SECONDS <= 110:
        errors.append("INTERACTIVE_TIMEOUT_SECONDS must be greater than 0 and at most 110.")
    if not 1 <= settings.LLM_REQUESTS_PER_MINUTE <= 1000:
        errors.append("LLM_REQUESTS_PER_MINUTE must be between 1 and 1000.")
    if errors:
        raise RuntimeError("Configuration errors:\n- " + "\n- ".join(errors))
