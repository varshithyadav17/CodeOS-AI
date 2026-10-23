"""AI routes: chat, reviews, architecture analysis, and documentation."""
from __future__ import annotations
import io
import asyncio
import logging
import math
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..auth.auth import get_current_user
from ..embedding_limits import EmbeddingDeferred
from ..config import settings
from ..database import (
    get_repo_repo, get_graph_service, get_vector_store,
    get_conversation_repo, get_message_repo,
    get_activity_repo, get_review_repo, get_docs_repo,
)
from ..models import User, ActivityEvent
from ..prompts import DOC_TYPES
from ..schemas import AskIn, GenIn
from .chat import ChatService, RetrievalService
from .review import ReviewService
from .architecture import ArchitectureService
from .service import DocGenService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ai"])


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------

def get_chat_service() -> ChatService:
    return ChatService(
        get_conversation_repo(),
        get_message_repo(),
        RetrievalService(get_graph_service(), get_vector_store()),
    )


def get_review_service() -> ReviewService:
    return ReviewService(get_review_repo(), get_repo_repo(), get_graph_service(), get_vector_store())


def _arch_svc() -> ArchitectureService:
    return ArchitectureService(get_graph_service())


def _doc_svc() -> DocGenService:
    return DocGenService(get_docs_repo(), get_graph_service(), get_vector_store())


# ---------------------------------------------------------------------------
# Chat routes
# ---------------------------------------------------------------------------

@router.post("/repos/{repo_id}/chat")
async def ask(
    repo_id: str,
    body: AskIn,
    user: User = Depends(get_current_user),
    chat: ChatService = Depends(get_chat_service),
):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status != "ready":
        raise HTTPException(409, "Repository must be ready before asking questions.")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    try:
        async with asyncio.timeout(settings.INTERACTIVE_TIMEOUT_SECONDS):
            result = await chat.ask(repo.id, user.id, body.conversation_id, body.message)
    except TimeoutError:
        raise HTTPException(503, "The answer took too long. Please try a more specific question or retry.")
    await get_activity_repo().insert(ActivityEvent(
        user_id=user.id, repo_id=repo.id, type="chat",
        message=f"Asked: {body.message[:60]}",
    ))
    return result


