"""Object storage interface — swap LocalFS → MinIO/S3 without changing services."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path


class IStorageService(ABC):
    @abstractmethod
    async def put_blob(self, key: str, data: bytes) -> str:
        """Return a local-resolvable path or URI."""

    @abstractmethod
    async def ensure_dir(self, key: str) -> Path: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    def resolve(self, key: str) -> Path: ...
