"""Local filesystem storage. Swap to S3/MinIO later."""
from __future__ import annotations
from pathlib import Path
import shutil
from ...core.config import settings
from ...core.interfaces.storage import IStorageService


class LocalFileStorage(IStorageService):
    def __init__(self, root: str | None = None):
        self.root = Path(root or settings.STORAGE_PATH)
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, key: str) -> Path:
        p = (self.root / key).resolve()
        # prevent path traversal outside root
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError("Invalid key (path traversal)")
        return p

    async def put_blob(self, key: str, data: bytes) -> str:
        p = self.resolve(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return str(p)

    async def ensure_dir(self, key: str) -> Path:
        p = self.resolve(key)
        p.mkdir(parents=True, exist_ok=True)
        return p

    async def delete(self, key: str) -> None:
        p = self.resolve(key)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
