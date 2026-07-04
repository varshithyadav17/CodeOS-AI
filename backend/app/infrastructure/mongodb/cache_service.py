"""In-memory cache (Phase-1). Same API as Redis adapter (Phase-3)."""
from __future__ import annotations
import time
from typing import Any
from ...core.interfaces.cache import ICacheService


class InMemoryCacheService(ICacheService):
    def __init__(self):
        self._store: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        exp, val = item
        if exp and exp < time.time():
            self._store.pop(key, None)
            return None
        return val

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        self._store[key] = (time.time() + ttl_seconds, value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
