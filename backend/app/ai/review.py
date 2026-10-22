"""Multi-agent code review: agents, runner, manager, and ReviewService."""
from __future__ import annotations
import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from ..config import settings
from ..database import IMetadataRepository, IGraphService, IVectorStore
from ..models import Review, AgentReport, Finding, Repository, KGNode, KGEdge, CodeChunk
from ..prompts import (
    REVIEW_OUTPUT_SCHEMA,
    ARCHITECT_PROMPT, SECURITY_PROMPT, PERFORMANCE_PROMPT,
    TESTING_PROMPT, DOCUMENTATION_PROMPT, REFACTORING_PROMPT,
    REVIEW_MANAGER_SYSTEM,
)
from ..utils import extract_json
from .chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

SEVERITY_WEIGHT = {"critical": 25, "high": 15, "medium": 7, "low": 3, "info": 1}

# ---------------------------------------------------------------------------
# Review context
# ---------------------------------------------------------------------------

@dataclass
class ReviewContext:
    """Snapshot passed to every agent — pre-computed once by ReviewService."""
    repo_id: str
    repo_name: str
    files: list[KGNode]
    classes: list[KGNode]
    functions: list[KGNode]
    edges: list[KGEdge]
    sample_chunks: list[CodeChunk]
    language_breakdown: dict[str, int]


# ---------------------------------------------------------------------------
# Base agent
# ---------------------------------------------------------------------------

class BaseAgent(ABC):
    name: str = "base"
    title: str = "Base Agent"
    SYSTEM: str = ""

    @abstractmethod
    async def run(self, ctx: ReviewContext) -> AgentReport: ...


# ---------------------------------------------------------------------------
# Shared LLM runner
# ---------------------------------------------------------------------------

def _build_context_text(ctx: ReviewContext, max_chunks: int = 10) -> str:
    parts: list[str] = [
        f"# Repository: {ctx.repo_name}",
        f"Languages: {ctx.language_breakdown}",
        f"Files: {len(ctx.files)} | Classes: {len(ctx.classes)} | Functions: {len(ctx.functions)} | Edges: {len(ctx.edges)}",
        "\n## Sample files",
        "\n".join(f"- {f.file_path} ({f.metadata.get('loc', 0)} loc)" for f in ctx.files[:20]),
    ]
    if ctx.classes:
        parts += ["\n## Sample classes",
                  "\n".join(f"- {c.qualified_name} ({c.file_path}:{c.start_line})" for c in ctx.classes[:15])]
    if ctx.functions:
        parts += ["\n## Sample functions",
                  "\n".join(f"- {fn.qualified_name} ({fn.file_path}:{fn.start_line})" for fn in ctx.functions[:20])]
    parts.append("\n## Code samples")
    for c in ctx.sample_chunks[:max_chunks]:
        parts.append(f"\n--- {c.file_path}:{c.start_line}-{c.end_line} ({c.language}) ---\n{c.text[:1200]}")
    return "\n".join(parts)


async def run_agent_with_llm(agent_name: str, system_prompt: str, ctx: ReviewContext, max_chunks: int = 10) -> AgentReport:
    started = time.time()
    rep = AgentReport(agent=agent_name, status="running")
    try:
        ctx_text = _build_context_text(ctx, max_chunks=max_chunks)
        chat = LlmChat(
            api_key=settings.GEMINI_API_KEY,
            session_id=f"review-{ctx.repo_id}-{agent_name}",
            system_message=system_prompt + "\n\n" + REVIEW_OUTPUT_SCHEMA,
        ).with_model("gemini", settings.LLM_MODEL)
        prompt = f"Review the following repository snapshot and return findings as required JSON.\n\n{ctx_text}"
        raw = await chat.send_message(UserMessage(text=prompt))
        text = raw if isinstance(raw, str) else getattr(raw, "content", str(raw))
        parsed = extract_json(text)
        if not isinstance(parsed, dict) or "findings" not in parsed:
            raise ValueError("AI review response did not match the expected schema.")
        findings_raw = parsed["findings"]
        if not isinstance(findings_raw, list) or len(findings_raw) > 25:
            raise ValueError("AI findings must be a bounded list.")
        findings: list[Finding] = []
        known_files = {node.file_path for node in ctx.files + ctx.classes + ctx.functions}
        known_files.update(chunk.file_path for chunk in ctx.sample_chunks)
        for f in findings_raw:
            if not isinstance(f, dict):
                raise ValueError("AI finding is not an object.")
            finding = Finding.model_validate({**f, "agent": agent_name, "category": f.get("category", "general")})
            if finding.file_path and finding.file_path not in known_files:
                raise ValueError("AI finding references a file outside its repository evidence.")
            findings.append(finding)
        rep.findings = findings
        rep.summary = str(parsed.get("summary", "")).strip()[:1000]
        score = parsed.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100:
            raise ValueError("AI review score must be between 0 and 100.")
        rep.score = int(score)
        rep.status = "done"
    except Exception:
        logger.exception("Agent %s failed", agent_name)
        rep.status = "failed"
        rep.error = "AI review failed. Check provider configuration and quota."
    rep.duration_ms = int((time.time() - started) * 1000)
    return rep


