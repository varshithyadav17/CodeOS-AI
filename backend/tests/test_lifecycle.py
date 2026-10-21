import asyncio
import io
import tempfile
import zipfile
from pathlib import Path
import pytest
from sqlalchemy import select, update
from app import database as db
from app.jobs import run_once
from app.models import Conversation, Memory, Message, Review


def source_zip(files=None):
    files = files or {"auth.py": "def authenticate(token):\n    return token == 'allowed'\n",
        "api.py": "from auth import authenticate\n\ndef login(token):\n    return authenticate(token)\n", "README.md": "# Example API\nAuthentication example.\n"}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return stream.getvalue()


async def upload(client, data=None, name="example"):
    response = await client.post("/api/repos/upload", files={"file": ("example.zip", data if data is not None else source_zip(), "application/zip")}, data={"name": name})
    assert response.status_code == 202, response.text
    return response.json()


async def ready_repo(client):
    repo = await upload(client)
    assert await run_once()
    response = await client.get(f"/api/repos/{repo['id']}")
    assert response.json()["status"] == "ready", response.text
    return response.json()


async def due_jobs():
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.jobs).values(next_run_at=0))


@pytest.mark.asyncio
async def test_upload_ingest_file_graph_chat_and_reingest(logged_in):
    client, graph, vectors, storage = logged_in
    repo = await ready_repo(client)
    repo_id = repo["id"]
    assert repo["stats"]["files"] == 3
    assert repo["stats"]["chunks"] > 0
    assert len(storage.objects) == 1
    assert "local_path" not in repo
    assert "file_manifest" not in repo
    file_list = (await client.get(f"/api/repos/{repo_id}/files")).json()
    assert {f["path"] for f in file_list} == {"auth.py", "api.py", "README.md"}
    assert "archive_path" not in file_list[0]
    content = await client.get(f"/api/repos/{repo_id}/files/content", params={"path": "auth.py"})
    assert "def authenticate" in content.json()["content"]
    data = (await client.get(f"/api/repos/{repo_id}/graph")).json()
    assert any(e["type"] == "CALLS" for e in data["edges"])
    assert any(e["type"] == "IMPORTS" for e in data["edges"])
    answer = await client.post(f"/api/repos/{repo_id}/chat", json={"message": "Where is authentication and what calls authenticate?"})
    assert answer.status_code == 200, answer.text
    assert answer.json()["sources"]
    assert any(r["type"] == "CALLS" for r in answer.json()["relationships"])
    conv = await client.get("/api/conversations/" + answer.json()["conversation_id"])
    assert len(conv.json()["messages"]) == 2
    assert conv.json()["messages"][1]["sources"] == answer.json()["sources"]
    before_ids = set(graph.nodes)
    assert (await client.post(f"/api/repos/{repo_id}/reingest")).status_code == 202
    assert await run_once()
    after = (await client.get(f"/api/repos/{repo_id}")).json()
    assert after["status"] == "ready"
    assert after["stats"] == repo["stats"]
    assert set(graph.nodes) == before_ids
    assert await vectors.count(repo_id) == repo["stats"]["chunks"]
    assert len(storage.objects) == 1
    assert (await client.get("/api/stats")).json()["llm_calls"] == 1


async def test_duplicate_jobs_and_cancel_queued_ingestion(logged_in):
    client, graph, vectors, storage = logged_in
    repo = await upload(client)
    id_ = repo["id"]
    assert (await client.post(f"/api/repos/{id_}/reingest")).status_code == 409
    assert (await client.post(f"/api/repos/{id_}/chat", json={"message": "hello"})).status_code == 409
    deletion = await client.delete(f"/api/repos/{id_}")
    assert deletion.status_code == 202
    same = await client.delete(f"/api/repos/{id_}")
    assert same.json()["job_id"] == deletion.json()["job_id"]
    assert await run_once()
    assert (await client.get(f"/api/repos/{id_}")).status_code == 404
    assert not storage.objects
    assert not graph.nodes


