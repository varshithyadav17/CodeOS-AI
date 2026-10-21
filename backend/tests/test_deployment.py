"""Deployment-specific failures must leave useful errors and intact data."""
import asyncio

import pytest

from app import database as db
from app.config import async_database_url, settings
from app.prompts import DOC_TYPES
from tests.test_lifecycle import ready_repo


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+asyncpg"])
def test_provider_database_url_preserves_credentials_and_database(scheme):
    suffix = "user:p%40ss%2Fword@db.internal:5432/codeos"
    assert async_database_url(scheme + "://" + suffix) == "postgresql+asyncpg://" + suffix


@pytest.mark.parametrize("operation", ["chat", "docs/generate"])
async def test_slow_ai_request_returns_retryable_error_without_saving_output(logged_in, monkeypatch, operation):
    from app.ai.chat import LlmChat
    client, *_ = logged_in
    repo = await ready_repo(client)
    cancelled = asyncio.Event()

    async def slow_answer(self, message):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    monkeypatch.setattr(LlmChat, "send_message", slow_answer)
    monkeypatch.setattr(settings, "INTERACTIVE_TIMEOUT_SECONDS", 0.2)
    body = {"message": "Where is authentication?"} if operation == "chat" else {"doc_type": next(iter(DOC_TYPES))}
    response = await client.post(f'/api/repos/{repo["id"]}/{operation}', json=body)
    assert response.status_code == 503, response.text
    assert "took too long" in response.json()["detail"]
    assert cancelled.is_set()
    assert await db.get_message_repo().count({}) == 0
    assert await db.get_docs_repo().count({}) == 0
    assert (await client.get("/api/stats")).json()["llm_calls"] == 0
