"""Repository-scoped Neo4j graph adapter. All Cypher parameters are bound."""
from __future__ import annotations
import json
from neo4j import AsyncGraphDatabase
from ..config import settings
from ..models import KGEdge, KGNode


class Neo4jGraphService:
    def __init__(self, driver=None):
        self.driver = driver or AsyncGraphDatabase.driver(
            settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            connection_timeout=10, max_connection_pool_size=20,
            connection_acquisition_timeout=15, max_transaction_retry_time=15,
        )

    async def _query(self, query, **params):
        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            async def run(tx):
                result = await tx.run(query, **params)
                return await result.data()
            return await session.execute_write(run)

    async def initialize(self):
        await self._query("CREATE CONSTRAINT code_node_id IF NOT EXISTS FOR (n:CodeNode) REQUIRE n.id IS UNIQUE")
        await self._query("CREATE INDEX code_repo IF NOT EXISTS FOR (n:CodeNode) ON (n.repo_id)")
        await self._query("CREATE INDEX code_qname IF NOT EXISTS FOR (n:CodeNode) ON (n.repo_id, n.qualified_name)")

    async def ping(self):
        await self.driver.verify_connectivity()

    async def close(self):
        await self.driver.close()

    @staticmethod
    def _node(data):
        if not data:
            return None
        data = dict(data)
        data["metadata"] = json.loads(data.pop("metadata_json", "{}"))
        return KGNode(**data)

    @staticmethod
    def _edge(data):
        data = dict(data)
        data["type"] = data.pop("kind", data.get("type", "CONTAINS"))
        data["metadata"] = json.loads(data.pop("metadata_json", "{}"))
        return KGEdge(**data)

    async def upsert_nodes(self, nodes):
        for start in range(0, len(nodes), 300):
            rows = []
            for node in nodes[start:start + 300]:
                row = node.model_dump()
                row["metadata_json"] = json.dumps(row.pop("metadata"))
                rows.append(row)
            await self._query("UNWIND $rows AS row MERGE (n:CodeNode {id: row.id}) SET n = row", rows=rows)
        return len(nodes)

    async def upsert_edges(self, edges):
        for start in range(0, len(edges), 500):
            rows = []
            for edge in edges[start:start + 500]:
                row = edge.model_dump()
                row["kind"] = row.pop("type")
                row["metadata_json"] = json.dumps(row.pop("metadata"))
                rows.append(row)
            await self._query(
                "UNWIND $rows AS row MATCH (a:CodeNode {id: row.source_id, repo_id: row.repo_id}) "
                "MATCH (b:CodeNode {id: row.target_id, repo_id: row.repo_id}) "
                "MERGE (a)-[r:CODE_REL {id: row.id}]->(b) SET r = row", rows=rows)
        return len(edges)

    async def get_node(self, repo_id, node_id):
        rows = await self._query("MATCH (n:CodeNode {repo_id:$repo, id:$id}) RETURN properties(n) AS n", repo=repo_id, id=node_id)
        return self._node(rows[0]["n"]) if rows else None

    async def list_nodes(self, repo_id, type_=None, limit=500, offset=0):
        rows = await self._query(
            "MATCH (n:CodeNode {repo_id:$repo}) WHERE $type IS NULL OR n.type=$type "
            "RETURN properties(n) AS n ORDER BY n.file_path, n.start_line, n.id SKIP $offset LIMIT $limit",
            repo=repo_id, type=type_, offset=offset, limit=limit)
        return [self._node(r["n"]) for r in rows]

    async def list_edges(self, repo_id, limit=1000, node_ids=None):
        rows = await self._query(
            "MATCH (a:CodeNode {repo_id:$repo})-[r:CODE_REL]->(b:CodeNode {repo_id:$repo}) "
            "WHERE r.repo_id=$repo AND ($ids IS NULL OR (a.id IN $ids AND b.id IN $ids)) "
            "RETURN properties(r) AS r ORDER BY r.id LIMIT $limit", repo=repo_id, limit=limit, ids=node_ids)
        return [self._edge(r["r"]) for r in rows]

    async def neighbors(self, repo_id, node_id, depth=1):
        # Bounded breadth-first expansion prevents a dense graph from exploding a variable path query.
        seen, nodes, edges = {node_id}, {}, {}
        root = await self.get_node(repo_id, node_id)
        if root:
            nodes[root.id] = root
        frontier = [node_id]
        for _ in range(min(max(depth, 1), 6)):
            if not frontier or len(nodes) >= 300:
                break
            rows = await self._query(
                "MATCH (a:CodeNode {repo_id:$repo})-[r:CODE_REL]-(b:CodeNode {repo_id:$repo}) "
                "WHERE a.id IN $ids AND r.repo_id=$repo RETURN properties(b) AS n, properties(r) AS r "
                "ORDER BY r.id LIMIT 300", repo=repo_id, ids=frontier)
            frontier = []
            for row in rows:
                n, e = self._node(row["n"]), self._edge(row["r"])
                nodes[n.id], edges[e.id] = n, e
                if n.id not in seen:
                    frontier.append(n.id)
                    seen.add(n.id)
        return {"nodes": list(nodes.values()), "edges": list(edges.values())}

    async def delete_repo(self, repo_id):
        # Batches keep deletion transactions bounded; safe to repeat after partial completion.
        while True:
            rows = await self._query(
                "MATCH (n:CodeNode {repo_id:$repo}) WITH n LIMIT 1000 DETACH DELETE n RETURN count(*) AS count", repo=repo_id)
            if rows[0]["count"] < 1000:
                break

    async def find_node_by_qname(self, repo_id, qualified_name):
        rows = await self._query("MATCH (n:CodeNode {repo_id:$repo, qualified_name:$qname}) RETURN properties(n) AS n LIMIT 1", repo=repo_id, qname=qualified_name)
        return self._node(rows[0]["n"]) if rows else None

    async def count_nodes(self, repo_id=None):
        rows = await self._query("MATCH (n:CodeNode) WHERE $repo IS NULL OR n.repo_id=$repo RETURN count(n) AS count", repo=repo_id)
        return rows[0]["count"]

    async def count_edges(self, repo_id=None):
        rows = await self._query("MATCH ()-[r:CODE_REL]->() WHERE $repo IS NULL OR r.repo_id=$repo RETURN count(r) AS count", repo=repo_id)
        return rows[0]["count"]
