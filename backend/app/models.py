"""All domain models — merged from core/models/*."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, EmailStr, ConfigDict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    password_hash: str | None = None
    picture: str | None = None
    provider: str = "local"  # local | google
    google_subject: str | None = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class RepoStatus(str, Enum):
    QUEUED = "queued"
    CLONING = "cloning"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"
    DELETING = "deleting"
    DELETE_FAILED = "delete_failed"


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
    archive_key: str | None = None
    archive_sha256: str | None = None
    source_commit: str | None = None
    active_job_id: str | None = None
    file_manifest: list[dict[str, Any]] = Field(default_factory=list, exclude=True)
    timeline: dict[str, Any] = Field(default_factory=dict, exclude=True)
    status: RepoStatus = RepoStatus.QUEUED
    progress: int = 0
    message: str | None = None
    language_breakdown: dict[str, int] = Field(default_factory=dict)
    stats: RepoStats = Field(default_factory=RepoStats)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Knowledge Graph
# ---------------------------------------------------------------------------

class KGNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    type: str  # file | class | function | method | variable | import
    name: str
    qualified_name: str
    file_path: str
    start_line: int = 0
    end_line: int = 0
    language: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


class KGEdge(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    source_id: str
    target_id: str
    type: str  # CONTAINS | IMPORTS | CALLS | EXTENDS | IMPLEMENTS | USES | DEPENDS_ON
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Code chunk (vector store unit)
# ---------------------------------------------------------------------------

class CodeChunk(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    node_id: str | None = None
    file_path: str
    start_line: int = 0
    end_line: int = 0
    language: str = "unknown"
    text: str
    token_count: int = 0
    score: float = 0.0
    created_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Conversation / Message
# ---------------------------------------------------------------------------

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
    role: str  # user | assistant | system
    content: str
    context_nodes: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

class ActivityEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    repo_id: str | None = None
    type: str
    message: str
    created_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Code Review
# ---------------------------------------------------------------------------

Severity = Literal["critical", "high", "medium", "low", "info"]


class Finding(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent: str
    category: str
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(max_length=2000)
    severity: Severity = "medium"
    confidence: float = Field(default=0.6, ge=0, le=1, allow_inf_nan=False)
    file_path: str | None = None
    line: int | None = Field(default=None, ge=1)
    recommendation: str | None = Field(default=None, max_length=4000)


class AgentReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    agent: str
    status: Literal["pending", "running", "done", "failed"] = "pending"
    summary: str = ""
    score: int = Field(default=70, ge=0, le=100)
    findings: list[Finding] = Field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0


class Review(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    user_id: str
    status: Literal["queued", "running", "done", "failed"] = "queued"
    progress: int = 0
    overall_score: int = 0
    summary: str = ""
    action_plan: list[str] = Field(default_factory=list)
    agents: list[AgentReport] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Engineering Memory
# ---------------------------------------------------------------------------

MemorySource = Literal["review", "user", "system", "ai"]
MemoryStatus = Literal["open", "in_progress", "resolved", "wont_fix"]


class Memory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    user_id: str
    source: MemorySource = "user"
    category: str  # architecture | security | performance | testing | documentation | refactoring | tech_debt | note
    title: str
    description: str = ""
    severity: str = "medium"  # critical | high | medium | low | info
    confidence: float = 0.7
    status: MemoryStatus = "open"
    file_path: str | None = None
    symbol: str | None = None
    tags: list[str] = Field(default_factory=list)
    review_id: str | None = None
    finding_id: str | None = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