async def test_deletion_cascades_all_records_and_is_repository_scoped(logged_in):
    client, graph, vectors, storage = logged_in
    one, two = await ready_repo(client), await ready_repo(client)
    user = (await client.get("/api/auth/me")).json()["user"]
    conv = Conversation(repo_id=one["id"], user_id=user["id"])
    await db.get_conversation_repo().insert(conv)
    await db.get_message_repo().insert(Message(conversation_id=conv.id, role="assistant", content="test"))
    review = Review(repo_id=one["id"], user_id=user["id"])
    await db.get_review_repo().insert(review)
    await db.get_memory_repo().insert(Memory(repo_id=one["id"], user_id=user["id"], category="note", title="note", review_id=review.id))
    await db.get_docs_repo().insert(dict(id="1", repo_id=one["id"], user_id=user["id"], doc_type="readme", content="test", created_at=db.now(), updated_at=db.now()))
    await client.delete(f"/api/repos/{one['id']}")
    assert await run_once()
    assert not await db.get_repo_repo().get(one["id"])
    for table in (db.jobs, db.memories, db.documentation, db.reviews, db.activities, db.conversations):
        async with db.get_engine().connect() as conn:
            assert not (await conn.execute(select(table).where(table.c.repo_id == one["id"]))).all()
    assert not await db.get_message_repo().get(conv.id)
    assert not await db.get_message_repo().count({"conversation_id": conv.id})
    assert await vectors.count(one["id"]) == 0
    assert await vectors.count(two["id"]) == two["stats"]["chunks"]
    assert len(storage.objects) == 1
    assert await graph.count_nodes(two["id"]) == two["stats"]["nodes"]


async def test_partial_delete_failure_resumes_and_preserves_status(logged_in):
    client, graph, vectors, storage = logged_in
    repo = await ready_repo(client)
    storage.fail_delete = True
    await client.delete(f"/api/repos/{repo['id']}")
    assert await run_once()
    current = await db.get_repo_repo().get(repo["id"])
    assert current.status == "deleting"
    assert not await graph.count_nodes(repo["id"])
    assert not await vectors.count(repo["id"])
    assert storage.objects
    jobs = (await client.get(f"/api/repos/{repo['id']}/jobs")).json()
    active = next(j for j in jobs if j["kind"] == "delete")
    assert active["details"]["graph"] and active["details"]["vectors"]
    assert not active["details"].get("archive")
    storage.fail_delete = False
    await due_jobs()
    assert await run_once()
    assert not await db.get_repo_repo().get(repo["id"])
    assert not storage.objects


async def test_delete_failed_can_be_retried(logged_in, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "JOB_MAX_ATTEMPTS", 1)
    client, graph, vectors, storage = logged_in
    repo = await ready_repo(client)
    graph.fail_delete = True
    await client.delete(f"/api/repos/{repo['id']}")
    await run_once()
    assert (await db.get_repo_repo().get(repo["id"])).status == "delete_failed"
    assert (await client.post(f"/api/repos/{repo['id']}/reingest")).status_code == 409
    graph.fail_delete = False
    assert (await client.delete(f"/api/repos/{repo['id']}")).status_code == 202
    await run_once()
    assert not await db.get_repo_repo().get(repo["id"])


async def test_failed_checksum_and_safe_retry(logged_in):
    client, graph, vectors, storage = logged_in
    repo = await upload(client)
    key = repo["archive_key"]
    original = storage.objects[key]
    storage.objects[key] = b"corrupt"
    await run_once()
    assert (await db.get_repo_repo().get(repo["id"])).status == "failed"
    assert not graph.nodes
    storage.objects[key] = original
    assert (await client.post(f"/api/repos/{repo['id']}/reingest")).status_code == 202
    await run_once()
    assert (await db.get_repo_repo().get(repo["id"])).status == "ready"


async def test_worker_reclaims_expired_job(logged_in):
    client, _, _, _ = logged_in
    repo = await upload(client)
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.jobs).where(db.jobs.c.repo_id == repo["id"]).values(status="running", lease_until=0, lease_token="dead-worker"))
    assert await run_once()
    assert (await db.get_repo_repo().get(repo["id"])).status == "ready"


