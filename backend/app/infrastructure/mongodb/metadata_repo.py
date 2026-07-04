"""Mongo-backed implementation of IMetadataRepository[T]."""
from __future__ import annotations
from typing import Type, TypeVar, Any
from pydantic import BaseModel
from ...core.interfaces.metadata import IMetadataRepository
from . import db

T = TypeVar("T", bound=BaseModel)


class MongoMetadataRepository(IMetadataRepository[T]):
    def __init__(self, collection: str, model: Type[T]):
        self._col = db[collection]
        self._model = model

    @staticmethod
    def _strip_id(doc: dict) -> dict:
        if doc is None:
            return doc
        doc.pop("_id", None)
        return doc

    async def insert(self, entity: T) -> T:
        await self._col.insert_one(entity.model_dump())
        return entity

    async def get(self, entity_id: str) -> T | None:
        doc = await self._col.find_one({"id": entity_id}, {"_id": 0})
        return self._model(**doc) if doc else None

    async def find_one(self, query: dict[str, Any]) -> T | None:
        doc = await self._col.find_one(query, {"_id": 0})
        return self._model(**doc) if doc else None

    async def list(self, query: dict[str, Any] | None = None, limit: int = 100, sort: list[tuple[str, int]] | None = None) -> list[T]:
        cursor = self._col.find(query or {}, {"_id": 0})
        if sort:
            cursor = cursor.sort(sort)
        docs = await cursor.to_list(length=limit)
        return [self._model(**d) for d in docs]

    async def update(self, entity_id: str, patch: dict[str, Any]) -> T | None:
        from datetime import datetime, timezone
        patch = {**patch, "updated_at": datetime.now(timezone.utc).isoformat()}
        await self._col.update_one({"id": entity_id}, {"$set": patch})
        return await self.get(entity_id)

    async def delete(self, entity_id: str) -> bool:
        res = await self._col.delete_one({"id": entity_id})
        return res.deleted_count > 0

    async def count(self, query: dict[str, Any] | None = None) -> int:
        return await self._col.count_documents(query or {})
