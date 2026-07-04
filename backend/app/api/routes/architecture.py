"""Architecture Intelligence routes."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import get_current_user
from ...core.container import get_repo_repo, get_graph_service
from ...core.models.user import User
from ...services.architecture_service import ArchitectureService

router = APIRouter(prefix="/repos", tags=["architecture"])


def _svc() -> ArchitectureService:
    return ArchitectureService(get_graph_service())


async def _auth_repo(repo_id: str, user: User):
    repo = await get_repo_repo().get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status != "ready":
        raise HTTPException(status_code=400, detail=f"Repository not ready (status={repo.status})")
    return repo


@router.get("/{repo_id}/architecture/graph")
async def graph(repo_id: str, view: str = Query("call", pattern="^(call|dependency|package|service)$"),
                limit: int = Query(200, ge=10, le=1000), user: User = Depends(get_current_user)):
    await _auth_repo(repo_id, user)
    s = _svc()
    if view == "call": return await s.call_graph(repo_id, limit)
    if view == "dependency": return await s.dependency_graph(repo_id, limit)
    if view == "package": return await s.package_graph(repo_id, limit)
    return await s.service_graph(repo_id, limit)


@router.get("/{repo_id}/architecture/cycles")
async def cycles(repo_id: str, user: User = Depends(get_current_user)):
    await _auth_repo(repo_id, user)
    return await _svc().detect_cycles(repo_id)


@router.get("/{repo_id}/architecture/dead-code")
async def dead_code(repo_id: str, user: User = Depends(get_current_user)):
    await _auth_repo(repo_id, user)
    return await _svc().dead_code(repo_id)


@router.get("/{repo_id}/architecture/impact/{node_id}")
async def impact(repo_id: str, node_id: str, depth: int = Query(3, ge=1, le=6),
                 user: User = Depends(get_current_user)):
    await _auth_repo(repo_id, user)
    return await _svc().impact(repo_id, node_id, depth)


@router.get("/{repo_id}/architecture/flow/{node_id}")
async def flow(repo_id: str, node_id: str, depth: int = Query(3, ge=1, le=6),
               user: User = Depends(get_current_user)):
    await _auth_repo(repo_id, user)
    return await _svc().execution_flow(repo_id, node_id, depth)
