"""Opt-in public GitHub network test; all other providers use isolated fixtures."""
import os
import tempfile
from pathlib import Path
import pytest
from app import database as db
from app.jobs import run_once

pytestmark = pytest.mark.skipif(os.getenv("CODEOS_LIVE_GITHUB_TESTS") != "1", reason="Set CODEOS_LIVE_GITHUB_TESTS=1 for the public GitHub network test")


async def test_public_github_snapshot_reingest_and_delete(logged_in, monkeypatch):
    import app.repository.service as service
    client, graph, vectors, storage = logged_in
    before = set(Path(tempfile.gettempdir()).glob("codeos-ingest-*"))
    response = await client.post("/api/repos/github", json={"url": "https://github.com/octocat/Spoon-Knife"})
    assert response.status_code == 202, response.text
    rid = response.json()["id"]
    assert await run_once()
    repo = await db.get_repo_repo().get(rid)
    assert repo.status == "ready", repo.message
    assert len(repo.source_commit) == 40 and repo.archive_sha256
    assert repo.stats.files >= 3 and repo.stats.chunks > 0
    assert repo.timeline["available"] and repo.timeline["shallow"]
    assert len(storage.objects) == 1
    preview = await client.get(f"/api/repos/{rid}/files/content", params={"path": "README.md"})
    assert preview.status_code == 200 and "Spoon-Knife" in preview.json()["content"]
    assert set(Path(tempfile.gettempdir()).glob("codeos-ingest-*")) == before
    async def unexpected_clone(*args, **kwargs):
        raise AssertionError("Re-ingestion must use the saved snapshot")
    monkeypatch.setattr(service, "clone_github", unexpected_clone)
    assert (await client.post(f"/api/repos/{rid}/reingest")).status_code == 202
    assert await run_once()
    again = await db.get_repo_repo().get(rid)
    assert again.status == "ready" and again.stats == repo.stats and again.source_commit == repo.source_commit
    assert (await client.delete(f"/api/repos/{rid}")).status_code == 202
    assert await run_once()
    assert await db.get_repo_repo().get(rid) is None
    assert not storage.objects and await graph.count_nodes(rid) == 0 and await vectors.count(rid) == 0
