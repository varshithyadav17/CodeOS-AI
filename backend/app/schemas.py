"""Bounded, validated API inputs."""
from typing import Literal
from pydantic import AliasChoices, BaseModel, EmailStr, Field, SecretStr


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GoogleIn(BaseModel):
    credential: str = Field(min_length=1, max_length=10000, validation_alias=AliasChoices("credential", "session_id"))
    link_password: SecretStr | None = Field(default=None, min_length=1, max_length=128)


class GithubIn(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    branch: str | None = Field(default=None, max_length=200)
    token: SecretStr | None = None


class AskIn(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: str | None = Field(default=None, max_length=36)


class MemoryIn(BaseModel):
    repo_id: str
    category: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20000)
    severity: Literal["critical", "high", "medium", "low", "info"] = "medium"
    status: Literal["open", "in_progress", "resolved", "wont_fix"] = "open"
    file_path: str | None = Field(default=None, max_length=1000)
    symbol: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=30)


class MemoryPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=20000)
    category: str | None = Field(default=None, max_length=80)
    severity: Literal["critical", "high", "medium", "low", "info"] | None = None
    status: Literal["open", "in_progress", "resolved", "wont_fix"] | None = None
    tags: list[str] | None = Field(default=None, max_length=30)


class GenIn(BaseModel):
    doc_type: str = Field(max_length=80)
