"""Drop-in replacement for the previous `LlmChat`/`UserMessage` chat wrapper.

Backed by the official Google Gemini SDK (`google-genai`). Keeps the same
async interface used throughout the codebase:

    chat = LlmChat(api_key=KEY, session_id="...", system_message="...")
          .with_model("gemini", "gemini-2.5-pro")
    raw = await chat.send_message(UserMessage(text="hello"))
    # raw is a string

Only the Gemini provider is implemented (it is the only one the codebase
uses); calling `.with_model()` with a non-gemini provider raises.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover - hard dep
    genai = None
    genai_types = None

logger = logging.getLogger(__name__)

# Reused across every LlmChat/send_message call (chat turns, all six review
# agents, docs generation, etc). Constructing genai.Client() allocates an
# HTTP client/session, so building a fresh one per call — as this module
# used to — was wasteful and unbounded. Keyed by api_key so a change in key
# still works correctly (relevant mainly for tests).
_client_cache: dict[str, Any] = {}


def _get_client(api_key: str) -> Any:
    client = _client_cache.get(api_key)
    if client is None:
        client = genai.Client(api_key=api_key)
        _client_cache[api_key] = client
    return client


@dataclass
class UserMessage:
    """Simple user-message container, API-compatible with the old import."""

    text: str


class LlmChat:
    """Async chat wrapper around `google-genai`.

    Mirrors the constructor / builder / `send_message` API of the previous
    `LlmChat` class so the rest of the application does not need to change.
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        session_id: str = "",
        system_message: str = "",
    ) -> None:
        # Resolve the API key: explicit constructor arg takes precedence,
        # otherwise fall back to the `GEMINI_API_KEY` env var.
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.session_id = session_id
        self.system_message = system_message
        self._provider = "gemini"
        self._model = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")

    # Builder API (kept for source compatibility) ------------------------------

    def with_model(self, provider: str, model: str) -> "LlmChat":
        if provider != "gemini":
            raise ValueError(
                f"Unsupported LLM provider '{provider}'. This standalone build "
                "only ships the Gemini provider via google-genai."
            )
        self._provider = provider
        self._model = model
        return self

    # Sending ------------------------------------------------------------------

    async def send_message(self, message: UserMessage | str) -> str:
        text = message.text if isinstance(message, UserMessage) else str(message)

        if not self.api_key:
            raise RuntimeError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in "
                "backend/.env (obtain one at https://aistudio.google.com/apikey)."
            )
        if genai is None or genai_types is None:
            raise RuntimeError(
                "google-genai is not installed. Run "
                "`pip install -r backend/requirements.txt`."
            )

        client = _get_client(self.api_key)
        config: Any = None
        if self.system_message:
            config = genai_types.GenerateContentConfig(
                system_instruction=self.system_message
            )

        response = await client.aio.models.generate_content(
            model=self._model,
            contents=text,
            config=config,
        )

        # `response.text` is a convenience accessor on the SDK response.
        return getattr(response, "text", "") or ""
