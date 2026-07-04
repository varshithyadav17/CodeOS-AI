"""Shared LLM helper for review agents. Returns parsed JSON findings."""
from __future__ import annotations
import json
import logging
import re
import time
from ..llm.chat_compat import LlmChat, UserMessage

from ..core.config import settings
from ..core.models.review import AgentReport, Finding
from .base import ReviewContext

logger = logging.getLogger(__name__)

OUTPUT_SCHEMA = """Respond ONLY with a single JSON object (no markdown fences) of this shape:
{
  "summary": "1-3 sentences",
  "score": 0-100,
  "findings": [
    {
      "category": "snake_case_label",
      "title": "Short title",
      "description": "1-3 sentences explaining the issue",
      "severity": "critical|high|medium|low|info",
      "confidence": 0.0-1.0,
      "file_path": "optional path or null",
      "line": optional int or null,
      "recommendation": "concrete next step"
    }
  ]
}"""


def _build_context_text(ctx: ReviewContext, max_chunks: int = 10) -> str:
    parts: list[str] = []
    parts.append(f"# Repository: {ctx.repo_name}")
    parts.append(f"Languages: {ctx.language_breakdown}")
    parts.append(f"Files: {len(ctx.files)} | Classes: {len(ctx.classes)} | Functions: {len(ctx.functions)} | Edges: {len(ctx.edges)}")
    parts.append("\n## Sample files")
    parts.append("\n".join(f"- {f.file_path} ({f.metadata.get('loc', 0)} loc)" for f in ctx.files[:20]))
    if ctx.classes:
        parts.append("\n## Sample classes")
        parts.append("\n".join(f"- {c.qualified_name} ({c.file_path}:{c.start_line})" for c in ctx.classes[:15]))
    if ctx.functions:
        parts.append("\n## Sample functions")
        parts.append("\n".join(f"- {fn.qualified_name} ({fn.file_path}:{fn.start_line})" for fn in ctx.functions[:20]))
    parts.append("\n## Code samples")
    for c in ctx.sample_chunks[:max_chunks]:
        parts.append(f"\n--- {c.file_path}:{c.start_line}-{c.end_line} ({c.language}) ---\n{c.text[:1200]}")
    return "\n".join(parts)


def _extract_json(text: str) -> dict | None:
    # First try direct parse
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # Find the first balanced JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return None
    return None


async def run_agent_with_llm(agent_name: str, system_prompt: str, ctx: ReviewContext, max_chunks: int = 10) -> AgentReport:
    started = time.time()
    rep = AgentReport(agent=agent_name, status="running")
    try:
        ctx_text = _build_context_text(ctx, max_chunks=max_chunks)
        chat = LlmChat(
            api_key=settings.GEMINI_API_KEY,
            session_id=f"review-{ctx.repo_id}-{agent_name}",
            system_message=system_prompt + "\n\n" + OUTPUT_SCHEMA,
        ).with_model("gemini", settings.LLM_MODEL)
        prompt = f"Review the following repository snapshot and return findings as required JSON.\n\n{ctx_text}"
        raw = await chat.send_message(UserMessage(text=prompt))
        text = raw if isinstance(raw, str) else getattr(raw, "content", str(raw))
        parsed = _extract_json(text) or {}
        findings_raw = parsed.get("findings") or []
        findings: list[Finding] = []
        for f in findings_raw[:25]:
            try:
                findings.append(Finding(
                    agent=agent_name,
                    category=str(f.get("category", "general"))[:64],
                    title=str(f.get("title", "Finding"))[:200],
                    description=str(f.get("description", "")).strip()[:2000],
                    severity=(f.get("severity") or "medium").lower(),
                    confidence=float(f.get("confidence") or 0.6),
                    file_path=(f.get("file_path") or None),
                    line=(int(f["line"]) if f.get("line") not in (None, "", "null") else None),
                    recommendation=(f.get("recommendation") or None),
                ))
            except Exception:
                continue
        rep.findings = findings
        rep.summary = str(parsed.get("summary", "")).strip()[:1000]
        rep.score = int(parsed.get("score") or 70)
        rep.status = "done"
    except Exception as e:
        logger.exception("Agent %s failed", agent_name)
        rep.status = "failed"
        rep.error = str(e)
    rep.duration_ms = int((time.time() - started) * 1000)
    return rep
