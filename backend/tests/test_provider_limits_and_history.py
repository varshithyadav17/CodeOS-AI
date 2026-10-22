from types import SimpleNamespace

import git
import pytest
from google.genai.errors import ClientError

from app.ai.chat import LlmChat, UserMessage
from app.memory.service import TimelineService


async def test_generation_waits_for_provider_quota_reset(monkeypatch):
    from app.ai import chat

    calls, waits = [], []

    async def generate(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED", "details": [
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "17s"}
            ]}})
        return SimpleNamespace(text="Recovered answer")

    async def sleep(delay):
        waits.append(delay)

    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    monkeypatch.setattr(chat, "_get_client", lambda key: client)
    monkeypatch.setattr(chat.asyncio, "sleep", sleep)
    assert await LlmChat().send_message(UserMessage("Explain the code")) == "Recovered answer"
    assert len(calls) == 2 and len(waits) == 1
    assert 17 <= waits[0] <= 60


async def test_daily_quota_is_not_retried_as_a_short_rate_limit(monkeypatch):
    from app.ai import chat

    calls = []

    async def generate(**kwargs):
        calls.append(kwargs)
        raise ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED", "details": [
            {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
                {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}
            ]}
        ]}})

    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    monkeypatch.setattr(chat, "_get_client", lambda key: client)
    with pytest.raises(ClientError):
        await LlmChat().send_message(UserMessage("Explain the code"))
    assert len(calls) == 1


def test_shallow_history_keeps_commit_and_file_identity_without_parent_stats(tmp_path):
    source = git.Repo.init(tmp_path / "source")
    path = tmp_path / "source" / "auth.py"
    path.write_text("def authenticate(): return False\n")
    source.index.add(["auth.py"])
    actor = git.Actor("History test", "history@example.com")
    source.index.commit("Initial", author=actor, committer=actor)
    path.write_text("def authenticate(): return True\n")
    source.index.add(["auth.py"])
    latest = source.index.commit("", author=actor, committer=actor)
    clone = git.Repo.clone_from((tmp_path / "source").as_uri(), tmp_path / "shallow", depth=1)
    assert (tmp_path / "shallow" / ".git" / "shallow").exists()

    snapshot = TimelineService(str(clone.working_tree_dir)).snapshot()
    assert snapshot["available"] and snapshot["shallow"]
    assert [c["full_sha"] for c in snapshot["commits"]] == [latest.hexsha]
    assert snapshot["commits"][0]["message"] == "(no commit message)"
    assert snapshot["commits"][0]["stats_available"] is False
    assert snapshot["files"]["auth.py"][0]["stats_available"] is False
    assert snapshot["contributors"][0]["commits"] == 1
    assert snapshot["contributors"][0]["last"]
    assert snapshot["complexity"][0]["stats_available"] is False

    complete = TimelineService(str(source.working_tree_dir)).snapshot()
    assert complete["shallow"] is False
    assert len(complete["commits"]) == 2
    assert all(c["stats_available"] for c in complete["commits"])
