"""Dashboard stats route."""
from __future__ import annotations
from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ...core.container import get_repo_repo, get_graph_service, get_vector_store, get_activity_repo, get_message_repo
from ...core.models.user import User

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def stats(user: User = Depends(get_current_user)):
    repos = get_repo_repo()
    user_repos = await repos.list({"user_id": user.id}, limit=500)
    repo_ids = [r.id for r in user_repos]
    files_indexed = sum(r.stats.files for r in user_repos)
    nodes_count = sum(r.stats.nodes for r in user_repos)
    edges_count = sum(r.stats.edges for r in user_repos)
    chunks_count = sum(r.stats.chunks for r in user_repos)
    msgs = get_message_repo()
    llm_calls = await msgs.count({"role": "assistant"})  # approx
    acts = get_activity_repo()
    recent = await acts.list({"user_id": user.id}, limit=15, sort=[("created_at", -1)])
    return {
        "repos_count": len(user_repos),
        "files_indexed": files_indexed,
        "nodes": nodes_count,
        "edges": edges_count,
        "chunks": chunks_count,
        "llm_calls": llm_calls,
        "recent_activity": [a.model_dump() for a in recent],
    }
