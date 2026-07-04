from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActivityEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    repo_id: str | None = None
    type: str
    message: str
    created_at: str = Field(default_factory=_now)
