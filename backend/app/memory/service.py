"""Engineering Memory and Timeline Intelligence services."""
from __future__ import annotations
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import git

from ..database import IMetadataRepository
from ..models import Memory, Review
from ..utils import tokenize, tfidf, cosine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MemoryService
# ---------------------------------------------------------------------------

class MemoryService:
    def __init__(self, memories: IMetadataRepository):
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
        allowed = {
            k: v for k, v in patch.items()
            if k in {"status", "title", "description", "severity", "tags", "category"}
        }
        return await self.memories.update(mid, allowed)

    async def delete(self, user_id: str, mid: str) -> bool:
        existing = await self.get(user_id, mid)
        if not existing:
            return False
        return await self.memories.delete(mid)

    async def search(self, user_id: str, query: str, limit: int = 30, filters: dict | None = None) -> list[Memory]:
        items = await self.list(user_id, filters or {}, limit=2000)
        if not items:
            return []
        docs = [
            f"{m.title} {m.description} {m.category} {m.file_path or ''} {' '.join(m.tags)}"
            for m in items
        ]
        df: dict[str, int] = {}
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
        q: dict[str, Any] = {"user_id": user_id}
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
        return {
            "total": len(items),
            "by_status": by_status,
            "by_category": by_category,
            "by_severity": by_severity,
        }

    async def import_from_review(self, review: Review, user_id: str) -> int:
        """Persist a review's findings as memories (idempotent on finding_id)."""
        existing = await self.memories.list(
            {"user_id": user_id, "review_id": review.id}, limit=2000
        )
        existing_fids = {m.finding_id for m in existing if m.finding_id}
        added = 0
        for a in review.agents:
            for f in a.findings:
                if f.id in existing_fids:
                    continue
                mem = Memory(
                    repo_id=review.repo_id, user_id=user_id, source="review",
                    category="architecture" if a.agent == "architect" else a.agent,
                    title=f.title, description=f.description,
                    severity=f.severity, confidence=f.confidence, status="open",
                    file_path=f.file_path, tags=[f.category] if f.category else [],
                    review_id=review.id, finding_id=f.id,
                )
                await self.memories.insert(mem)
                added += 1
        return added


# ---------------------------------------------------------------------------
# TimelineService
# ---------------------------------------------------------------------------

