"""Base contract for code-review agents. Each agent is a pure async callable."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..core.models.review import AgentReport
from ..core.models.kg import KGNode, KGEdge
from ..core.models.code import CodeChunk


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


class BaseAgent(ABC):
    name: str = "base"
    title: str = "Base Agent"

    @abstractmethod
    async def run(self, ctx: ReviewContext) -> AgentReport:
        ...
