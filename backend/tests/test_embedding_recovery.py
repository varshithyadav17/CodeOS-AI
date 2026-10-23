"""Quota pauses must retain real parser/graph/Qdrant results and resume safely."""
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from sqlalchemy import select, update
from app import database as db
from app.embedding_limits import EmbeddingBudget, EmbeddingDeferred, embedding_batches, embedding_retry_hint
from app.jobs import enqueue, recover_legacy_embedding_jobs, run_once
from app.stores import vectors as vector_module
from tests.test_lifecycle import source_zip, upload, due_jobs, ready_repo


class Clock:
    def __init__(self):
        self.now = 0.0
        self.waits = []

    async def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


async def test_shared_embedding_budget_paces_inputs_tokens_requests_and_cooldown():
    clock = Clock()
    budget = EmbeddingBudget(5, 8, 12, clock=lambda: clock.now, sleep=clock.sleep)
    await budget.wait(['a' * 12] * 2)  # Eight estimated tokens.
    await budget.wait(['a' * 12] * 2)  # Token budget, not RPM, controls this wait.
    assert clock.now >= 60.5
    budget.defer(180, 'quota')
    before = clock.now
    with pytest.raises(EmbeddingDeferred) as failure:
        await budget.wait(['query'])
    assert failure.value.retry_after == 180 and clock.now == before
    clock.now += 180
    await budget.wait(['query'])
    input_budget = EmbeddingBudget(60, 8, 8000, clock=lambda: clock.now, sleep=clock.sleep)
    await input_budget.wait(['x'] * 8)
    before = clock.now
    await input_budget.wait(['x'])
    assert clock.now - before >= 60.5


def test_batches_limit_inputs_and_estimated_tokens_without_losing_text():
    texts = ['a' * 3000] * 10 + ['large' * 6000, 'last']
    batches = list(embedding_batches(texts))
    assert [item for batch in batches for item in batch] == texts
    assert all(len(batch) <= 8 for batch in batches)
    assert len(batches[0]) == 4


class ProviderError(Exception):
    code = 429
    def __init__(self, details=None):
        self.details = details or {}


def test_provider_retry_hint_distinguishes_long_waits_and_daily_quota(monkeypatch):
    assert embedding_retry_hint(ProviderError()) == (65, 'quota')
    retry = {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '600s'}
    assert embedding_retry_hint(ProviderError({'error': {'details': [retry]}})) == (601, 'quota')
    monkeypatch.setattr('app.embedding_limits.next_daily_reset_seconds', lambda: 3600)
    quota = {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaId': 'EmbedContentPerDay'}]}
    assert embedding_retry_hint(ProviderError({'details': [retry, quota]})) == (3600, 'daily_quota')


async def test_google_429_pauses_once_and_shares_cooldown_with_query_calls(monkeypatch):
    monkeypatch.setattr(vector_module, '_budgets', {})
    embed = AsyncMock(side_effect=ProviderError())
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(embed_content=embed)))
    document, query = vector_module.GeminiEmbedder(), vector_module.GeminiEmbedder()
    document._client = query._client = client
    with pytest.raises(EmbeddingDeferred):
        await document.embed(['source'])
    with pytest.raises(EmbeddingDeferred):
        await query.embed(['question'], query=True)
    assert embed.await_count == 1  # No tight retries or independent query quota bursts.


async def pause_import(client, vectors, monkeypatch):
    original = vectors.embedder.embed
    accepted, calls = [], 0
    async def quota_on_second_batch(texts, query=False):
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise EmbeddingDeferred(65)
        accepted.extend(texts)
        return await original(texts, query=query)
    monkeypatch.setattr(vectors.embedder, 'embed', quota_on_second_batch)
    files = {f'module_{i}.py': f'def function_{i}():\n    return {i}\n' for i in range(30)}
    repo = await upload(client, source_zip(files))
    assert await run_once()
    return repo['id'], original, accepted


async def test_quota_pause_keeps_graph_source_and_checkpoints_then_resumes(logged_in, monkeypatch):
    client, graph, vectors, storage = logged_in
    repo_id, original, accepted = await pause_import(client, vectors, monkeypatch)
    paused = (await client.get(f'/api/repos/{repo_id}')).json()
    assert paused['status'] == 'waiting_embeddings'
    assert paused['stats']['chunks'] == len(accepted) == 8
    assert paused['stats']['chunks_total'] > 8
    node_ids = set(graph.nodes)
    assert node_ids and await vectors.count(repo_id) == 8
    for path in ['graph', 'files', 'architecture/graph?view=dependency']:
        assert (await client.get(f'/api/repos/{repo_id}/{path}')).status_code == 200
    assert (await client.get(f'/api/repos/{repo_id}/files/content?path=module_0.py')).json()['content'].startswith('def function_0')
    assert (await client.post(f'/api/repos/{repo_id}/chat', json={'message': 'test'})).status_code == 409
    assert (await client.post(f'/api/repos/{repo_id}/reingest')).status_code == 409
    async with db.get_engine().connect() as conn:
        job = (await conn.execute(select(db.jobs).where(db.jobs.c.repo_id == repo_id))).mappings().one()
    assert job['status'] == 'retry' and job['attempts'] == 0 and job['next_run_at'] > time.time()
    # Simulate a restart with one Qdrant batch committed but its DB checkpoint missing.
    async with db.get_engine().begin() as conn:
        details = {**job['details'], 'index_checkpoint': {**job['details']['index_checkpoint'], 'offset': 0}}
        await conn.execute(update(db.jobs).where(db.jobs.c.id == job['id']).values(details=details))
    resumed_texts = []
    async def resume(texts, query=False):
        resumed_texts.extend(texts)
        return await original(texts, query=query)
    monkeypatch.setattr(vectors.embedder, 'embed', resume)
    await due_jobs()
    assert await run_once()
    ready = (await client.get(f'/api/repos/{repo_id}')).json()
    assert ready['status'] == 'ready' and ready['progress'] == 100
    assert ready['stats']['chunks'] == ready['stats']['chunks_total'] == await vectors.count(repo_id)
    assert set(graph.nodes) == node_ids and len(storage.objects) == 1
    assert not set(accepted) & set(resumed_texts), 'Completed embeddings were unnecessarily regenerated'


