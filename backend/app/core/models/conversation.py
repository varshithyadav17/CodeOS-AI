from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Conversation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    user_id: str
    title: str = "New chat"
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    role: str  # user|assistant|system
    content: str
    context_nodes: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
