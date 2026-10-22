"""AI support services: DocGenService."""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, insert, update

from ..config import settings
from .. import database as db
from ..database import DictRepo, IGraphService, IVectorStore
from ..models import Repository
from ..prompts import DOC_GEN_SYSTEM, DOC_TYPES
from .chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DocGenService
# ---------------------------------------------------------------------------

class DocGenService:
    def __init__(self, docs: DictRepo, graph: IGraphService, vectors: IVectorStore):
        self.docs = docs
        self.graph = graph
        self.vectors = vectors

    async def _context(self, repo: Repository) -> str:
        files = await self.graph.list_nodes(repo.id, type_="file", limit=200)
        classes = await self.graph.list_nodes(repo.id, type_="class", limit=80)
        functions = await self.graph.list_nodes(repo.id, type_="function", limit=120)
        chunks = await self.vectors.query(
            repo.id, "main entry api route handler model controller", k=15
        )
        lines = [
            f"# Repository: {repo.name}",
            f"Source: {repo.source_url or repo.source}",
            f"Languages: {repo.language_breakdown}",
            f"Stats: {repo.stats.model_dump()}",
            "\n## Files",
            *[f"- {f.file_path} ({f.metadata.get('loc', 0)} loc)" for f in files[:80]],
            "\n## Classes",
            *[f"- {c.qualified_name}" for c in classes[:40]],
            "\n## Functions",
            *[f"- {fn.qualified_name}" for fn in functions[:60]],
            "\n## Code samples",
        ]
        for c in chunks[:10]:
            lines.append(f"\n--- {c.file_path}:{c.start_line} ---\n{c.text[:1000]}")
        return "\n".join(lines)

    async def generate(self, repo: Repository, doc_type: str, user_id: str) -> dict:
        spec = DOC_TYPES.get(doc_type)
        if not spec:
            raise ValueError("Unknown doc type")
        ctx = await self._context(repo)
        chat = LlmChat(
            api_key=settings.GEMINI_API_KEY,
            session_id=f"docs-{repo.id}-{doc_type}-{uuid.uuid4().hex[:6]}",
            system_message=DOC_GEN_SYSTEM,
        ).with_model("gemini", settings.LLM_MODEL)
        prompt = f"Generate: {spec}\n\nRepository context:\n{ctx}\n\nReturn only Markdown."
        raw = await chat.send_message(UserMessage(text=prompt))
        text = raw if isinstance(raw, str) else getattr(raw, "content", str(raw))
        now = datetime.now(timezone.utc).isoformat()
        async with db.get_engine().begin() as conn:
            # Serialize concurrent saves; deletion cannot leave an orphan.
            row = (await conn.execute(select(db.repositories.c.status).where(db.repositories.c.id == repo.id,
                db.repositories.c.user_id == user_id).with_for_update())).first()
            if not row or row.status != "ready":
                raise HTTPException(409, "Repository changed during generation. Try again when it is ready.")
            existing = (await conn.execute(select(db.documentation).where(db.documentation.c.repo_id == repo.id,
                db.documentation.c.user_id == user_id, db.documentation.c.doc_type == doc_type))).mappings().first()
            if existing:
                await conn.execute(update(db.documentation).where(db.documentation.c.id == existing["id"]).values(content=text, updated_at=now))
                return {**existing, "content": text, "updated_at": now}
            doc = {"id": str(uuid.uuid4()), "repo_id": repo.id, "user_id": user_id,
                "doc_type": doc_type, "content": text, "created_at": now, "updated_at": now}
            await conn.execute(insert(db.documentation).values(**doc))
            return doc
