"""FastAPI bootstrap, health checks and managed job worker lifecycle."""
from __future__ import annotations
import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager, suppress
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.cors import CORSMiddleware
from .config import settings, validate_startup_config
from . import database as db
from .auth.auth import get_current_user, router as auth_router
from .repository.routes import router as repo_router
from .ai.routes import router as ai_router
from .memory.routes import router as memory_router
from .jobs import worker_loop
from .middleware import UploadLimitMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    validate_startup_config()
    # Fail clearly if migrations or PostgreSQL connectivity are missing.
    try:
        async with db.get_engine().connect() as conn:
            await conn.execute(select(db.users).limit(1))
    except SQLAlchemyError as exc:
        raise RuntimeError("PostgreSQL is unavailable or migrations are missing. Run: alembic upgrade head") from exc
    worker = asyncio.create_task(worker_loop()) if settings.WORKER_ENABLED else None
    try:
        yield
    finally:
        if worker:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
        from .ai.chat import close_clients
        await close_clients()
        for factory in (db.get_graph_service, db.get_vector_store):
            if factory.cache_info().currsize:
                await factory().close()
                factory.cache_clear()
        await db.get_engine().dispose()


app = FastAPI(title="CodeOS AI", version="1.0.0", lifespan=lifespan)
api = APIRouter(prefix="/api")
for router in (auth_router, repo_router, ai_router, memory_router):
    api.include_router(router)


@api.get("/")
async def root():
    return {"name": "CodeOS AI", "version": "1.0.0", "status": "ok"}


@api.get("/health/live")
async def live():
    return {"status": "ok"}


@api.get("/health/ready")
async def ready(user=Depends(get_current_user)):
    async def postgres():
        async with db.get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    async def check(name, operation):
        try:
            async with asyncio.timeout(15):
                await operation()
            return name, "ok"
        except Exception:
            return name, "unavailable"
    status = dict(await asyncio.gather(check("postgresql", postgres),
        check("s3", db.get_storage().ping), check("neo4j", db.get_graph_service().ping), check("qdrant", db.get_vector_store().ping)))
    status["gemini"] = "configured" if settings.GEMINI_API_KEY else "missing_api_key"
    ok = all(v in {"ok", "configured"} for v in status.values())
    return JSONResponse({"status": "ready" if ok else "degraded", "services": status,
        "model": settings.LLM_MODEL, "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dimensions": settings.EMBEDDING_DIMENSIONS}, status_code=200 if ok else 503)


app.include_router(api)


@app.middleware("http")
async def request_safety(request: Request, call_next):
    request_id = str(uuid.uuid4())
    started = time.monotonic()
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if origin and origin.rstrip("/") not in settings.CORS_ORIGINS:
            return JSONResponse({"detail": "Request origin is not allowed."}, status_code=403)
        if not origin and request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site mutation is not allowed."}, status_code=403)
    # Reject oversized uploads before multipart parsing; nginx enforces the same bound.
    if request.url.path.endswith("/repos/upload"):
        try:
            if int(request.headers.get("content-length", "0")) > settings.MAX_ARCHIVE_BYTES + 1024**2:
                return JSONResponse({"detail": "Archive exceeds the configured upload size limit."}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed request_id=%s path=%s", request_id, request.url.path)
        response = JSONResponse({"detail": "Service operation failed. Check service health and retry.", "request_id": request_id}, status_code=503)
    response.headers.update({"X-Request-ID": request_id, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "strict-origin-when-cross-origin"})
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    logger.info("request request_id=%s method=%s path=%s status=%s seconds=%.3f", request_id, request.method, request.url.path, response.status_code, time.monotonic()-started)
    return response


app.add_middleware(UploadLimitMiddleware)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])
