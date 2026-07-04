"""Mongo-backed graph service. Will be replaced by Neo4jGraphService later."""
from __future__ import annotations
from typing import Any
from ...core.interfaces.graph import IGraphService
from ...core.models.kg import KGNode, KGEdge
from . import db


class MongoGraphService(IGraphService):
    def __init__(self):
        self.nodes = db["kg_nodes"]
        self.edges = db["kg_edges"]

    async def upsert_nodes(self, nodes: list[KGNode]) -> int:
        if not nodes:
            return 0
        ops = []
        from pymongo import UpdateOne
        for n in nodes:
            ops.append(UpdateOne(
                {"repo_id": n.repo_id, "qualified_name": n.qualified_name, "type": n.type},
                {"$set": n.model_dump()},
                upsert=True,
            ))
        res = await self.nodes.bulk_write(ops, ordered=False)
        return (res.upserted_count or 0) + (res.modified_count or 0)

    async def upsert_edges(self, edges: list[KGEdge]) -> int:
        if not edges:
            return 0
        from pymongo import UpdateOne
        ops = []
        for e in edges:
            ops.append(UpdateOne(
                {"repo_id": e.repo_id, "source_id": e.source_id, "target_id": e.target_id, "type": e.type},
                {"$set": e.model_dump()},
                upsert=True,
            ))
        res = await self.edges.bulk_write(ops, ordered=False)
        return (res.upserted_count or 0) + (res.modified_count or 0)

    async def get_node(self, repo_id: str, node_id: str) -> KGNode | None:
        d = await self.nodes.find_one({"repo_id": repo_id, "id": node_id}, {"_id": 0})
        return KGNode(**d) if d else None

    async def list_nodes(self, repo_id: str, type_: str | None = None, limit: int = 500) -> list[KGNode]:
        q: dict[str, Any] = {"repo_id": repo_id}
        if type_:
            q["type"] = type_
        docs = await self.nodes.find(q, {"_id": 0}).limit(limit).to_list(length=limit)
        return [KGNode(**d) for d in docs]

    async def list_edges(self, repo_id: str, limit: int = 1000) -> list[KGEdge]:
        docs = await self.edges.find({"repo_id": repo_id}, {"_id": 0}).limit(limit).to_list(length=limit)
        return [KGEdge(**d) for d in docs]

    async def neighbors(self, repo_id: str, node_id: str, depth: int = 1) -> dict[str, Any]:
        frontier = {node_id}
        all_nodes: dict[str, KGNode] = {}
        all_edges: list[KGEdge] = []
        for _ in range(depth):
            if not frontier:
                break
            edges_out = await self.edges.find(
                {"repo_id": repo_id, "$or": [{"source_id": {"$in": list(frontier)}}, {"target_id": {"$in": list(frontier)}}]},
                {"_id": 0},
            ).to_list(length=500)
            next_ids: set[str] = set()
            for e in edges_out:
                all_edges.append(KGEdge(**e))
                next_ids.add(e["source_id"])
                next_ids.add(e["target_id"])
            frontier = next_ids - set(all_nodes.keys())
            if frontier:
                docs = await self.nodes.find({"repo_id": repo_id, "id": {"$in": list(frontier)}}, {"_id": 0}).to_list(length=500)
                for d in docs:
                    all_nodes[d["id"]] = KGNode(**d)
        return {"nodes": list(all_nodes.values()), "edges": all_edges}

    async def delete_repo(self, repo_id: str) -> None:
        await self.nodes.delete_many({"repo_id": repo_id})
        await self.edges.delete_many({"repo_id": repo_id})

    async def find_node_by_qname(self, repo_id: str, qualified_name: str) -> KGNode | None:
        d = await self.nodes.find_one({"repo_id": repo_id, "qualified_name": qualified_name}, {"_id": 0})
        return KGNode(**d) if d else None

    async def count_nodes(self, repo_id: str | None = None) -> int:
        return await self.nodes.count_documents({"repo_id": repo_id} if repo_id else {})

    async def count_edges(self, repo_id: str | None = None) -> int:
        return await self.edges.count_documents({"repo_id": repo_id} if repo_id else {})