# ---------------------------------------------------------------------------
# Specialist agents
# ---------------------------------------------------------------------------

class ArchitectAgent(BaseAgent):
    name = "architect"; title = "Architect"; SYSTEM = ARCHITECT_PROMPT
    async def run(self, ctx: ReviewContext) -> AgentReport:
        return await run_agent_with_llm(self.name, self.SYSTEM, ctx, max_chunks=10)


class SecurityAgent(BaseAgent):
    name = "security"; title = "Security"; SYSTEM = SECURITY_PROMPT
    async def run(self, ctx: ReviewContext) -> AgentReport:
        return await run_agent_with_llm(self.name, self.SYSTEM, ctx, max_chunks=12)


class PerformanceAgent(BaseAgent):
    name = "performance"; title = "Performance"; SYSTEM = PERFORMANCE_PROMPT
    async def run(self, ctx: ReviewContext) -> AgentReport:
        return await run_agent_with_llm(self.name, self.SYSTEM, ctx, max_chunks=10)


class TestingAgent(BaseAgent):
    name = "testing"; title = "Testing"; SYSTEM = TESTING_PROMPT
    async def run(self, ctx: ReviewContext) -> AgentReport:
        return await run_agent_with_llm(self.name, self.SYSTEM, ctx, max_chunks=8)


class DocumentationAgent(BaseAgent):
    name = "documentation"; title = "Documentation"; SYSTEM = DOCUMENTATION_PROMPT
    async def run(self, ctx: ReviewContext) -> AgentReport:
        return await run_agent_with_llm(self.name, self.SYSTEM, ctx, max_chunks=8)


class RefactoringAgent(BaseAgent):
    name = "refactoring"; title = "Refactoring"; SYSTEM = REFACTORING_PROMPT
    async def run(self, ctx: ReviewContext) -> AgentReport:
        return await run_agent_with_llm(self.name, self.SYSTEM, ctx, max_chunks=10)


REVIEW_AGENTS: list[BaseAgent] = [
    ArchitectAgent(), SecurityAgent(), PerformanceAgent(),
    TestingAgent(), DocumentationAgent(), RefactoringAgent(),
]


