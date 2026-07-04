"""Review Service — orchestrates the multi-agent DAG.

Today: asyncio.gather fan-out + manager fan-in. The graph is identical to what
LangGraph would produce (parallel nodes → aggregator). Swap to LangGraph by
replacing the body of `_run_agents_parallel` without changing callers.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from ..core.interfaces.metadata import IMetadataRepository
from ..core.interfaces.graph import IGraphService
from ..core.interfaces.vector import IVectorStore
from ..core.models.review import Review, AgentReport
from ..core.models.repository import Repository
from ..agents.base import ReviewContext
from ..agents.specialists import REVIEW_AGENTS
from ..agents.manager import finalize_review

logger = logging.getLogger(__name__)


class ReviewService:
    def __init__(
        self,
        reviews: IMetadataRepository[Review],
        repos: IMetadataRepository[Repository],
        graph: IGraphService,
        vectors: IVectorStore,
    ):
        self.reviews = reviews
        self.repos = repos
        self.graph = graph
        self.vectors = vectors

    async def create(self, repo_id: str, user_id: str) -> Review:
        review = Review(repo_id=repo_id, user_id=user_id, status="queued",
                        agents=[AgentReport(agent=a.name, status="pending") for a in REVIEW_AGENTS])
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
        # Use 'architecture overview' as a synthetic query to grab representative chunks
        sample = await self.vectors.query(repo.id, "architecture authentication database api entry point", k=12)
        return ReviewContext(
            repo_id=repo.id,
            repo_name=repo.name,
            files=files,
            classes=classes,
            functions=functions + methods,
            edges=edges,
            sample_chunks=sample,
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

        # Fan-out: all agents in parallel, with progressive persistence
        n = len(REVIEW_AGENTS)
        done_count = 0

        async def _run_one(agent, idx: int):
            nonlocal done_count
            # mark running
            review.agents[idx].status = "running"
            await self._persist(review)
            try:
                report = await agent.run(ctx)
            except Exception as e:
                report = AgentReport(agent=agent.name, status="failed", error=str(e))
            review.agents[idx] = report
            done_count += 1
            review.progress = 5 + int(85 * done_count / n)
            await self._persist(review)

        try:
            await asyncio.gather(*[_run_one(a, i) for i, a in enumerate(REVIEW_AGENTS)])
            # Fan-in: manager
            review.progress = 92
            await self._persist(review)
            await finalize_review(review)
            review.status = "done"
            review.progress = 100
            # Persist findings to Engineering Memory (idempotent)
            try:
                from ..api.routes.memory import _memo_repo
                from .memory_service import MemoryService
                await MemoryService(_memo_repo()).import_from_review(review, review.user_id)
            except Exception:
                logger.exception("Memory import failed (non-fatal)")
        except Exception as e:
            logger.exception("Review pipeline failed")
            review.status = "failed"
            review.summary = f"Review failed: {e}"
        await self._persist(review)
