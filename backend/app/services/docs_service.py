"""AI Documentation Generator — Gemini-powered, grounded on KG + chunks + memory."""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from ..llm.chat_compat import LlmChat, UserMessage

from ..core.config import settings
from ..core.interfaces.metadata import IMetadataRepository
from ..core.interfaces.graph import IGraphService
from ..core.interfaces.vector import IVectorStore
from ..core.models.repository import Repository

logger = logging.getLogger(__name__)

DOC_TYPES = {
    "readme": "Professional README.md with badges, install, usage, features, license sections",
    "api": "Complete API documentation (endpoints, methods, params, responses, examples)",
    "architecture": "Architecture documentation: components, layers, data flow, diagrams in Mermaid",
    "modules": "Module-by-module documentation with responsibilities & key classes",
    "setup": "Developer setup guide: prereqs, install, env vars, run commands",
    "developer": "Developer guide: coding conventions, contribution, testing",
    "structure": "Folder structure documentation explaining every top-level directory",
    "database": "Database documentation: schema, tables/collections, relationships",
    "dependency": "Dependency documentation: libraries used and why",
    "pipeline": "AI/Data pipeline documentation if applicable",
}

SYSTEM = """You are a senior technical writer. Generate clear, accurate, professional GitHub-flavored Markdown documentation grounded ONLY in the provided repository context. Use proper headings, code blocks, lists, tables, and Mermaid diagrams when useful. Never fabricate APIs or features not present in the context."""


class DocGenService:
    def __init__(self, docs: IMetadataRepository, graph: IGraphService, vectors: IVectorStore):
        self.docs = docs; self.graph = graph; self.vectors = vectors

    async def _context(self, repo: Repository) -> str:
        files = await self.graph.list_nodes(repo.id, type_="file", limit=200)
        classes = await self.graph.list_nodes(repo.id, type_="class", limit=80)
        functions = await self.graph.list_nodes(repo.id, type_="function", limit=120)
        chunks = await self.vectors.query(repo.id, "main entry api route handler model controller", k=15)
        lines = [
            f"# Repository: {repo.name}",
            f"Source: {repo.source_url or repo.source}",
            f"Languages: {repo.language_breakdown}",
            f"Stats: {repo.stats.model_dump()}",
            "\n## Files", *[f"- {f.file_path} ({f.metadata.get('loc',0)} loc)" for f in files[:80]],
            "\n## Classes", *[f"- {c.qualified_name}" for c in classes[:40]],
            "\n## Functions", *[f"- {fn.qualified_name}" for fn in functions[:60]],
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
        chat = LlmChat(api_key=settings.GEMINI_API_KEY,
                       session_id=f"docs-{repo.id}-{doc_type}-{uuid.uuid4().hex[:6]}",
                       system_message=SYSTEM).with_model("gemini", settings.LLM_MODEL)
        prompt = f"Generate: {spec}\n\nRepository context:\n{ctx}\n\nReturn only Markdown."
        raw = await chat.send_message(UserMessage(text=prompt))
        text = raw if isinstance(raw, str) else getattr(raw, "content", str(raw))
        # Upsert
        existing = await self.docs.find_one({"repo_id": repo.id, "doc_type": doc_type, "user_id": user_id})
        now = datetime.now(timezone.utc).isoformat()
        if existing:
            await self.docs.update(existing["id"], {"content": text, "updated_at": now})
            doc = {**existing, "content": text, "updated_at": now}
        else:
            doc = {"id": str(uuid.uuid4()), "repo_id": repo.id, "user_id": user_id,
                   "doc_type": doc_type, "content": text, "created_at": now, "updated_at": now}
            await self.docs.insert(doc)
        return doc
