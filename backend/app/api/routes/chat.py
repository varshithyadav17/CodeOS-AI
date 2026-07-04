"""Chat routes."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_current_user, get_chat_service
from ...core.container import get_repo_repo, get_conversation_repo, get_message_repo, get_activity_repo
from ...core.models.user import User
from ...core.models.activity import ActivityEvent
from ...services.chat_service import ChatService

router = APIRouter(tags=["chat"])


class AskIn(BaseModel):
    message: str
    conversation_id: str | None = None


@router.post("/repos/{repo_id}/chat")
async def ask(repo_id: str, body: AskIn, user: User = Depends(get_current_user), chat: ChatService = Depends(get_chat_service)):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    result = await chat.ask(repo.id, user.id, body.conversation_id, body.message)
    await get_activity_repo().insert(ActivityEvent(user_id=user.id, repo_id=repo.id, type="chat", message=f"Asked: {body.message[:60]}"))
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
