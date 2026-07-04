from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    # Sparse TF-IDF term map; Phase-2 swap to dense Gemini embedding
    sparse_vec: dict[str, float] = Field(default_factory=dict)
    norm: float = 0.0
    created_at: str = Field(default_factory=_now)
