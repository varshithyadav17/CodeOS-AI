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


async def test_qdrant_outage_keeps_files_and_graph_and_resumes_without_rebuilding(logged_in, monkeypatch):
    import httpx
    from qdrant_client.http.exceptions import ResponseHandlingException

    client, graph, vectors, storage = logged_in
    repo_id = (await upload(client))["id"]
    original = vectors.client.collection_exists

    async def unreachable(*args, **kwargs):
        raise ResponseHandlingException(httpx.ConnectError("Qdrant unavailable"))

    monkeypatch.setattr(vectors.client, "collection_exists", unreachable)
    assert await run_once()
    endpoint = f"/api/repos/{repo_id}"
    paused = (await client.get(endpoint)).json()
    assert paused["status"] == "waiting_embeddings"
    assert paused["stats"]["chunks"] == 0
    assert "Your files and graph are saved" in paused["message"]
    assert (await client.get(endpoint + "/files/content?path=auth.py")).status_code == 200
    assert (await client.get(endpoint + "/graph")).json()["nodes"]
    graph_ids = set(graph.nodes)
    assert len(storage.objects) == 1
    jobs = (await client.get(endpoint + "/jobs")).json()
    assert jobs[0]["attempts"] == 0 and jobs[0]["status"] == "retry"
    assert jobs[0]["next_run_at"] > time.time()

    monkeypatch.setattr(vectors.client, "collection_exists", original)
    fail_rebuild = AsyncMock(side_effect=AssertionError("Existing graph must be reused"))
    monkeypatch.setattr(graph, "delete_repo", fail_rebuild)
    await due_jobs()
    assert await run_once()
    ready = (await client.get(endpoint)).json()
    assert ready["status"] == "ready" and ready["stats"]["chunks"] > 0
    assert set(graph.nodes) == graph_ids
    fail_rebuild.assert_not_awaited()


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


async def test_background_pacing_yields_without_sleeping_or_reserving_capacity():
    clock = Clock()
    budget = EmbeddingBudget(20, 80, 100, clock=lambda: clock.now, sleep=clock.sleep)
    await budget.wait(['a' * 240], max_wait=5)  # 80 estimated tokens.
    with pytest.raises(EmbeddingDeferred) as failure:
        await budget.wait(['b' * 240], max_wait=5)
    assert failure.value.reason == 'pacing' and failure.value.retry_after >= 60
    assert clock.now == 0 and not clock.waits
    assert len(budget.events) == 1 and not budget.lock.locked()
    # A small interactive query can use remaining tokens without waiting for
    # the background document's larger request or holding its queue lock.
    clock.now = 4
    await budget.wait(['query'])
    assert clock.now == 4 and len(budget.events) == 2


async def test_waiting_embedding_request_releases_lock_and_rechecks_shared_cooldown():
    import asyncio
    started, resume = asyncio.Event(), asyncio.Event()
    current = [0.0]

    async def sleep(delay):
        started.set()
        await resume.wait()
        current[0] += delay

    budget = EmbeddingBudget(20, 80, 24000, clock=lambda: current[0], sleep=sleep)
    await budget.wait(['source'])
    waiting = asyncio.create_task(budget.wait(['next']))
    await started.wait()
    assert not budget.lock.locked()
    budget.defer(180, 'quota')
    resume.set()
    with pytest.raises(EmbeddingDeferred) as failure:
        await waiting
    assert failure.value.reason == 'quota' and len(budget.events) == 1


async def test_reingest_unchanged_archive_reuses_completed_embeddings(logged_in, monkeypatch):
    client, graph, vectors, storage = logged_in
    repo = await ready_repo(client)
    previous_nodes = set(graph.nodes)
    embed = AsyncMock(side_effect=AssertionError('Unchanged code must reuse its saved embeddings'))
    monkeypatch.setattr(vectors.embedder, 'embed', embed)
    assert (await client.post(f"/api/repos/{repo['id']}/reingest")).status_code == 202
    assert await run_once()
    updated = (await client.get(f"/api/repos/{repo['id']}")).json()
    assert updated['status'] == 'ready' and updated['stats'] == repo['stats']
    assert set(graph.nodes) == previous_nodes and len(storage.objects) == 1
    assert embed.await_count == 0


async def test_reingest_repairs_a_missing_vector_index_instead_of_accepting_cached_counts(logged_in, monkeypatch):
    client, _, vectors, _ = logged_in
    repo = await ready_repo(client)
    await vectors.delete_namespace(repo['id'])
    embed = AsyncMock(wraps=vectors.embedder.embed)
    monkeypatch.setattr(vectors.embedder, 'embed', embed)
    assert (await client.post(f"/api/repos/{repo['id']}/reingest")).status_code == 202
    assert await run_once()
    updated = (await client.get(f"/api/repos/{repo['id']}")).json()
    assert updated['status'] == 'ready' and embed.await_count > 0
    assert await vectors.count(repo['id']) == repo['stats']['chunks']


async def test_paced_indexing_leaves_worker_available_for_the_next_repository(logged_in, monkeypatch):
    client, graph, vectors, _ = logged_in
    original = vectors.embedder.embed
    calls = 0

    async def pace_after_first_batch(texts, query=False):
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise EmbeddingDeferred(45, 'pacing')
        return await original(texts, query=query)

    monkeypatch.setattr(vectors.embedder, 'embed', pace_after_first_batch)
    first = await upload(client, source_zip({f'module_{i}.py': f'VALUE = {i}\n' for i in range(20)}))
    second = await upload(client, name='second')
    assert await run_once()
    assert (await client.get(f"/api/repos/{first['id']}")).json()['stats']['chunks'] == 8
    assert await run_once()
    for repo in (first, second):
        current = (await client.get(f"/api/repos/{repo['id']}")).json()
        assert current['status'] == 'waiting_embeddings'
        assert current['stats']['nodes'] > 0 and await graph.count_nodes(repo['id']) > 0
        assert (await client.get(f"/api/repos/{repo['id']}/files")).status_code == 200
    async with db.get_engine().connect() as conn:
        jobs = (await conn.execute(select(db.jobs))).mappings().all()
    assert all(job['status'] == 'retry' and job['attempts'] == 0 for job in jobs)
    assert all(job['details']['pause_reason'] == 'pacing' for job in jobs)
