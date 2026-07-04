"""Repository routes: upload, list, status, delete, reingest."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form
from pydantic import BaseModel

from ..deps import get_current_user, get_ingestion_service
from ...core.container import get_repo_repo, get_graph_service, get_vector_store, get_storage, get_activity_repo
from ...core.models.user import User
from ...core.models.repository import Repository, RepoStatus
from ...core.models.activity import ActivityEvent
from ...services.ingestion_service import IngestionService, UnsafeGitURLError, validate_git_url

router = APIRouter(prefix="/repos", tags=["repos"])


class GithubIn(BaseModel):
    url: str
    branch: str | None = None


def _name_from_url(url: str) -> str:
    base = url.rstrip("/").split("/")[-1]
    return base.removesuffix(".git") or "repo"


@router.get("")
async def list_repos(user: User = Depends(get_current_user)):
    repos = get_repo_repo()
    items = await repos.list({"user_id": user.id}, limit=200, sort=[("created_at", -1)])
    return [r.model_dump() for r in items]


@router.post("/github")
async def add_github(body: GithubIn, bg: BackgroundTasks, user: User = Depends(get_current_user), ingest: IngestionService = Depends(get_ingestion_service)):
    try:
        validate_git_url(body.url)
    except UnsafeGitURLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid or disallowed repository URL: {e}")
    repos = get_repo_repo()
    storage = get_storage()
    name = _name_from_url(body.url)
    repo = Repository(
        user_id=user.id, name=name, source="github",
        source_url=body.url, branch=body.branch,
        local_path="",  # set after clone
        status=RepoStatus.QUEUED,
    )
    await repos.insert(repo)
    await storage.ensure_dir(f"repos/{repo.id}")
    await get_activity_repo().insert(ActivityEvent(user_id=user.id, repo_id=repo.id, type="repo_added", message=f"Added GitHub repo {name}"))
    bg.add_task(ingest.kickoff, repo, body.url, None)
    return repo.model_dump()


@router.post("/upload")
async def upload_zip(bg: BackgroundTasks, file: UploadFile = File(...), name: str = Form(None), user: User = Depends(get_current_user), ingest: IngestionService = Depends(get_ingestion_service)):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip uploads are supported")
    data = await file.read()
    if len(data) > 200 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="ZIP too large (200MB max)")
    repos = get_repo_repo()
    storage = get_storage()
    repo_name = name or file.filename.rsplit(".", 1)[0]
    repo = Repository(user_id=user.id, name=repo_name, source="zip", local_path="", status=RepoStatus.QUEUED)
    await repos.insert(repo)
    await storage.ensure_dir(f"repos/{repo.id}")
    await get_activity_repo().insert(ActivityEvent(user_id=user.id, repo_id=repo.id, type="repo_added", message=f"Uploaded ZIP repo {repo_name}"))
    bg.add_task(ingest.kickoff, repo, None, data)
    return repo.model_dump()


@router.get("/{repo_id}")
async def get_repo(repo_id: str, user: User = Depends(get_current_user)):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo.model_dump()


@router.get("/{repo_id}/status")
async def get_status(repo_id: str, user: User = Depends(get_current_user)):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    return {"status": repo.status, "progress": repo.progress, "message": repo.message, "stats": repo.stats.model_dump()}


@router.delete("/{repo_id}")
async def delete_repo(repo_id: str, user: User = Depends(get_current_user)):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    await get_graph_service().delete_repo(repo_id)
    await get_vector_store().delete_namespace(repo_id)
    await get_storage().delete(f"repos/{repo_id}")
    await repos.delete(repo_id)
    return {"ok": True}


@router.post("/{repo_id}/reingest")
async def reingest(repo_id: str, bg: BackgroundTasks, user: User = Depends(get_current_user), ingest: IngestionService = Depends(get_ingestion_service)):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    await get_graph_service().delete_repo(repo_id)
    await get_vector_store().delete_namespace(repo_id)
    if repo.source == "github" and repo.source_url:
        bg.add_task(ingest.kickoff, repo, repo.source_url, None)
    else:
        # Re-parse from cached local_path
        from pathlib import Path
        local = Path(repo.local_path) if repo.local_path else None
        if local and local.exists():
            # quick path: parse without re-extracting
            async def _runner():
                await ingest._update(repo.id, RepoStatus.PARSING, 25, "Reparsing")
                parsed = await asyncio.to_thread(ingest.parser.parse_repo, local)
                from ...core.models.repository import RepoStats
                nodes, edges = ingest.builder.build(repo.id, parsed)
                await ingest.graph.upsert_nodes(nodes); await ingest.graph.upsert_edges(edges)
                qmap = {n.qualified_name: n.id for n in nodes}
                chunks = ingest.embedder.build_chunks(repo.id, parsed, qmap)
                await ingest.vectors.upsert(chunks)
                total_loc = sum(f.loc for f in parsed)
                lang = {}
                for f in parsed:
                    lang[f.language] = lang.get(f.language, 0) + 1
                stats = RepoStats(files=len(parsed), loc=total_loc, nodes=len(nodes), edges=len(edges), chunks=len(chunks))
                await ingest.repos.update(repo.id, {"status": RepoStatus.READY.value, "progress": 100, "message": "Ready",
                                                     "language_breakdown": lang, "stats": stats.model_dump()})
            bg.add_task(_runner)
        else:
            raise HTTPException(status_code=400, detail="No source available to reingest")
    return {"ok": True}
