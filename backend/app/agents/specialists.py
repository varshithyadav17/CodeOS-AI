"""The six specialised agents — each is a thin shell over `run_agent_with_llm`."""
from __future__ import annotations
from .base import BaseAgent, ReviewContext
from .llm_runner import run_agent_with_llm
from ..core.models.review import AgentReport


class ArchitectAgent(BaseAgent):
    name = "architect"
    title = "Architect"
    SYSTEM = """You are a Staff Software Architect reviewing a repository.
Focus on: SOLID violations, design smells (god class, feature envy, shotgun surgery),
layering violations, circular dependencies, missing abstractions, and architectural
improvements. Use file paths and class/function names from the provided context.
Be specific. Prefer 3-7 high-signal findings over many low-signal ones."""

    async def run(self, ctx: ReviewContext) -> AgentReport:
        return await run_agent_with_llm(self.name, self.SYSTEM, ctx, max_chunks=10)


class SecurityAgent(BaseAgent):
    name = "security"
    title = "Security"
    SYSTEM = """You are a senior application-security engineer following OWASP Top 10.
Focus on: hardcoded secrets/keys, weak auth/authorization checks, injection (SQL/NoSQL/Command/SSRF),
insecure deserialization, sensitive data exposure, missing input validation, vulnerable patterns
in dependency usage, and unsafe defaults. Cite exact file paths and lines when possible."""

    async def run(self, ctx: ReviewContext) -> AgentReport:
        return await run_agent_with_llm(self.name, self.SYSTEM, ctx, max_chunks=12)


class PerformanceAgent(BaseAgent):
    name = "performance"
    title = "Performance"
    SYSTEM = """You are a performance engineer reviewing for bottlenecks.
Focus on: O(n^2)+ loops, N+1 queries, blocking I/O on async paths, redundant work,
expensive computations in hot paths, unbounded memory growth, missing caching,
and duplicate logic. Recommend concrete optimisations."""

    async def run(self, ctx: ReviewContext) -> AgentReport:
        return await run_agent_with_llm(self.name, self.SYSTEM, ctx, max_chunks=10)


class TestingAgent(BaseAgent):
    name = "testing"
    title = "Testing"
    SYSTEM = """You are a senior QA engineer.
Focus on: modules with no tests, missing edge-case coverage, untested error paths,
recommend specific unit and integration tests for the highest-risk modules.
Identify files that absolutely need tests first."""

    async def run(self, ctx: ReviewContext) -> AgentReport:
        return await run_agent_with_llm(self.name, self.SYSTEM, ctx, max_chunks=8)


class DocumentationAgent(BaseAgent):
    name = "documentation"
    title = "Documentation"
    SYSTEM = """You are a developer-experience engineer reviewing documentation quality.
Focus on: missing/weak docstrings on public APIs, undocumented modules, missing README sections
(install/usage/architecture), unclear function/class names. Suggest concrete docstrings to add."""

    async def run(self, ctx: ReviewContext) -> AgentReport:
        return await run_agent_with_llm(self.name, self.SYSTEM, ctx, max_chunks=8)


class RefactoringAgent(BaseAgent):
    name = "refactoring"
    title = "Refactoring"
    SYSTEM = """You are a refactoring expert.
Focus on: duplicated code, long methods (>40 lines)/classes (>300 lines), high coupling
between modules, low cohesion, primitive obsession, deeply nested conditionals.
Recommend Extract Method / Extract Class / Move Method actions with concrete targets."""

    async def run(self, ctx: ReviewContext) -> AgentReport:
        return await run_agent_with_llm(self.name, self.SYSTEM, ctx, max_chunks=10)


REVIEW_AGENTS: list[BaseAgent] = [
    ArchitectAgent(),
    SecurityAgent(),
    PerformanceAgent(),
    TestingAgent(),
    DocumentationAgent(),
    RefactoringAgent(),
]