# ---------------------------------------------------------------------------
# Manager (executive fan-in)
# ---------------------------------------------------------------------------

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

    compact = []
    for a in review.agents:
        if a.status != "done":
            continue
        compact.append({
            "agent": a.agent, "summary": a.summary, "score": a.score,
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
            system_message=REVIEW_MANAGER_SYSTEM,
        ).with_model("gemini", settings.LLM_MODEL)
        prompt = f"Overall computed score: {overall}/100\n\nSpecialist agent reports:\n{json.dumps(compact, indent=2)}"
        raw = await chat.send_message(UserMessage(text=prompt))
        text = raw if isinstance(raw, str) else getattr(raw, "content", str(raw))
        start = text.find("{"); end = text.rfind("}")
        if start != -1 and end != -1:
            parsed = json.loads(text[start:end + 1])
            summary_text = str(parsed.get("executive_summary", "")).strip()
            action_plan = [str(x).strip() for x in (parsed.get("action_plan") or []) if str(x).strip()][:10]
    except Exception:
        logger.exception("Manager aggregation failed")
        summary_text = (
            f"Multi-agent review completed across {len(review.agents)} specialists. "
            f"Overall health score: {overall}/100. See individual agent reports for findings."
        )
        action_plan = ["Review high-severity findings first", "Run the review again after fixes"]

    review.summary = summary_text or f"Overall health: {overall}/100. See individual agents."
    review.action_plan = action_plan
    return review


# ---------------------------------------------------------------------------
# ReviewService
# ---------------------------------------------------------------------------

class ReviewService:
    def __init__(
        self,
        reviews: IMetadataRepository,
        repos: IMetadataRepository,
        graph: IGraphService,
        vectors: IVectorStore,
    ):
        self.reviews = reviews
        self.repos = repos
        self.graph = graph
        self.vectors = vectors

    async def create(self, repo_id: str, user_id: str) -> Review:
        review = Review(
            repo_id=repo_id, user_id=user_id, status="queued",
            agents=[AgentReport(agent=a.name, status="pending") for a in REVIEW_AGENTS],
        )
        await self.reviews.insert(review)
        return review

    async def _persist(self, review: Review) -> None:
        review.updated_at = datetime.now(timezone.utc).isoformat()
        await self.reviews.update(review.id, review.model_dump())

    async def _build_context(self, repo: Repository) -> ReviewContext:
        files = await self.graph.list_nodes(repo.id, type_="file", limit=400)
        classes = await self.graph.list_nodes(repo.id, type_="class", limit=200)
        functions = await self.graph.list_nodes(repo.id, type_="function", limit=300)
        methods = await self.graph.list_nodes(repo.id, type_="method", limit=200)
        edges = await self.graph.list_edges(repo.id, limit=800)
        sample = await self.vectors.query(
            repo.id, "architecture authentication database api entry point", k=12
        )
        return ReviewContext(
            repo_id=repo.id, repo_name=repo.name,
            files=files, classes=classes, functions=functions + methods,
            edges=edges, sample_chunks=sample,
            language_breakdown=repo.language_breakdown or {},
        )

    async def kickoff(self, review_id: str) -> None:
        """Background task — runs all agents in parallel, then the manager."""
        review = await self.reviews.get(review_id)
        if not review:
            return
        repo = await self.repos.get(review.repo_id)
        if not repo or repo.status != "ready":
            review.status = "failed"
            review.summary = "Repository is not ready for review."
            await self._persist(review)
            return

        review.status = "running"
        review.progress = 5
        await self._persist(review)

        ctx = await self._build_context(repo)
        n = len(REVIEW_AGENTS)
        done_count = 0

        persist_lock = asyncio.Lock()

        async def _run_one(agent, idx: int):
            nonlocal done_count
            async with persist_lock:
                review.agents[idx].status = "running"
                await self._persist(review)
            try:
                report = await agent.run(ctx)
            except Exception:
                report = AgentReport(agent=agent.name, status="failed", error="Review specialist failed. Please retry.")
            async with persist_lock:
                review.agents[idx] = report
                done_count += 1
                review.progress = 5 + int(85 * done_count / n)
                await self._persist(review)

        try:
            await asyncio.gather(*[_run_one(a, i) for i, a in enumerate(REVIEW_AGENTS)])
            review.progress = 92
            await self._persist(review)
            if not any(a.status == "done" for a in review.agents):
                raise RuntimeError("All review specialists failed. Check Gemini configuration.")
            await finalize_review(review)
            review.status = "done"
            review.progress = 100
            try:
                from ..database import get_memory_repo
                from ..memory.service import MemoryService
                await MemoryService(get_memory_repo()).import_from_review(review, review.user_id)
            except Exception:
                logger.exception("Memory import failed (non-fatal)")
        except Exception:
            logger.exception("Review pipeline failed")
            review.status = "failed"
            review.summary = "Review failed. Check service health and Gemini configuration, then retry."
        await self._persist(review)
