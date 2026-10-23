"""Authorized repository APIs. Request handlers queue expensive work in PostgreSQL."""
from __future__ import annotations
import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, insert, select
from ..auth.auth import get_current_user
from .. import database as db
from ..config import settings
from ..jobs import enqueue, repository_guard
from ..security import encrypt_credential
from ..models import ActivityEvent, Repository, User
from ..schemas import GithubIn
from ..utils import blocking
from .archive import UnsafeZipError, normalized_path, read_source, sha256, validate_archive
from .service import validate_branch, validate_git_url

router = APIRouter(tags=["repos"])


async def authorized_repo(repo_id, user, ready=False):
    repo = await db.get_repo_repo().get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(404, "Repository not found")
    if ready and (repo.status not in {"ready", "embedding", "waiting_embeddings"} or not repo.file_manifest):
        raise HTTPException(409, "Repository parsing must finish before using this feature.")
    return repo


async def reserve_repo(user, name, source, **extra):
    repo = Repository(user_id=user.id, name=name[:200], source=source, **extra)
    repo.archive_key = db.get_storage().key(user.id, repo.id)
    async with db.get_engine().begin() as conn:
        # Serializes concurrent imports by the same owner, including quota checks.
        await conn.execute(select(db.users.c.id).where(db.users.c.id == user.id).with_for_update())
        count = (await conn.execute(select(func.count()).select_from(db.repositories).where(db.repositories.c.user_id == user.id))).scalar_one()
        if count >= settings.MAX_REPOSITORIES_PER_USER:
            raise HTTPException(409, "Repository limit reached. Delete an existing repository first.")
        data = repo.model_dump(mode="json")
        data.update(file_manifest=[], timeline={})
        await conn.execute(insert(db.repositories).values(**data))
    return repo


@router.get("/repos")
async def list_repos(user: User = Depends(get_current_user), limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
    items = await db.get_repo_repo().list({"user_id": user.id}, limit=limit, offset=offset, sort=[("created_at", -1)])
    return [r.model_dump() for r in items]


@router.post("/repos/github", status_code=202)
async def add_github(body: GithubIn, user: User = Depends(get_current_user)):
    try:
        url = validate_git_url(body.url.strip(), resolve=False)
        validate_branch(body.branch)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    name = url.rsplit("/", 1)[-1].removesuffix(".git")
    repo = await reserve_repo(user, name, "github", source_url=url, branch=body.branch)
    details = {}
    if body.token:
        token = body.token.get_secret_value()
        if len(token) > 500 or "\n" in token or "\r" in token:
            await db.get_repo_repo().delete(repo.id)
            raise HTTPException(400, "Invalid GitHub access token.")
        details["github_credential"] = encrypt_credential(token)
    await enqueue(repo.id, user.id, details=details)
    await db.get_activity_repo().insert(ActivityEvent(user_id=user.id, repo_id=repo.id, type="repo_added", message=f"Added GitHub repository {name}"))
    return (await db.get_repo_repo().get(repo.id)).model_dump()


@router.post("/repos/upload", status_code=202)
async def upload_zip(file: UploadFile = File(...), name: str | None = Form(None), user: User = Depends(get_current_user)):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(400, "Only .zip uploads are supported.")
    try:
        with tempfile.TemporaryDirectory(prefix="codeos-upload-") as temporary:
            path = Path(temporary) / "source.zip"
            size = 0
            with path.open("wb") as output:
                while block := await file.read(1024 * 1024):
                    size += len(block)
                    if size > settings.MAX_ARCHIVE_BYTES:
                        raise HTTPException(413, "Archive exceeds the configured upload size limit.")
                    await blocking(output.write, block)
            try:
                await blocking(validate_archive, path)
            except UnsafeZipError as exc:
                raise HTTPException(400, str(exc))
            checksum = await blocking(sha256, path)
            repo_name = (name or Path(file.filename).stem).strip()
            if not repo_name or len(repo_name) > 200 or any(ord(c) < 32 for c in repo_name):
                raise HTTPException(400, "Repository name must be 1–200 printable characters.")
            # An interrupted upload stays visible and deletable, including its stable S3 key.
            repo = await reserve_repo(user, repo_name, "zip", status="failed", archive_sha256=checksum,
                message="Archive upload did not finish. Delete this entry and upload again.")
            async with repository_guard(repo.id):
                latest=await authorized_repo(repo.id,user)
                if latest.status in {"deleting","delete_failed"}:
                    raise HTTPException(409,"Repository deletion has already started.")
                try:
                    await db.get_storage().put_archive(repo.archive_key, path, checksum)
                except Exception:
                    raise HTTPException(503, "Archive storage is unavailable. Check service health and retry the upload.")
                await enqueue(repo.id, user.id)
            await db.get_activity_repo().insert(ActivityEvent(user_id=user.id, repo_id=repo.id, type="repo_added", message=f"Uploaded {repo_name}"))
            return (await db.get_repo_repo().get(repo.id)).model_dump()
    finally:
        await file.close()


@router.get("/repos/{repo_id}")
async def get_repo(repo_id: str, user: User = Depends(get_current_user)):
    return (await authorized_repo(repo_id, user)).model_dump()


@router.get("/repos/{repo_id}/status")
async def get_status(repo_id: str, user: User = Depends(get_current_user)):
    repo = await authorized_repo(repo_id, user)
    return {"status": repo.status, "progress": repo.progress, "message": repo.message, "stats": repo.stats.model_dump(), "active_job_id": repo.active_job_id}


@router.get("/repos/{repo_id}/jobs")
async def get_jobs(repo_id: str, user: User = Depends(get_current_user), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    await authorized_repo(repo_id, user)
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(db.jobs).where(db.jobs.c.repo_id == repo_id).order_by(db.jobs.c.created_at.desc()).limit(limit).offset(offset))).mappings().all()
    return [{**{k: v for k, v in row.items() if k not in {"lease_token", "lease_until", "details"}}, "details": {k: v for k, v in row["details"].items() if k != "github_credential"}} for row in rows]


