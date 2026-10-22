import os
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET"] = "isolated-test-secret-over-thirty-two-characters"
os.environ["NEO4J_PASSWORD"] = "isolated-test-password"
os.environ["GEMINI_API_KEY"] = "test-provider-is-stubbed"
os.environ["WORKER_ENABLED"] = "false"

import pytest
from functools import lru_cache
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient
from app import database as db
from app.config import settings
from app.main import app
from app.stores.vectors import QdrantVectorStore
from tests.fakes import TestEmbedder, TestGraph, TestStorage


@pytest.fixture
async def system(tmp_path, monkeypatch):
    if db._engine:
        await db._engine.dispose()
        db._engine = None
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///" + str(tmp_path / "test.sqlite"))
    async with db.get_engine().begin() as conn:
        await conn.run_sync(db.metadata.create_all)
    graph, storage = TestGraph(), TestStorage()
    vectors = QdrantVectorStore(client=AsyncQdrantClient(location=":memory:"), embedder=TestEmbedder())
    await vectors.initialize()
    monkeypatch.setattr(db, "get_graph_service", lru_cache()(lambda: graph))
    monkeypatch.setattr(db, "get_storage", lru_cache()(lambda: storage))
    monkeypatch.setattr(db, "get_vector_store", lru_cache()(lambda: vectors))
    import app.ai.routes as ai_routes
    monkeypatch.setattr(ai_routes, "get_graph_service", db.get_graph_service)
    monkeypatch.setattr(ai_routes, "get_vector_store", db.get_vector_store)
    from app.ai.chat import LlmChat
    async def answer(self, message):
        return "Authentication is implemented in [auth.py:1-2]. The login route calls authenticate."
    monkeypatch.setattr(LlmChat, "send_message", answer)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, graph, vectors, storage
    await vectors.close()
    await db.get_engine().dispose()
    db._engine = None


@pytest.fixture
async def logged_in(system):
    client, graph, vectors, storage = system
    response = await client.post("/api/auth/signup", json={"email": "alice@example.com", "name": "Alice", "password": "correct-horse-123"})
    assert response.status_code == 200, response.text
    return system
