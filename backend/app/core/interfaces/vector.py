"""Vector store interface — swap Mongo → Qdrant without changing services."""
from __future__ import annotations
from abc import ABC, abstractmethod
from ..models.code import CodeChunk


class IVectorStore(ABC):
    @abstractmethod
    async def upsert(self, chunks: list[CodeChunk]) -> int: ...

    @abstractmethod
    async def query(self, repo_id: str, query_text: str, k: int = 8) -> list[CodeChunk]: ...

    @abstractmethod
    async def delete_namespace(self, repo_id: str) -> None: ...

    @abstractmethod
    async def count(self, repo_id: str | None = None) -> int: ...