@router.delete("/repos/{repo_id}", status_code=202)
async def delete_repo(repo_id: str, user: User = Depends(get_current_user)):
    await authorized_repo(repo_id, user)
    job = await enqueue(repo_id, user.id, "delete")
    return {"ok": True, "job_id": job["id"], "status": "deleting"}


@router.post("/repos/{repo_id}/reingest", status_code=202)
async def reingest(repo_id: str, user: User = Depends(get_current_user)):
    repo = await authorized_repo(repo_id, user)
    if not repo.archive_sha256:
        if repo.source != "github":
            raise HTTPException(409, "No archive exists; upload the repository again.")
    details = {}
    if repo.source == "github" and not repo.archive_sha256 and repo.active_job_id:
        async with db.get_engine().connect() as conn:
            previous = (await conn.execute(select(db.jobs.c.details).where(db.jobs.c.id == repo.active_job_id))).scalar_one_or_none()
        if previous and previous.get("github_credential"):
            details["github_credential"] = previous["github_credential"]
    job = await enqueue(repo_id, user.id, details=details)
    return {"ok": True, "job_id": job["id"]}


@router.get("/repos/{repo_id}/graph")
async def get_graph(repo_id: str, user: User = Depends(get_current_user),
    limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0), type: str | None = None):
    await authorized_repo(repo_id, user, ready=True)
    graph = db.get_graph_service()
    page = await graph.list_nodes(repo_id, type_=type, limit=limit + 1, offset=offset)
    nodes = page[:limit]
    edges = await graph.list_edges(repo_id, limit=10001, node_ids=[n.id for n in nodes])
    return {"nodes": [n.model_dump() for n in nodes], "edges": [e.model_dump() for e in edges[:10000]],
        "offset": offset, "limit": limit, "has_more": len(page) > limit,
        "total": await graph.count_nodes(repo_id) if type is None else None,
        "edges_truncated": len(edges) > 10000}


@router.get("/repos/{repo_id}/graph/node/{node_id}")
async def get_node_detail(repo_id: str, node_id: str, user: User = Depends(get_current_user)):
    await authorized_repo(repo_id, user, ready=True)
    graph = db.get_graph_service()
    node = await graph.get_node(repo_id, node_id)
    if not node:
        raise HTTPException(404, "Node not found")
    neighbors = await graph.neighbors(repo_id, node_id, depth=1)
    return {"node": node.model_dump(), "neighbors": [n.model_dump() for n in neighbors["nodes"]], "edges": [e.model_dump() for e in neighbors["edges"]]}


@router.get("/repos/{repo_id}/files")
async def list_files(repo_id: str, user: User = Depends(get_current_user), limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)):
    repo = await authorized_repo(repo_id, user, ready=True)
    return [{k: v for k, v in f.items() if k != "archive_path"} for f in repo.file_manifest[offset:offset+limit]]


@router.get("/repos/{repo_id}/files/content")
async def get_file_content(repo_id: str, path: str, user: User = Depends(get_current_user)):
    repo = await authorized_repo(repo_id, user, ready=True)
    try:
        normalized_path(path)
    except UnsafeZipError as exc:
        raise HTTPException(400, str(exc))
    item = next((f for f in repo.file_manifest if f["path"] == path), None)
    if not item:
        raise HTTPException(404, "Indexed file not found")
    with tempfile.TemporaryDirectory(prefix="codeos-preview-") as temporary:
        archive = Path(temporary) / "source.zip"
        try:
            await db.get_storage().get_archive(repo.archive_key, archive)
            if await blocking(sha256, archive) != repo.archive_sha256:
                raise ValueError("Repository archive checksum verification failed.")
            content = await blocking(read_source, archive, item["archive_path"])
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(400, str(exc))
    return {"content": content, "path": path, "language": item["language"]}


@router.get("/stats")
async def stats(user: User = Depends(get_current_user)):
    repos = await db.get_repo_repo().list({"user_id": user.id}, limit=10000)
    conversations = await db.get_conversation_repo().list({"user_id": user.id}, limit=10000)
    count = await db.get_message_repo().count({"conversation_id": {"$in": [c.id for c in conversations]}, "role": "assistant"})
    recent = await db.get_activity_repo().list({"user_id": user.id}, limit=15, sort=[("created_at", -1)])
    return {"repos_count": len(repos), "files_indexed": sum(r.stats.files for r in repos),
        "nodes": sum(r.stats.nodes for r in repos), "edges": sum(r.stats.edges for r in repos),
        "chunks": sum(r.stats.chunks for r in repos), "llm_calls": count,
        "recent_activity": [a.model_dump() for a in recent]}
