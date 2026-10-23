"""Isolated browser-test server. Never use this test harness as a deployment entry point."""
import os
import json
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
work = Path(tempfile.mkdtemp(prefix="codeos-ui-test-"))
os.environ.update(ENV="test", DATABASE_URL="sqlite+aiosqlite:///"+str(work/"app.sqlite"),
    JWT_SECRET="browser-test-only-secret-over-thirty-two-characters", NEO4J_PASSWORD="test-password",
    GEMINI_API_KEY="test-provider-stub", WORKER_ENABLED="true", JOB_POLL_SECONDS="0.1",
    AUTH_COOKIE_SECURE="false", AUTH_COOKIE_SAMESITE="lax", GOOGLE_CLIENT_ID="browser-test.apps.googleusercontent.com",
    CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173")

import asyncio
import uvicorn
from qdrant_client import AsyncQdrantClient
from app import database as db
from app.main import app
from app.stores.vectors import QdrantVectorStore
from app.ai.chat import LlmChat
from tests.fakes import TestGraph, TestStorage, TestEmbedder
import app.ai.routes as ai_routes
import app.auth.auth as auth_routes

# Isolated harness only: the real verifier is exercised in test_google_auth.py.
auth_routes.verify_google_credential = json.loads


db.get_graph_service = lru_cache()(lambda: TestGraph())
db.get_storage = lru_cache()(lambda: TestStorage())
class BrowserEmbedder(TestEmbedder):
    async def embed(self, texts, query=False):
        if any("CODEOS_QUOTA_TEST" in text for text in texts):
            from app.embedding_limits import EmbeddingDeferred
            raise EmbeddingDeferred(3600)
        return await super().embed(texts, query=query)


db.get_vector_store = lru_cache()(lambda: QdrantVectorStore(client=AsyncQdrantClient(location=":memory:"), embedder=BrowserEmbedder()))
ai_routes.get_graph_service = db.get_graph_service
ai_routes.get_vector_store = db.get_vector_store


async def answer(self, message):
    if self.session_id.startswith("docs-"):
        return "# Repository documentation\n\nAuthentication is handled in `auth.py`.\n\n## Entry point\n\n`api.py` calls `authenticate`.\n"
    if self.session_id.startswith("review-manager-"):
        return json.dumps({"executive_summary": "Review complete using supplied source evidence.", "action_plan": ["Add regression tests for token validation."]})
    if self.session_id.startswith("review-"):
        return json.dumps({"summary": "Checked the supplied source evidence.", "score": 85,
            "findings": [{"category": "testing", "title": "Add token tests", "description": "Cover token validation in auth.py.",
                "severity": "low", "confidence": 0.8, "file_path": "auth.py", "line": 1}]})
    return "Authentication is handled by `authenticate` in [auth.py:1-2]. `login` calls it in [api.py:3-4]."


LlmChat.send_message = answer


async def prepare():
    async with db.get_engine().begin() as conn:
        await conn.run_sync(db.metadata.create_all)
    await db.get_vector_store().initialize()
    await db.get_engine().dispose()


if __name__ == "__main__":
    try:
        asyncio.run(prepare())
        uvicorn.run(app,host="127.0.0.1",port=8000)
    finally:
        shutil.rmtree(work,ignore_errors=True)
