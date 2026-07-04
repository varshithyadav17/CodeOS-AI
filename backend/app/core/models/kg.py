from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class KGNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_id: str
    type: str  # file|class|function|method|variable|import
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
    type: str  # CONTAINS|IMPORTS|CALLS|EXTENDS|IMPLEMENTS|USES|DEPENDS_ON
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)
