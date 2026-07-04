"""Hybrid Retrieval — combines vector top-K with 1-hop graph expansion."""
from __future__ import annotations
from ..core.interfaces.graph import IGraphService
from ..core.interfaces.vector import IVectorStore
from ..core.models.code import CodeChunk
from ..core.models.kg import KGNode


class RetrievalService:
    def __init__(self, graph: IGraphService, vectors: IVectorStore):
        self.graph = graph
        self.vectors = vectors

    async def hybrid(self, repo_id: str, question: str, k: int = 6) -> tuple[list[CodeChunk], list[KGNode]]:
        chunks = await self.vectors.query(repo_id, question, k=k)
        # Graph expansion
        seen_nodes: dict[str, KGNode] = {}
        for ch in chunks:
            if not ch.node_id:
                continue
            data = await self.graph.neighbors(repo_id, ch.node_id, depth=1)
            for n in data["nodes"]:
                seen_nodes[n.id] = n
        return chunks, list(seen_nodes.values())[:20]

    def format_context(self, chunks: list[CodeChunk], nodes: list[KGNode]) -> str:
        parts: list[str] = []
        if nodes:
            parts.append("### Related Symbols\n" + "\n".join(
                f"- [{n.type}] {n.qualified_name} ({n.file_path}:{n.start_line})" for n in nodes[:15]
            ))
        if chunks:
            parts.append("### Code Snippets")
            for c in chunks:
                snippet = c.text[:1500]
                parts.append(f"\n--- {c.file_path}:{c.start_line}-{c.end_line} ({c.language}) ---\n{snippet}")
        return "\n".join(parts)
