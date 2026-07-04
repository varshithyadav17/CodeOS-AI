from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field, EmailStr, ConfigDict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    password_hash: str | None = None
    picture: str | None = None
    provider: str = "local"  # local | google
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