async def test_deletion_during_ingestion_and_workspace_cleanup(logged_in, monkeypatch):
    client, graph, vectors, storage = logged_in
    repo = await upload(client)
    entered, release = asyncio.Event(), asyncio.Event()
    original = vectors.upsert
    async def pause(chunks):
        entered.set()
        await release.wait()
        return await original(chunks)
    monkeypatch.setattr(vectors, "upsert", pause)
    running = asyncio.create_task(run_once())
    await asyncio.wait_for(entered.wait(), 10)
    assert (await client.delete(f"/api/repos/{repo['id']}")).status_code == 202
    release.set()
    await running
    assert await run_once()
    assert not await db.get_repo_repo().get(repo["id"])
    assert not storage.objects and not graph.nodes
    assert not list(Path(tempfile.gettempdir()).glob("codeos-ingest-*"))


async def test_graceful_worker_shutdown_returns_job_to_queue(logged_in, monkeypatch):
    client, _, vectors, _ = logged_in
    repo = await upload(client)
    entered = asyncio.Event()
    original = vectors.upsert
    async def pause(chunks):
        entered.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(vectors, "upsert", pause)
    running = asyncio.create_task(run_once())
    await asyncio.wait_for(entered.wait(), 10)
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running
    jobs = (await client.get(f"/api/repos/{repo['id']}/jobs")).json()
    assert jobs[0]["status"] == "retry" and jobs[0]["attempts"] == 0
    assert not list(Path(tempfile.gettempdir()).glob("codeos-ingest-*"))
    monkeypatch.setattr(vectors, "upsert", original)
    await run_once()
    assert (await db.get_repo_repo().get(repo["id"])).status == "ready"


async def test_git_import_uses_same_archive_pipeline_and_reingest_snapshot(logged_in, monkeypatch):
    import app.repository.service as service
    from app.memory.service import TimelineService
    client, graph, _, storage = logged_in
    calls = []
    async def clone(url, dest, branch, job):
        calls.append(url)
        dest.mkdir()
        (dest / "auth.py").write_text("def authenticate():\n    return True\n")
        return "a"*40
    monkeypatch.setattr(service, "clone_github", clone)
    monkeypatch.setattr(TimelineService, "snapshot", lambda self: {"available": True, "shallow": True, "commits": []})
    response = await client.post("/api/repos/github", json={"url": "https://github.com/example/project", "branch": "main"})
    assert response.status_code == 202, response.text
    repo_id = response.json()["id"]
    await run_once()
    repo = await db.get_repo_repo().get(repo_id)
    assert repo.status == "ready" and repo.source_commit == "a"*40
    assert len(storage.objects) == 1
    await client.post(f"/api/repos/{repo_id}/reingest")
    await run_once()
    assert len(calls) == 1
    assert (await client.get(f"/api/repos/{repo_id}/files/content", params={"path": "auth.py"})).status_code == 200


async def test_final_ingestion_failure_cleans_partial_indexes(logged_in,monkeypatch):
    from app.config import settings
    client,graph,vectors,storage=logged_in
    monkeypatch.setattr(settings,'JOB_MAX_ATTEMPTS',1)
    repo=await upload(client)
    async def fail(chunks):
        raise ConnectionError('embedding provider unavailable')
    monkeypatch.setattr(vectors,'upsert',fail)
    await run_once()
    assert (await db.get_repo_repo().get(repo['id'])).status=='failed'
    assert not await graph.count_nodes(repo['id'])
    assert not await vectors.count(repo['id'])
    assert len(storage.objects)==1


async def test_failed_ingestion_cleanup_is_durable_and_retryable(logged_in,monkeypatch):
    from app.config import settings
    client,graph,vectors,_=logged_in
    monkeypatch.setattr(settings,'JOB_MAX_ATTEMPTS',1)
    repo=await upload(client)
    async def fail(chunks):
        graph.fail_delete=True
        raise ConnectionError('embedding failure followed by graph outage')
    monkeypatch.setattr(vectors,'upsert',fail)
    await run_once()
    assert await graph.count_nodes(repo['id'])>0
    history=(await client.get(f'/api/repos/{repo["id"]}/jobs')).json()
    assert any(j['kind']=='cleanup' and j['status']=='queued' for j in history)
    graph.fail_delete=False
    await run_once()
    assert not await graph.count_nodes(repo['id'])
    assert (await db.get_repo_repo().get(repo['id'])).status=='failed'
