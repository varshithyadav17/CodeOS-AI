"""Graph service interface — swap Mongo → Neo4j without changing services."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from ..models.kg import KGNode, KGEdge


class IGraphService(ABC):
    @abstractmethod
    async def upsert_nodes(self, nodes: list[KGNode]) -> int: ...

    @abstractmethod
    async def upsert_edges(self, edges: list[KGEdge]) -> int: ...

    @abstractmethod
    async def get_node(self, repo_id: str, node_id: str) -> KGNode | None: ...

    @abstractmethod
    async def list_nodes(self, repo_id: str, type_: str | None = None, limit: int = 500) -> list[KGNode]: ...

    @abstractmethod
    async def list_edges(self, repo_id: str, limit: int = 1000) -> list[KGEdge]: ...

    @abstractmethod
    async def neighbors(self, repo_id: str, node_id: str, depth: int = 1) -> dict[str, Any]: ...

    @abstractmethod
    async def delete_repo(self, repo_id: str) -> None: ...

    @abstractmethod
    async def find_node_by_qname(self, repo_id: str, qualified_name: str) -> KGNode | None: ...

    @abstractmethod
    async def count_nodes(self, repo_id: str | None = None) -> int: ...

    @abstractmethod
    async def count_edges(self, repo_id: str | None = None) -> int: ...