async def test_delete_while_paused_cancels_resume_and_removes_all_stores(logged_in, monkeypatch):
    client, graph, vectors, storage = logged_in
    repo_id, _, _ = await pause_import(client, vectors, monkeypatch)
    assert (await client.delete(f'/api/repos/{repo_id}')).status_code == 202
    assert await run_once()
    await due_jobs()
    assert not await run_once()
    assert (await client.get(f'/api/repos/{repo_id}')).status_code == 404
    assert not graph.nodes and not storage.objects and await vectors.count(repo_id) == 0


async def test_legacy_recovery_is_scoped_idempotent_and_one_time(logged_in):
    client, _, _, _ = logged_in
    eligible, early = await ready_repo(client), await ready_repo(client)
    async with db.get_engine().begin() as conn:
        for repo, progress in [(eligible, 70), (early, 5)]:
            await conn.execute(update(db.repositories).where(db.repositories.c.id == repo['id']).values(status='failed', progress=progress))
            await conn.execute(update(db.jobs).where(db.jobs.c.id == repo['active_job_id']).values(status='failed', error='ClientError'))
    await recover_legacy_embedding_jobs()
    await recover_legacy_embedding_jobs()
    updated = await db.get_repo_repo().get(eligible['id'])
    assert updated.status == 'queued' and updated.active_job_id != eligible['active_job_id']
    assert (await db.get_repo_repo().get(early['id'])).active_job_id == early['active_job_id']
    async with db.get_engine().begin() as conn:
        jobs = (await conn.execute(select(db.jobs).where(db.jobs.c.repo_id == eligible['id']))).mappings().all()
        assert len(jobs) == 2
        await conn.execute(update(db.repositories).where(db.repositories.c.id == eligible['id']).values(status='failed', progress=70))
        await conn.execute(update(db.jobs).where(db.jobs.c.id == updated.active_job_id).values(status='failed', error='ClientError'))
    await recover_legacy_embedding_jobs()
    assert (await db.get_repo_repo().get(eligible['id'])).active_job_id == updated.active_job_id
    with pytest.raises(HTTPException) as error:
        await enqueue(eligible['id'], updated.user_id, expected_failed_job_id=eligible['active_job_id'])
    assert error.value.status_code == 409


async def test_chat_embedding_quota_is_retryable_and_never_saves_fake_answer(logged_in, monkeypatch):
    client, _, vectors, _ = logged_in
    repo = await ready_repo(client)
    monkeypatch.setattr(vectors.embedder, 'embed', AsyncMock(side_effect=EmbeddingDeferred(180)))
    response = await client.post(f"/api/repos/{repo['id']}/chat", json={'message': 'Where is login?'})
    assert response.status_code == 503 and response.headers['retry-after'] == '180'
    assert await db.get_message_repo().count({}) == 0
    docs = await client.post(f"/api/repos/{repo['id']}/docs/generate", json={'doc_type': 'readme'})
    assert docs.status_code == 503 and docs.headers['retry-after'] == '180'


@pytest.mark.parametrize('stderr,exception,message', [
    (b'fatal: Remote branch unknown not found in upstream origin', ValueError, 'Leave Branch empty'),
    (b'fatal: Authentication failed: confidential-provider-detail', ValueError, 'contents read access'),
    (b'fatal: Could not resolve host: github.com', ConnectionError, 'import will retry'),
])
async def test_clone_errors_are_actionable_and_do_not_expose_git_stderr(monkeypatch, tmp_path, stderr, exception, message):
    import app.repository.service as service
    process = SimpleNamespace(returncode=128, communicate=AsyncMock(return_value=(b'', stderr)), wait=AsyncMock())
    monkeypatch.setattr(service, 'validate_git_url', lambda url: url)
    monkeypatch.setattr(service.asyncio, 'create_subprocess_exec', AsyncMock(return_value=process))
    with pytest.raises(exception, match=message) as failure:
        await service.clone_github('https://github.com/example/repo', tmp_path / 'source')
    assert 'confidential-provider-detail' not in str(failure.value)
