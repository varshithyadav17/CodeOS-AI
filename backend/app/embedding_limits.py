"""Shared free-tier embedding budget and durable, non-destructive pauses."""
from __future__ import annotations
import asyncio
import math
import time
from collections import deque
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


class EmbeddingDeferred(Exception):
    def __init__(self, retry_after=65, reason="quota"):
        self.retry_after = max(1.0, float(retry_after))
        self.reason = reason
        messages = {
            "quota": "Google's embedding quota is temporarily full. Your files and graph are saved; AI indexing will resume automatically.",
            "daily_quota": "Google's daily embedding quota is exhausted. Your files and graph are saved; AI indexing will resume after the quota reset.",
            "unavailable": "The embedding provider is temporarily unavailable. Your files and graph are saved; AI indexing will retry automatically.",
            "continuation": "Your files and graph are ready. AI indexing is continuing from its saved progress.",
        }
        super().__init__(messages.get(reason, messages["unavailable"]))


def estimated_tokens(text):
    # A conservative local estimate; actual provider tokenization can differ.
    return max(1, math.ceil(len(text.encode("utf-8")) / 3))


def embedding_batches(items, text=lambda item: item, size=8, token_limit=4000):
    batch, tokens = [], 0
    for item in items:
        cost = estimated_tokens(text(item))
        if batch and (len(batch) >= size or tokens + cost > token_limit):
            yield batch
            batch, tokens = [], 0
        batch.append(item)
        tokens += cost
    if batch:
        yield batch


def next_daily_reset_seconds():
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
    return max(60, tomorrow.timestamp() - now.timestamp())


def embedding_retry_hint(exc):
    """Keep long RetryInfo delays; only explicit per-day violations mean daily quota."""
    payload = getattr(exc, "details", {})
    error = payload.get("error", payload) if isinstance(payload, dict) else {}
    details = error.get("details", []) if isinstance(error, dict) else []
    delay, reason = 65.0, "quota" if getattr(exc, "code", None) == 429 else "unavailable"
    daily = False
    for detail in details if isinstance(details, list) else []:
        if not isinstance(detail, dict):
            continue
        if str(detail.get("@type", "")).endswith("QuotaFailure"):
            daily |= any("perday" in str(v.get("quotaId", "")).lower()
                for v in detail.get("violations", []) if isinstance(v, dict))
        if str(detail.get("@type", "")).endswith("RetryInfo"):
            try:
                value = float(str(detail.get("retryDelay", "")).removesuffix("s"))
                if math.isfinite(value):
                    delay = max(delay, value + 1)
            except ValueError:
                pass
    if daily:
        return max(delay, next_daily_reset_seconds()), "daily_quota"
    return delay, reason


class EmbeddingBudget:
    """Pace requests, input count and estimated tokens across ingestion/query calls."""
    def __init__(self, rpm, inputs_per_minute, tokens_per_minute, *, clock=None, sleep=None):
        self.interval = 60.0 / rpm + 0.25
        self.inputs = inputs_per_minute
        self.tokens = tokens_per_minute
        self.clock, self.sleep = clock or time.monotonic, sleep or asyncio.sleep
        self.events = deque()
        self.next_request = self.cooldown = 0.0
        self.reason = "quota"
        self.lock = asyncio.Lock()

    def defer(self, seconds, reason):
        self.cooldown = max(self.cooldown, self.clock() + seconds)
        self.reason = reason

    async def wait(self, texts):
        cost = min(self.tokens, sum(estimated_tokens(text) for text in texts))
        async with self.lock:
            while True:
                now = self.clock()
                if self.cooldown > now:
                    raise EmbeddingDeferred(self.cooldown - now, self.reason)
                while self.events and self.events[0][0] <= now - 60.5:
                    self.events.popleft()
                delay = self.next_request - now
                if self.events and (sum(e[1] for e in self.events) + len(texts) > self.inputs
                                    or sum(e[2] for e in self.events) + cost > self.tokens):
                    delay = max(delay, self.events[0][0] + 60.5 - now)
                if delay <= 0:
                    break
                await self.sleep(delay)
            self.events.append((now, len(texts), cost))
            self.next_request = now + self.interval
