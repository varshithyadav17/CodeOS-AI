from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


MemorySource = Literal["review", "user", "system", "ai"]
MemoryStatus = Literal["open", "in_progress", "resolved", "wont_fix"]


class Memory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    user_id: str
    source: MemorySource = "user"
    category: str  # architecture|security|performance|testing|documentation|refactoring|tech_debt|note
    title: str
    description: str = ""
    severity: str = "medium"  # critical|high|medium|low|info
    confidence: float = 0.7
    status: MemoryStatus = "open"
    file_path: str | None = None
    symbol: str | None = None  # class/function qualified name
    tags: list[str] = Field(default_factory=list)
    review_id: str | None = None
    finding_id: str | None = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
