"""FastAPI application bootstrap for CodeOS AI."""
from __future__ import annotations
import logging
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from .core.config import settings, validate_startup_config
from .api.routes import auth, repos, graph, chat, stats, reviews, architecture, memory, docs

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Fail fast on misconfiguration (missing JWT_SECRET in prod, wildcard CORS
# in prod, etc.) rather than starting up and misbehaving silently.
validate_startup_config()

app = FastAPI(title="CodeOS AI", version="0.1.0")

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(repos.router)
api_router.include_router(graph.router)
api_router.include_router(chat.router)
api_router.include_router(stats.router)
api_router.include_router(reviews.router)
api_router.include_router(architecture.router)
api_router.include_router(memory.router)
api_router.include_router(docs.router)


@api_router.get("/")
async def root():
    return {"name": "CodeOS AI", "version": "0.1.0", "status": "ok"}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
