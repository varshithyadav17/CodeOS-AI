from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


Severity = Literal["critical", "high", "medium", "low", "info"]


class Finding(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent: str
    category: str  # e.g. "circular_dependency", "hardcoded_secret"
    title: str
    description: str
    severity: Severity = "medium"
    confidence: float = 0.6  # 0..1
    file_path: str | None = None
    line: int | None = None
    recommendation: str | None = None


class AgentReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    agent: str
    status: Literal["pending", "running", "done", "failed"] = "pending"
    summary: str = ""
    score: int = 70  # 0..100
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
