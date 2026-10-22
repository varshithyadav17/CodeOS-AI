import asyncio
from types import SimpleNamespace

import git
import pytest
from google.genai.errors import ClientError, ServerError

from app.ai.chat import LlmChat, UserMessage
from app.memory.service import TimelineService


@pytest.fixture
def paced_clock(monkeypatch):
    from app.ai import chat

    current, waits = [0.0], []
    pacer_type = chat._RequestPacer

    async def sleep(delay):
        waits.append(delay)
        current[0] += delay

    monkeypatch.setattr(chat, "_generation_pacers", {})
    monkeypatch.setattr(chat.settings, "LLM_REQUESTS_PER_MINUTE", 5)
    monkeypatch.setattr(chat, "_RequestPacer", lambda rpm: pacer_type(rpm, clock=lambda: current[0], sleep=sleep))
    return current, waits


@pytest.mark.parametrize("retry_seconds", [17, 60])
async def test_generation_waits_for_provider_quota_reset(monkeypatch, paced_clock, retry_seconds):
    from app.ai import chat
    _, waits = paced_clock

    calls = []

    async def generate(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED", "details": [
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": f"{retry_seconds}s"}
            ]}})
        return SimpleNamespace(text="Recovered answer")

    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    monkeypatch.setattr(chat, "_get_client", lambda key: client)
    assert await LlmChat().send_message(UserMessage("Explain the code")) == "Recovered answer"
    assert len(calls) == 2 and len(waits) == 1
    assert retry_seconds < waits[0] <= 120


async def test_daily_quota_is_not_retried_as_a_short_rate_limit(monkeypatch, paced_clock):
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


async def test_six_concurrent_specialists_share_budget_including_overload_retries(monkeypatch, paced_clock):
    from app.ai import chat
    current, _ = paced_clock
    starts = []

    async def generate(**kwargs):
        starts.append(current[0])
        if len(starts) <= 2:
            raise ServerError(503, {"error": {"status": "UNAVAILABLE", "message": "High demand"}})
        return SimpleNamespace(text="Specialist completed")

    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    monkeypatch.setattr(chat, "_get_client", lambda key: client)
    answers = await asyncio.gather(*[LlmChat().send_message(UserMessage("Review the code")) for _ in range(6)])
    assert answers == ["Specialist completed"] * 6
    assert len(starts) == 8
    assert all(sum(start <= other < start + 60 for other in starts) <= 5 for start in starts)


async def test_flash_lite_uses_supported_generation_parameters(monkeypatch, paced_clock):
    from app.ai import chat
    calls = []

    async def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text="Supported free model answer")

    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    monkeypatch.setattr(chat, "_get_client", lambda key: client)
    llm = LlmChat().with_model("gemini", "gemini-3.5-flash-lite")
    assert await llm.send_message(UserMessage("Explain the code")) == "Supported free model answer"
    assert calls[0]["model"] == "gemini-3.5-flash-lite"
    assert calls[0]["config"].temperature is None
    assert calls[0]["config"].thinking_config.thinking_level.upper() == "MEDIUM"


async def test_quota_cooldown_reaches_a_request_already_waiting():
    from app.ai.chat import _RequestPacer
    current = [0.0]
    sleeping, release = asyncio.Event(), asyncio.Event()

    async def sleep(delay):
        if not sleeping.is_set():
            sleeping.set()
            await release.wait()
        current[0] += delay

    pacer = _RequestPacer(5, clock=lambda: current[0], sleep=sleep)
    await pacer.wait()
    waiting = asyncio.create_task(pacer.wait())
    await sleeping.wait()
    pacer.defer(60)
    release.set()
    await waiting
    assert current[0] >= 60


async def test_interactive_cancellation_releases_the_request_queue():
    from app.ai.chat import _RequestPacer
    current = [0.0]
    pacer = _RequestPacer(5, clock=lambda: current[0])
    await pacer.wait()
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.01):
            await pacer.wait()
    assert not pacer.lock.locked()
    current[0] = 13
    await pacer.wait()


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
