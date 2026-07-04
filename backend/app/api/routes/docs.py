"""AI Documentation routes."""
from __future__ import annotations
import io, zipfile, json
from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..deps import get_current_user
from ...core.container import get_repo_repo, get_graph_service, get_vector_store
from ...core.models.user import User
from ...services.docs_service import DocGenService, DOC_TYPES
from ...infrastructure.mongodb import db

router = APIRouter(tags=["docs"])


class _DictRepo:
    def __init__(self, coll): self.coll = coll
    async def insert(self, d): await self.coll.insert_one(dict(d)); return d
    async def get(self, i): r = await self.coll.find_one({"id": i}, {"_id": 0}); return r
    async def find_one(self, q): return await self.coll.find_one(q, {"_id": 0})
    async def list(self, q, limit=200, sort=None):
        cur = self.coll.find(q or {}, {"_id": 0})
        if sort: cur = cur.sort(sort)
        return await cur.to_list(length=limit)
    async def update(self, i, patch): await self.coll.update_one({"id": i}, {"$set": patch})
    async def delete(self, i): r = await self.coll.delete_one({"id": i}); return r.deleted_count > 0
    async def count(self, q): return await self.coll.count_documents(q or {})


@lru_cache
def _docs_repo(): return _DictRepo(db["documentation"])


def _svc(): return DocGenService(_docs_repo(), get_graph_service(), get_vector_store())


class GenIn(BaseModel):
    doc_type: str


@router.get("/repos/{repo_id}/docs/types")
async def doc_types(user: User = Depends(get_current_user)):
    return [{"key": k, "label": v} for k, v in DOC_TYPES.items()]


@router.get("/repos/{repo_id}/docs")
async def list_docs(repo_id: str, user: User = Depends(get_current_user)):
    repo = await get_repo_repo().get(repo_id)
    if not repo or repo.user_id != user.id: raise HTTPException(404, "Repository not found")
    items = await _docs_repo().list({"repo_id": repo_id, "user_id": user.id}, limit=50, sort=[("updated_at", -1)])
    return items


@router.post("/repos/{repo_id}/docs/generate")
async def generate(repo_id: str, body: GenIn, user: User = Depends(get_current_user)):
    repo = await get_repo_repo().get(repo_id)
    if not repo or repo.user_id != user.id: raise HTTPException(404, "Repository not found")
    if repo.status != "ready": raise HTTPException(400, "Repository not ready")
    if body.doc_type not in DOC_TYPES: raise HTTPException(400, "Unknown doc type")
    doc = await _svc().generate(repo, body.doc_type, user.id)
    return doc


@router.get("/repos/{repo_id}/docs/export")
async def export_zip(repo_id: str, user: User = Depends(get_current_user)):
    repo = await get_repo_repo().get(repo_id)
    if not repo or repo.user_id != user.id: raise HTTPException(404, "Repository not found")
    items = await _docs_repo().list({"repo_id": repo_id, "user_id": user.id}, limit=50)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in items:
            name = f"{d['doc_type']}.md"
            z.writestr(name, d.get("content", ""))
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{repo.name}-docs.zip"'})
