"""Review Manager — aggregates agent reports into an executive review."""
from __future__ import annotations
import json
import logging
from ..llm.chat_compat import LlmChat, UserMessage

from ..core.config import settings
from ..core.models.review import Review, AgentReport

logger = logging.getLogger(__name__)

SEVERITY_WEIGHT = {"critical": 25, "high": 15, "medium": 7, "low": 3, "info": 1}

SYSTEM = """You are a Principal Engineer authoring an executive code-review summary
combining six specialist reports (architect, security, performance, testing, documentation, refactoring).

Return ONLY JSON of this exact shape (no markdown):
{
  "executive_summary": "3-6 sentences in professional engineering tone",
  "action_plan": ["concrete bullet 1", "concrete bullet 2", ...]   // 5-8 prioritized items
}"""


def _compute_overall_score(agents: list[AgentReport]) -> int:
    done = [a for a in agents if a.status == "done"]
    if not done:
        return 0
    avg_agent = sum(a.score for a in done) / len(done)
    penalty = 0
    for a in done:
        for f in a.findings:
            penalty += SEVERITY_WEIGHT.get(f.severity, 3) * max(0.2, min(1.0, f.confidence))
    raw = avg_agent - (penalty / max(1, len(done)))
    return max(0, min(100, int(round(raw))))


async def finalize_review(review: Review) -> Review:
    overall = _compute_overall_score(review.agents)
    review.overall_score = overall

    # Compact findings for the manager LLM
    compact = []
    for a in review.agents:
        if a.status != "done":
            continue
        compact.append({
            "agent": a.agent,
            "summary": a.summary,
            "score": a.score,
            "top_findings": [
                {"severity": f.severity, "title": f.title, "category": f.category, "file": f.file_path}
                for f in sorted(a.findings, key=lambda x: SEVERITY_WEIGHT.get(x.severity, 0), reverse=True)[:6]
            ],
        })

    summary_text = ""
    action_plan: list[str] = []
    try:
        chat = LlmChat(
            api_key=settings.GEMINI_API_KEY,
            session_id=f"review-manager-{review.id}",
            system_message=SYSTEM,
        ).with_model("gemini", settings.LLM_MODEL)
        prompt = f"Overall computed score: {overall}/100\n\nSpecialist agent reports:\n{json.dumps(compact, indent=2)}"
        raw = await chat.send_message(UserMessage(text=prompt))
        text = raw if isinstance(raw, str) else getattr(raw, "content", str(raw))
        start = text.find("{"); end = text.rfind("}")
        if start != -1 and end != -1:
            parsed = json.loads(text[start:end + 1])
            summary_text = str(parsed.get("executive_summary", "")).strip()
            action_plan = [str(x).strip() for x in (parsed.get("action_plan") or []) if str(x).strip()][:10]
    except Exception as e:
        logger.exception("Manager aggregation failed")
        summary_text = (
            f"Multi-agent review completed across {len(review.agents)} specialists. "
            f"Overall health score: {overall}/100. See individual agent reports for findings."
        )
        action_plan = ["Review high-severity findings first", "Run the review again after fixes"]

    review.summary = summary_text or f"Overall health: {overall}/100. See individual agents."
    review.action_plan = action_plan
    return review