@router.get("/repos/{repo_id}/conversations")
async def list_conversations(repo_id: str, user: User = Depends(get_current_user)):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    convs = get_conversation_repo()
    items = await convs.list({"repo_id": repo_id, "user_id": user.id}, limit=100, sort=[("updated_at", -1)])
    return [c.model_dump() for c in items]


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user: User = Depends(get_current_user)):
    convs = get_conversation_repo()
    conv = await convs.get(conversation_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    msgs = get_message_repo()
    messages = await msgs.list({"conversation_id": conversation_id}, limit=500, sort=[("created_at", 1)])
    return {"conversation": conv.model_dump(), "messages": [m.model_dump() for m in messages]}


# ---------------------------------------------------------------------------
# Code review routes
# ---------------------------------------------------------------------------

@router.post("/repos/{repo_id}/reviews", status_code=202)
async def start_review(
    repo_id: str,
    user: User = Depends(get_current_user),
    svc: ReviewService = Depends(get_review_service),
):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status != "ready":
        raise HTTPException(status_code=400, detail=f"Repository must be 'ready' (current: {repo.status})")
    from ..jobs import enqueue
    if not settings.GEMINI_API_KEY:
        raise HTTPException(503, "Set GEMINI_API_KEY to enable code review.")
    review = await svc.create(repo_id, user.id)
    try:
        await enqueue(repo_id, user.id, "review", {"review_id": review.id})
    except HTTPException:
        await get_review_repo().delete(review.id)
        raise
    await get_activity_repo().insert(ActivityEvent(
        user_id=user.id, repo_id=repo_id, type="review_started",
        message=f"Started multi-agent review for {repo.name}",
    ))
    return review.model_dump()


@router.get("/repos/{repo_id}/reviews")
async def list_reviews(repo_id: str, user: User = Depends(get_current_user)):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    items = await get_review_repo().list(
        {"repo_id": repo_id, "user_id": user.id}, limit=50, sort=[("created_at", -1)]
    )
    return [r.model_dump() for r in items]


@router.get("/reviews/{review_id}")
async def get_review(review_id: str, user: User = Depends(get_current_user)):
    rev = await get_review_repo().get(review_id)
    if not rev or rev.user_id != user.id:
        raise HTTPException(status_code=404, detail="Review not found")
    return rev.model_dump()


# ---------------------------------------------------------------------------
# Architecture routes
# ---------------------------------------------------------------------------

async def _auth_repo(repo_id: str, user: User):
    repo = await get_repo_repo().get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status not in {"ready", "embedding", "waiting_embeddings"} or not repo.file_manifest:
        raise HTTPException(status_code=400, detail=f"Repository not ready (status={repo.status})")
    return repo


@router.get("/repos/{repo_id}/architecture/graph")
async def architecture_graph(
    repo_id: str,
    view: str = Query("call", pattern="^(call|dependency|package|service)$"),
    limit: int = Query(200, ge=10, le=1000),
    user: User = Depends(get_current_user),
):
    await _auth_repo(repo_id, user)
    s = _arch_svc()
    if view == "call":
        return await s.call_graph(repo_id, limit)
    if view == "dependency":
        return await s.dependency_graph(repo_id, limit)
    if view == "package":
        return await s.package_graph(repo_id, limit)
    return await s.service_graph(repo_id, limit)


@router.get("/repos/{repo_id}/architecture/cycles")
async def architecture_cycles(repo_id: str, user: User = Depends(get_current_user)):
    await _auth_repo(repo_id, user)
    return await _arch_svc().detect_cycles(repo_id)


@router.get("/repos/{repo_id}/architecture/dead-code")
async def architecture_dead_code(repo_id: str, user: User = Depends(get_current_user)):
    await _auth_repo(repo_id, user)
    return await _arch_svc().dead_code(repo_id)


@router.get("/repos/{repo_id}/architecture/impact/{node_id}")
async def architecture_impact(
    repo_id: str, node_id: str,
    depth: int = Query(3, ge=1, le=6),
    user: User = Depends(get_current_user),
):
    await _auth_repo(repo_id, user)
    return await _arch_svc().impact(repo_id, node_id, depth)


@router.get("/repos/{repo_id}/architecture/flow/{node_id}")
async def architecture_flow(
    repo_id: str, node_id: str,
    depth: int = Query(3, ge=1, le=6),
    user: User = Depends(get_current_user),
):
    await _auth_repo(repo_id, user)
    return await _arch_svc().execution_flow(repo_id, node_id, depth)


# ---------------------------------------------------------------------------
# Documentation routes
# ---------------------------------------------------------------------------

@router.get("/repos/{repo_id}/docs/types")
async def doc_types(repo_id: str, user: User = Depends(get_current_user)):
    await _auth_repo(repo_id, user)
    return [{"key": k, "label": v} for k, v in DOC_TYPES.items()]


@router.get("/repos/{repo_id}/docs")
async def list_docs(repo_id: str, user: User = Depends(get_current_user)):
    repo = await get_repo_repo().get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    items = await get_docs_repo().list(
        {"repo_id": repo_id, "user_id": user.id}, limit=50, sort=[("updated_at", -1)]
    )
    return items


@router.post("/repos/{repo_id}/docs/generate")
async def generate_doc(repo_id: str, body: GenIn, user: User = Depends(get_current_user)):
    repo = await get_repo_repo().get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status != "ready":
        raise HTTPException(status_code=400, detail="Repository not ready")
    if body.doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail="Unknown doc type")
    try:
        async with asyncio.timeout(settings.INTERACTIVE_TIMEOUT_SECONDS):
            return await _doc_svc().generate(repo, body.doc_type, user.id)
    except HTTPException:
        raise
    except EmbeddingDeferred as exc:
        raise HTTPException(503, "Google embedding capacity is temporarily unavailable. Your repository is saved; please retry later.",
            headers={"Retry-After": str(math.ceil(exc.retry_after))}) from exc
    except TimeoutError:
        raise HTTPException(503, "Documentation generation took too long. Please retry.")
    except RuntimeError:
        raise HTTPException(503, "AI documentation is unavailable. Check Gemini configuration and try again.")
    except Exception:
        logger.exception("Doc generation failed for repo %s type %s", repo_id, body.doc_type)
        raise HTTPException(status_code=500, detail="Doc generation failed. Check server logs for details.")


@router.get("/repos/{repo_id}/docs/export")
async def export_docs_zip(repo_id: str, user: User = Depends(get_current_user)):
    repo = await get_repo_repo().get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    items = await get_docs_repo().list({"repo_id": repo_id, "user_id": user.id}, limit=50)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in items:
            z.writestr(f"{d['doc_type']}.md", d.get("content", ""))
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="codeos-{repo.id}-docs.zip"'},
    )