class TimelineService:
    def __init__(self, repo_local_path: str):
        self.path = Path(repo_local_path)

    def _git(self):
        return git.Repo(self.path)

    def available(self) -> bool:
        try:
            return self.path.exists() and (self.path / ".git").exists()
        except Exception:
            return False

    @staticmethod
    def _stats(commit):
        # A shallow boundary can contain the commit but omit its parent object.
        # Keep its identity/history even when GitPython cannot calculate a diff.
        try:
            return commit.stats
        except Exception:
            return None

    @staticmethod
    def _message(commit):
        lines = (commit.message or "").strip().splitlines()
        return lines[0][:200] if lines else "(no commit message)"

    def commits(self, limit: int = 200) -> list[dict]:
        try:
            repo = self._git()
        except Exception as e:
            logger.warning("Git repo unavailable: %s", e)
            return []
        out = []
        for c in repo.iter_commits(max_count=limit):
            try:
                available_stats = self._stats(c)
                stats = available_stats.total if available_stats is not None else {}
                out.append({
                    "sha": c.hexsha[:12], "full_sha": c.hexsha,
                    "author": c.author.name, "email": c.author.email,
                    "date": c.committed_datetime.isoformat(),
                    "message": self._message(c),
                    "stats_available": available_stats is not None,
                    "insertions": stats.get("insertions", 0),
                    "deletions": stats.get("deletions", 0),
                    "files": stats.get("files", 0),
                })
            except Exception:
                continue
        return out

    def file_evolution(self, file_path: str, limit: int = 100) -> list[dict]:
        try:
            repo = self._git()
        except Exception:
            return []
        out = []
        for c in repo.iter_commits(paths=file_path, max_count=limit):
            stats = self._stats(c)
            file_stats = stats.files.get(file_path, {}) if stats is not None else {}
            out.append({
                "sha": c.hexsha[:12], "author": c.author.name,
                "date": c.committed_datetime.isoformat(),
                "message": self._message(c),
                "stats_available": stats is not None,
                "insertions": file_stats.get("insertions", 0),
                "deletions": file_stats.get("deletions", 0),
            })
        return out

    def hotspots(self, limit: int = 50) -> list[dict]:
        try:
            repo = self._git()
        except Exception:
            return []
        churn: dict[str, dict] = defaultdict(
            lambda: {"changes": 0, "insertions": 0, "deletions": 0, "authors": set()}
        )
        for c in repo.iter_commits(max_count=500):
            try:
                stats = self._stats(c)
                if stats is None:
                    continue
                for path, st in stats.files.items():
                    churn[path]["changes"] += 1
                    churn[path]["insertions"] += st.get("insertions", 0)
                    churn[path]["deletions"] += st.get("deletions", 0)
                    churn[path]["authors"].add(c.author.name)
            except Exception:
                continue
        items = [
            {
                "path": p, "changes": v["changes"],
                "insertions": v["insertions"], "deletions": v["deletions"],
                "authors": len(v["authors"]),
            }
            for p, v in churn.items()
        ]
        items.sort(key=lambda x: x["changes"], reverse=True)
        return items[:limit]

    def contributors(self) -> list[dict]:
        try:
            repo = self._git()
        except Exception:
            return []
        stats: dict[str, dict] = defaultdict(
            lambda: {"commits": 0, "insertions": 0, "deletions": 0, "email": "", "last": "", "stats_available": True}
        )
        for c in repo.iter_commits(max_count=1000):
            try:
                a = c.author.name
                s = stats[a]
                s["commits"] += 1
                s["email"] = c.author.email
                d = c.committed_datetime.isoformat()
                if d > s["last"]:
                    s["last"] = d
                commit_stats = self._stats(c)
                if commit_stats is None:
                    s["stats_available"] = False
                else:
                    s["insertions"] += commit_stats.total.get("insertions", 0)
                    s["deletions"] += commit_stats.total.get("deletions", 0)
            except Exception:
                continue
        out = [{"author": k, **v} for k, v in stats.items()]
        out.sort(key=lambda x: x["commits"], reverse=True)
        return out

    def complexity_trend(self, buckets: int = 20) -> list[dict]:
        try:
            repo = self._git()
        except Exception:
            return []
        try:
            commits = list(repo.iter_commits(max_count=500))
        except Exception:
            return []
        if not commits:
            return []
        commits.reverse()
        n = len(commits)
        size = max(1, n // buckets)
        out = []
        for i in range(0, n, size):
            slab = commits[i:i + size]
            if not slab:
                continue
            ins = dels = valid = 0
            for c in slab:
                try:
                    stats = self._stats(c)
                    if stats is None:
                        continue
                    t = stats.total
                    ins += t.get("insertions", 0)
                    dels += t.get("deletions", 0)
                    valid += 1
                except Exception:
                    continue
            try:
                out.append({
                    "from": slab[0].committed_datetime.isoformat(),
                    "to": slab[-1].committed_datetime.isoformat(),
                    "commits": len(slab), "churn": ins + dels,
                    "insertions": ins, "deletions": dels,
                    "stats_available": valid == len(slab),
                })
            except Exception:
                continue
        return out


    def snapshot(self):
        """Preserve bounded history metadata before removing the temporary clone."""
        commits = self.commits(200)
        hotspots = self.hotspots(100)
        paths = [f["path"] for f in hotspots[:50]]
        shallow = False
        if self.available():
            repo = self._git()
            shallow = repo.git.rev_parse("--is-shallow-repository").strip() == "true"
            if not paths:
                paths = [p for p in repo.git.ls_files(z=True).split("\0") if p][:50]
        return {"available": self.available(), "shallow": shallow, "commits": commits,
            "hotspots": hotspots, "contributors": self.contributors(),
            "complexity": self.complexity_trend(20),
            "files": {path: self.file_evolution(path, 100) for path in paths}}
