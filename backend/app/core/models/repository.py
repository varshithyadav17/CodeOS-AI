from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RepoStatus(str, Enum):
    QUEUED = "queued"
    CLONING = "cloning"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"


class RepoStats(BaseModel):
    files: int = 0
    loc: int = 0
    nodes: int = 0
    edges: int = 0
    chunks: int = 0


class Repository(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    source: str  # github | zip
    source_url: str | None = None
    branch: str | None = None
    local_path: str
    status: RepoStatus = RepoStatus.QUEUED
    progress: int = 0
    message: str | None = None
    language_breakdown: dict[str, int] = Field(default_factory=dict)
    stats: RepoStats = Field(default_factory=RepoStats)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
