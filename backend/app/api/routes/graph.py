"""Graph viewing routes."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import get_current_user
from ...core.container import get_repo_repo, get_graph_service
from ...core.models.user import User

router = APIRouter(prefix="/repos", tags=["graph"])


@router.get("/{repo_id}/graph")
async def get_graph(
    repo_id: str,
    user: User = Depends(get_current_user),
    limit: int = Query(200, ge=10, le=1000),
    type: str | None = None,
):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    g = get_graph_service()
    nodes = await g.list_nodes(repo_id, type_=type, limit=limit)
    node_ids = {n.id for n in nodes}
    all_edges = await g.list_edges(repo_id, limit=2000)
    edges = [e for e in all_edges if e.source_id in node_ids and e.target_id in node_ids]
    return {"nodes": [n.model_dump() for n in nodes], "edges": [e.model_dump() for e in edges]}


@router.get("/{repo_id}/graph/node/{node_id}")
async def get_node_detail(repo_id: str, node_id: str, user: User = Depends(get_current_user)):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    g = get_graph_service()
    node = await g.get_node(repo_id, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    data = await g.neighbors(repo_id, node_id, depth=1)
    return {"node": node.model_dump(), "neighbors": [n.model_dump() for n in data["nodes"]], "edges": [e.model_dump() for e in data["edges"]]}


@router.get("/{repo_id}/files")
async def list_files(repo_id: str, user: User = Depends(get_current_user)):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    g = get_graph_service()
    nodes = await g.list_nodes(repo_id, type_="file", limit=1000)
    return [{"path": n.file_path, "language": n.language, "loc": n.metadata.get("loc", 0)} for n in nodes]
