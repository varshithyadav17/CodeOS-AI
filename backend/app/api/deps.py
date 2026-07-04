"""FastAPI dependencies: current_user from JWT (cookie OR Bearer header)."""
from __future__ import annotations
from fastapi import Cookie, Depends, Header, HTTPException
from ..core.config import settings
from ..core.security import decode_token
from ..core.models.user import User
from ..core.container import (
    get_user_repo, get_repo_repo, get_conversation_repo, get_message_repo, get_activity_repo,
    get_graph_service, get_vector_store, get_storage,
)
from ..services.auth_service import AuthService
from ..services.ingestion_service import IngestionService
from ..services.retrieval_service import RetrievalService
from ..services.chat_service import ChatService


def _extract_token(
    authorization: str | None,
    cookie_token: str | None,
) -> str:
    # Prefer the Authorization header (used by curl / tests / API clients);
    # fall back to the HttpOnly auth cookie used by the browser frontend.
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    if cookie_token:
        return cookie_token.strip()
    raise HTTPException(status_code=401, detail="Missing bearer token")


async def get_current_user(
    authorization: str | None = Header(default=None),
    codeos_token: str | None = Cookie(default=None, alias=settings.COOKIE_NAME),
) -> User:
    token = _extract_token(authorization, codeos_token)
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    users = get_user_repo()
    user = await users.get(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_auth_service() -> AuthService:
    return AuthService(get_user_repo())


def get_ingestion_service() -> IngestionService:
    return IngestionService(get_repo_repo(), get_graph_service(), get_vector_store(), get_storage())


def get_retrieval_service() -> RetrievalService:
    return RetrievalService(get_graph_service(), get_vector_store())


def get_chat_service() -> ChatService:
    return ChatService(get_conversation_repo(), get_message_repo(), get_retrieval_service())
