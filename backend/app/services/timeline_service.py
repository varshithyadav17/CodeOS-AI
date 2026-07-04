"""Timeline Intelligence — git log analytics via GitPython."""
from __future__ import annotations
import logging
from collections import defaultdict
from pathlib import Path
import git

logger = logging.getLogger(__name__)


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

    def commits(self, limit: int = 200) -> list[dict]:
        try:
            repo = self._git()
        except Exception as e:
            logger.warning("Git repo unavailable: %s", e)
            return []
        out = []
        for c in repo.iter_commits(max_count=limit):
            try:
                stats = c.stats.total
                out.append({
                    "sha": c.hexsha[:12], "full_sha": c.hexsha,
                    "author": c.author.name, "email": c.author.email,
                    "date": c.committed_datetime.isoformat(),
                    "message": (c.message or "").strip().splitlines()[0][:200],
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
            try:
                file_stats = c.stats.files.get(file_path, {})
            except Exception:
                file_stats = {}
            out.append({
                "sha": c.hexsha[:12], "author": c.author.name,
                "date": c.committed_datetime.isoformat(),
                "message": (c.message or "").strip().splitlines()[0][:200],
                "insertions": file_stats.get("insertions", 0),
                "deletions": file_stats.get("deletions", 0),
            })
        return out

    def hotspots(self, limit: int = 50) -> list[dict]:
        try:
            repo = self._git()
        except Exception:
            return []
        churn: dict[str, dict] = defaultdict(lambda: {"changes": 0, "insertions": 0, "deletions": 0, "authors": set()})
        for c in repo.iter_commits(max_count=500):
            try:
                for path, st in c.stats.files.items():
                    churn[path]["changes"] += 1
                    churn[path]["insertions"] += st.get("insertions", 0)
                    churn[path]["deletions"] += st.get("deletions", 0)
                    churn[path]["authors"].add(c.author.name)
            except Exception:
                continue
        items = [
            {"path": p, "changes": v["changes"], "insertions": v["insertions"], "deletions": v["deletions"], "authors": len(v["authors"])}
            for p, v in churn.items()
        ]
        items.sort(key=lambda x: x["changes"], reverse=True)
        return items[:limit]

    def contributors(self) -> list[dict]:
        try:
            repo = self._git()
        except Exception:
            return []
        stats: dict[str, dict] = defaultdict(lambda: {"commits": 0, "insertions": 0, "deletions": 0, "email": "", "last": ""})
        for c in repo.iter_commits(max_count=1000):
            try:
                a = c.author.name
                s = stats[a]
                s["commits"] += 1
                s["email"] = c.author.email
                s["insertions"] += c.stats.total.get("insertions", 0)
                s["deletions"] += c.stats.total.get("deletions", 0)
                d = c.committed_datetime.isoformat()
                if d > s["last"]:
                    s["last"] = d
            except Exception:
                continue
        out = [{"author": k, **v} for k, v in stats.items()]
        out.sort(key=lambda x: x["commits"], reverse=True)
        return out

    def complexity_trend(self, buckets: int = 20) -> list[dict]:
        """Approximate complexity over time using LOC-changed per commit, bucketed."""
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
        commits.reverse()  # chronological
        n = len(commits)
        size = max(1, n // buckets)
        out = []
        for i in range(0, n, size):
            slab = commits[i:i + size]
            if not slab:
                continue
            ins = 0; dels = 0; valid = 0
            for c in slab:
                try:
                    t = c.stats.total
                    ins += t.get("insertions", 0)
                    dels += t.get("deletions", 0)
                    valid += 1
                except Exception:
                    continue
            try:
                out.append({
                    "from": slab[0].committed_datetime.isoformat(),
                    "to": slab[-1].committed_datetime.isoformat(),
                    "commits": len(slab),
                    "churn": ins + dels,
                    "insertions": ins,
                    "deletions": dels,
                })
            except Exception:
                continue
        return out
