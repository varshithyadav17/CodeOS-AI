"""Engineering Memory service — CRUD + semantic search."""
from __future__ import annotations
from typing import Any
from ..core.interfaces.metadata import IMetadataRepository
from ..core.models.memory import Memory
from ..core.models.review import Review
from ..infrastructure.mongodb.vector_store import tfidf, cosine


class MemoryService:
    def __init__(self, memories: IMetadataRepository[Memory]):
        self.memories = memories

    async def create(self, mem: Memory) -> Memory:
        await self.memories.insert(mem)
        return mem

    async def list(self, user_id: str, filters: dict[str, Any], limit: int = 200) -> list[Memory]:
        q: dict[str, Any] = {"user_id": user_id}
        for k in ("repo_id", "category", "severity", "status", "source"):
            if filters.get(k):
                q[k] = filters[k]
        return await self.memories.list(q, limit=limit, sort=[("updated_at", -1)])

    async def get(self, user_id: str, mid: str) -> Memory | None:
        m = await self.memories.get(mid)
        if not m or m.user_id != user_id:
            return None
        return m

    async def update(self, user_id: str, mid: str, patch: dict[str, Any]) -> Memory | None:
        existing = await self.get(user_id, mid)
        if not existing:
            return None
        allowed = {k: v for k, v in patch.items() if k in {"status", "title", "description", "severity", "tags", "category"}}
        return await self.memories.update(mid, allowed)

    async def delete(self, user_id: str, mid: str) -> bool:
        existing = await self.get(user_id, mid)
        if not existing:
            return False
        return await self.memories.delete(mid)

    async def search(self, user_id: str, query: str, limit: int = 30) -> list[Memory]:
        items = await self.memories.list({"user_id": user_id}, limit=2000, sort=[("updated_at", -1)])
        if not items:
            return []
        docs = [f"{m.title} {m.description} {m.category} {m.file_path or ''} {' '.join(m.tags)}" for m in items]
        df: dict[str, int] = {}
        from ..infrastructure.mongodb.vector_store import tokenize
        for d in docs:
            for t in set(tokenize(d)):
                df[t] = df.get(t, 0) + 1
        q_vec, q_norm = tfidf(query, df, len(docs))
        scored = []
        for m, d in zip(items, docs):
            v, n = tfidf(d, df, len(docs))
            s = cosine(q_vec, q_norm, v, n)
            if s > 0:
                scored.append((s, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:limit]]

    async def stats(self, user_id: str, repo_id: str | None = None) -> dict[str, Any]:
        q = {"user_id": user_id}
        if repo_id:
            q["repo_id"] = repo_id
        items = await self.memories.list(q, limit=5000)
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for m in items:
            by_status[m.status] = by_status.get(m.status, 0) + 1
            by_category[m.category] = by_category.get(m.category, 0) + 1
            by_severity[m.severity] = by_severity.get(m.severity, 0) + 1
        return {"total": len(items), "by_status": by_status, "by_category": by_category, "by_severity": by_severity}

    async def import_from_review(self, review: Review, user_id: str) -> int:
        """Persist a review's findings as memories (idempotent on finding_id)."""
        existing = await self.memories.list({"user_id": user_id, "review_id": review.id}, limit=2000)
        existing_fids = {m.finding_id for m in existing if m.finding_id}
        added = 0
        for a in review.agents:
            for f in a.findings:
                if f.id in existing_fids:
                    continue
                mem = Memory(
                    repo_id=review.repo_id, user_id=user_id, source="review",
                    category=a.agent, title=f.title, description=f.description,
                    severity=f.severity, confidence=f.confidence, status="open",
                    file_path=f.file_path, tags=[f.category] if f.category else [],
                    review_id=review.id, finding_id=f.id,
                )
                await self.memories.insert(mem)
                added += 1
        return added
