"""LLM integration package — standalone Google Gemini SDK wrapper.

This module replaces the previous third-party LLM SDK dependency with a
thin compatibility shim over the official `google-genai` SDK so the rest of
the codebase keeps using the same `LlmChat` / `UserMessage` surface area.
"""
from .chat_compat import LlmChat, UserMessage

__all__ = ["LlmChat", "UserMessage"]
