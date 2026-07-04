"""Generic metadata repository interface — adapter-agnostic CRUD."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, Any

T = TypeVar("T")


class IMetadataRepository(ABC, Generic[T]):
    @abstractmethod
    async def insert(self, entity: T) -> T: ...

    @abstractmethod
    async def get(self, entity_id: str) -> Optional[T]: ...

    @abstractmethod
    async def find_one(self, query: dict[str, Any]) -> Optional[T]: ...

    @abstractmethod
    async def list(self, query: dict[str, Any] | None = None, limit: int = 100, sort: list[tuple[str, int]] | None = None) -> list[T]: ...

    @abstractmethod
    async def update(self, entity_id: str, patch: dict[str, Any]) -> Optional[T]: ...

    @abstractmethod
    async def delete(self, entity_id: str) -> bool: ...

    @abstractmethod
    async def count(self, query: dict[str, Any] | None = None) -> int: ...
