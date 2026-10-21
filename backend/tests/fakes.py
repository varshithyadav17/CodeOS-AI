"""Explicit test doubles. Production code never falls back to these adapters."""
import hashlib
import math
from pathlib import Path
from app.utils import tokenize


class TestEmbedder:
    async def embed(self, texts, query=False):
        from app.config import settings
        results = []
        for text in texts:
            v = [0.0]*settings.EMBEDDING_DIMENSIONS
            for token in tokenize(text):
                v[int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % len(v)] += 1.0
            if not any(v):
                v[0] = 1.0
            norm = math.sqrt(sum(x*x for x in v))
            results.append([x/norm for x in v])
        return results


class TestGraph:
    def __init__(self):
        self.nodes, self.edges = {}, {}
        self.fail_delete = False

    async def initialize(self): pass
    async def ping(self): pass
    async def close(self): pass
    async def upsert_nodes(self, nodes):
        self.nodes.update({n.id: n for n in nodes})
        return len(nodes)
    async def upsert_edges(self, edges):
        self.edges.update({e.id: e for e in edges})
        return len(edges)
    async def get_node(self, repo_id, node_id):
        node = self.nodes.get(node_id)
        return node if node and node.repo_id == repo_id else None
    async def list_nodes(self, repo_id, type_=None, limit=500, offset=0):
        values = sorted([n for n in self.nodes.values() if n.repo_id == repo_id and (not type_ or n.type == type_)], key=lambda n: (n.file_path, n.start_line, n.id))
        return values[offset:offset+limit]
    async def list_edges(self, repo_id, limit=1000, node_ids=None):
        ids = set(node_ids) if node_ids is not None else None
        return [e for e in self.edges.values() if e.repo_id == repo_id and
            (ids is None or (e.source_id in ids and e.target_id in ids))][:limit]
    async def neighbors(self, repo_id, node_id, depth=1):
        ids, edges = {node_id}, {}
        for _ in range(depth):
            for edge in list(self.edges.values()):
                if edge.repo_id == repo_id and (edge.source_id in ids or edge.target_id in ids):
                    edges[edge.id] = edge
                    ids.update((edge.source_id, edge.target_id))
        return {"nodes": [n for n in self.nodes.values() if n.repo_id == repo_id and n.id in ids], "edges": list(edges.values())}
    async def delete_repo(self, repo_id):
        if self.fail_delete:
            raise ConnectionError("Simulated Neo4j outage")
        self.nodes = {k: v for k, v in self.nodes.items() if v.repo_id != repo_id}
        self.edges = {k: v for k, v in self.edges.items() if v.repo_id != repo_id}
    async def find_node_by_qname(self, repo_id, qualified_name):
        return next((n for n in self.nodes.values() if n.repo_id == repo_id and n.qualified_name == qualified_name), None)
    async def count_nodes(self, repo_id=None):
        return sum(not repo_id or n.repo_id == repo_id for n in self.nodes.values())
    async def count_edges(self, repo_id=None):
        return sum(not repo_id or e.repo_id == repo_id for e in self.edges.values())


class TestStorage:
    def __init__(self):
        self.objects = {}
        self.fail_delete = False
    @staticmethod
    def key(user_id, repo_id):
        return f"repositories/{user_id}/{repo_id}/source.zip"
    async def put_archive(self, key, path, sha256):
        self.objects[key] = Path(path).read_bytes()
    async def get_archive(self, key, path):
        Path(path).write_bytes(self.objects[key])
    async def delete(self, key):
        if self.fail_delete:
            raise ConnectionError("Simulated S3 outage")
        self.objects.pop(key, None)
    async def ping(self): pass
