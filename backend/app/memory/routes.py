"""Engineering Memory and Timeline Intelligence routes."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.auth import get_current_user
from ..database import get_repo_repo, get_review_repo, get_memory_repo
from ..models import User, Memory
from ..schemas import MemoryIn, MemoryPatch
from .service import MemoryService

router = APIRouter(tags=["memory-timeline"])


def _svc() -> MemoryService:
    return MemoryService(get_memory_repo())


# ---------------------------------------------------------------------------
# Engineering Memory
# ---------------------------------------------------------------------------

@router.get("/memory")
async def list_memories(
    user: User = Depends(get_current_user),
    repo_id: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    source: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
):
    items = await _svc().list(
        user.id,
        {"repo_id": repo_id, "category": category, "severity": severity, "status": status, "source": source},
        limit,
    )
    return [m.model_dump() for m in items]


@router.post("/memory")
async def create_memory(body: MemoryIn, user: User = Depends(get_current_user)):
    repo = await get_repo_repo().get(body.repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    mem = Memory(user_id=user.id, source="user", **body.model_dump())
    await _svc().create(mem)
    return mem.model_dump()


@router.patch("/memory/{mid}")
async def update_memory(mid: str, body: MemoryPatch, user: User = Depends(get_current_user)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    m = await _svc().update(user.id, mid, patch)
    if not m:
        raise HTTPException(status_code=404, detail="Memory not found")
    return m.model_dump()


@router.delete("/memory/{mid}")
async def delete_memory(mid: str, user: User = Depends(get_current_user)):
    ok = await _svc().delete(user.id, mid)
    if not ok:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}


@router.get("/memory/search")
async def search_memory(q: str = Query(..., min_length=1, max_length=1000),
    repo_id: str | None = None, category: str | None = None,
    severity: str | None = None, status: str | None = None, source: str | None = None,
    limit: int = Query(30, ge=1, le=200), user: User = Depends(get_current_user)):
    items = await _svc().search(user.id, q, limit,
        {"repo_id": repo_id, "category": category, "severity": severity, "status": status, "source": source})
    return [m.model_dump() for m in items]


@router.get("/memory/stats")
async def memory_stats(repo_id: str | None = None, user: User = Depends(get_current_user)):
    return await _svc().stats(user.id, repo_id)


@router.post("/memory/import/{review_id}")
async def import_review(review_id: str, user: User = Depends(get_current_user)):
    rev = await get_review_repo().get(review_id)
    if not rev or rev.user_id != user.id:
        raise HTTPException(status_code=404, detail="Review not found")
    added = await _svc().import_from_review(rev, user.id)
    return {"added": added}


# ---------------------------------------------------------------------------
# Timeline Intelligence
# ---------------------------------------------------------------------------

async def _repo_or_404(repo_id: str, user: User):
    repo = await get_repo_repo().get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


def _timeline(repo):
    return repo.timeline or {}


@router.get("/repos/{repo_id}/timeline/commits")
async def tl_commits(
    repo_id: str,
    limit: int = Query(200, ge=1, le=500),
    user: User = Depends(get_current_user),
):
    repo = await _repo_or_404(repo_id, user)
    svc = _timeline(repo)
    return {"available": svc.get("available", False), "shallow": svc.get("shallow", False), "commits": svc.get("commits", [])[:limit]}


@router.get("/repos/{repo_id}/timeline/hotspots")
async def tl_hotspots(
    repo_id: str,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
):
    repo = await _repo_or_404(repo_id, user)
    return {"items": _timeline(repo).get("hotspots", [])[:limit]}


@router.get("/repos/{repo_id}/timeline/contributors")
async def tl_contributors(repo_id: str, user: User = Depends(get_current_user)):
    repo = await _repo_or_404(repo_id, user)
    return {"items": _timeline(repo).get("contributors", [])}


@router.get("/repos/{repo_id}/timeline/complexity")
async def tl_complexity(
    repo_id: str,
    buckets: int = Query(20, ge=4, le=60),
    user: User = Depends(get_current_user),
):
    repo = await _repo_or_404(repo_id, user)
    return {"trend": _timeline(repo).get("complexity", [])[:buckets]}


@router.get("/repos/{repo_id}/timeline/file")
async def tl_file(repo_id: str, path: str, user: User = Depends(get_current_user)):
    repo = await _repo_or_404(repo_id, user)
    return {"history": _timeline(repo).get("files", {}).get(path, [])}
