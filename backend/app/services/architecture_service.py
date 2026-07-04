"""Architecture Intelligence — pure analytics on top of IGraphService.

No new interfaces. No business-logic dependence on MongoDB.
"""
from __future__ import annotations
from collections import defaultdict, deque
import os

from ..core.interfaces.graph import IGraphService
from ..core.models.kg import KGNode, KGEdge


PUBLIC_API_HINTS = ("__init__", "main", "index", "app", "server", "wsgi", "asgi", "manage")
ROLE_PATTERNS = [
    ("controller", ("controller", "route", "router", "handler", "api/", "/api", "view")),
    ("service", ("service", "usecase", "use_case")),
    ("repository", ("repository", "/repo", "/dao", "/db/")),
    ("model", ("model", "schema", "entity")),
    ("util", ("util", "helper", "common")),
    ("test", ("test", "spec")),
]


def _classify_role(path: str) -> str:
    p = path.lower()
    for role, needles in ROLE_PATTERNS:
        if any(n in p for n in needles):
            return role
    return "module"


def _package_of(path: str) -> str:
    # Top two directories or top dir
    parts = path.split("/")
    if len(parts) <= 1:
        return "(root)"
    return "/".join(parts[: min(2, len(parts) - 1)])


def _to_dict_nodes(ns: list[KGNode]) -> list[dict]:
    return [n.model_dump() for n in ns]


def _to_dict_edges(es: list[KGEdge]) -> list[dict]:
    return [e.model_dump() for e in es]


class ArchitectureService:
    def __init__(self, graph: IGraphService):
        self.graph = graph

    async def _load(self, repo_id: str) -> tuple[list[KGNode], list[KGEdge]]:
        nodes = await self.graph.list_nodes(repo_id, limit=5000)
        edges = await self.graph.list_edges(repo_id, limit=20000)
        return nodes, edges

    async def call_graph(self, repo_id: str, limit: int = 200) -> dict:
        nodes, edges = await self._load(repo_id)
        keep_types = {"function", "method"}
        nmap = {n.id: n for n in nodes if n.type in keep_types}
        call_edges = [e for e in edges if e.type == "CALLS" and e.source_id in nmap and e.target_id in nmap]
        # Rank by degree, keep top N
        deg = defaultdict(int)
        for e in call_edges:
            deg[e.source_id] += 1; deg[e.target_id] += 1
        ranked = sorted(nmap.values(), key=lambda n: deg[n.id], reverse=True)[:limit]
        keep_ids = {n.id for n in ranked}
        kept_edges = [e for e in call_edges if e.source_id in keep_ids and e.target_id in keep_ids]
        return {"nodes": _to_dict_nodes(ranked), "edges": _to_dict_edges(kept_edges)}

    async def dependency_graph(self, repo_id: str, limit: int = 200) -> dict:
        nodes, edges = await self._load(repo_id)
        files = {n.id: n for n in nodes if n.type == "file"}
        imp_edges = [e for e in edges if e.type == "IMPORTS" and e.source_id in files and e.target_id in files]
        deg = defaultdict(int)
        for e in imp_edges:
            deg[e.source_id] += 1; deg[e.target_id] += 1
        ranked = sorted(files.values(), key=lambda n: deg[n.id], reverse=True)[:limit]
        keep_ids = {n.id for n in ranked}
        kept = [e for e in imp_edges if e.source_id in keep_ids and e.target_id in keep_ids]
        return {"nodes": _to_dict_nodes(ranked), "edges": _to_dict_edges(kept)}

    async def package_graph(self, repo_id: str, limit: int = 80) -> dict:
        nodes, edges = await self._load(repo_id)
        files = {n.id: n for n in nodes if n.type == "file"}
        pkg_of_node = {nid: _package_of(f.file_path) for nid, f in files.items()}
        # Aggregate IMPORTS by package pair
        pkg_edges = defaultdict(int)
        pkg_loc = defaultdict(int)
        for f in files.values():
            pkg_loc[_package_of(f.file_path)] += int(f.metadata.get("loc", 0))
        for e in edges:
            if e.type != "IMPORTS" or e.source_id not in pkg_of_node or e.target_id not in pkg_of_node:
                continue
            s, t = pkg_of_node[e.source_id], pkg_of_node[e.target_id]
            if s != t:
                pkg_edges[(s, t)] += 1
        # Build pseudo-node dicts
        pkgs = sorted(pkg_loc.items(), key=lambda x: x[1], reverse=True)[:limit]
        pkg_ids = {name: f"pkg::{name}" for name, _ in pkgs}
        out_nodes = [{
            "id": pkg_ids[name], "type": "package", "name": name, "qualified_name": name,
            "file_path": name, "start_line": 0, "end_line": 0, "language": "package",
            "metadata": {"loc": loc},
        } for name, loc in pkgs]
        out_edges = []
        for (s, t), w in pkg_edges.items():
            if s in pkg_ids and t in pkg_ids:
                out_edges.append({
                    "id": f"pe::{s}->{t}", "repo_id": repo_id, "source_id": pkg_ids[s],
                    "target_id": pkg_ids[t], "type": "DEPENDS_ON", "metadata": {"weight": w},
                })
        return {"nodes": out_nodes, "edges": out_edges}

    async def service_graph(self, repo_id: str, limit: int = 200) -> dict:
        nodes, edges = await self._load(repo_id)
        files = {n.id: n for n in nodes if n.type == "file"}
        # Tag each file with role
        roles = {nid: _classify_role(f.file_path) for nid, f in files.items()}
        # Keep only meaningful roles + their IMPORTS edges
        meaningful = {"controller", "service", "repository", "model"}
        keep = {nid: f for nid, f in files.items() if roles[nid] in meaningful}
        deg = defaultdict(int)
        imp_edges = [e for e in edges if e.type == "IMPORTS" and e.source_id in keep and e.target_id in keep]
        for e in imp_edges:
            deg[e.source_id] += 1; deg[e.target_id] += 1
        ranked = sorted(keep.values(), key=lambda n: deg[n.id], reverse=True)[:limit]
        ids = {n.id for n in ranked}
        # Annotate role in metadata
        out_nodes = []
        for n in ranked:
            d = n.model_dump()
            d["metadata"] = {**(d.get("metadata") or {}), "role": roles[n.id]}
            out_nodes.append(d)
        kept = [e for e in imp_edges if e.source_id in ids and e.target_id in ids]
        return {"nodes": out_nodes, "edges": _to_dict_edges(kept)}

    async def execution_flow(self, repo_id: str, node_id: str, depth: int = 3) -> dict:
        """BFS down CALLS edges from a function/method (or file's first function)."""
        nodes, edges = await self._load(repo_id)
        nmap = {n.id: n for n in nodes}
        if node_id not in nmap:
            return {"nodes": [], "edges": [], "root": None}
        adj_out = defaultdict(list)
        for e in edges:
            if e.type == "CALLS":
                adj_out[e.source_id].append(e)
        visited: set[str] = {node_id}
        frontier = deque([(node_id, 0)])
        used_edges: list[KGEdge] = []
        while frontier:
            cur, d = frontier.popleft()
            if d >= depth:
                continue
            for e in adj_out.get(cur, []):
                used_edges.append(e)
                if e.target_id not in visited:
                    visited.add(e.target_id)
                    frontier.append((e.target_id, d + 1))
        out_nodes = [nmap[i] for i in visited if i in nmap]
        # Mark root
        out_nodes_d = []
        for n in out_nodes:
            d = n.model_dump()
            if n.id == node_id:
                d["metadata"] = {**(d.get("metadata") or {}), "is_root": True}
            out_nodes_d.append(d)
        return {"nodes": out_nodes_d, "edges": _to_dict_edges(used_edges), "root": node_id}

    async def detect_cycles(self, repo_id: str) -> dict:
        """Tarjan SCC over IMPORTS edges → cycles among files."""
        nodes, edges = await self._load(repo_id)
        files = {n.id: n for n in nodes if n.type == "file"}
        adj = defaultdict(list)
        for e in edges:
            if e.type == "IMPORTS" and e.source_id in files and e.target_id in files:
                adj[e.source_id].append(e.target_id)

        index = 0
        stack: list[str] = []
        on_stack: dict[str, bool] = {}
        idx: dict[str, int] = {}
        low: dict[str, int] = {}
        sccs: list[list[str]] = []

        def strongconnect(v: str):
            nonlocal index
            idx[v] = index; low[v] = index; index += 1
            stack.append(v); on_stack[v] = True
            for w in adj.get(v, []):
                if w not in idx:
                    strongconnect(w)
                    low[v] = min(low[v], low[w])
                elif on_stack.get(w):
                    low[v] = min(low[v], idx[w])
            if low[v] == idx[v]:
                comp: list[str] = []
                while True:
                    w = stack.pop(); on_stack[w] = False; comp.append(w)
                    if w == v: break
                if len(comp) > 1:
                    sccs.append(comp)

        import sys
        sys.setrecursionlimit(10000)
        for v in list(files.keys()):
            if v not in idx:
                strongconnect(v)

        cycles = []
        for comp in sccs:
            cycles.append({
                "size": len(comp),
                "nodes": [files[i].model_dump() for i in comp],
            })
        cycles.sort(key=lambda c: c["size"], reverse=True)
        return {"cycles": cycles, "count": len(cycles)}

    async def dead_code(self, repo_id: str) -> dict:
        """Heuristic: function/method nodes with 0 incoming CALLS edges and name
        not in PUBLIC_API_HINTS. Confidence reflects how likely it is unused."""
        nodes, edges = await self._load(repo_id)
        funcs = [n for n in nodes if n.type in ("function", "method")]
        in_calls = defaultdict(int)
        for e in edges:
            if e.type == "CALLS":
                in_calls[e.target_id] += 1
        items = []
        for n in funcs:
            if in_calls.get(n.id, 0) > 0:
                continue
            lname = n.name.lower()
            if lname.startswith("_") and not lname.startswith("__"):
                continue  # private helpers are likely module-scope intentional
            if any(h in lname for h in PUBLIC_API_HINTS):
                continue
            confidence = 0.55
            if n.type == "method":
                confidence = 0.45  # could be invoked via dynamic dispatch
            if lname in ("setup", "teardown", "configure"):
                confidence = 0.3
            items.append({
                "node": n.model_dump(),
                "confidence": confidence,
                "reason": "No incoming CALLS edge detected by static analysis.",
            })
        items.sort(key=lambda x: x["confidence"], reverse=True)
        return {"items": items[:200], "count": len(items)}

    async def impact(self, repo_id: str, node_id: str, depth: int = 3) -> dict:
        """Transitive callers (incoming CALLS/IMPORTS) + callees (outgoing)."""
        nodes, edges = await self._load(repo_id)
        nmap = {n.id: n for n in nodes}
        if node_id not in nmap:
            return {"target": None, "callers": [], "callees": [], "dependents": [], "summary": {}}

        out_calls = defaultdict(list); in_calls = defaultdict(list)
        out_imp = defaultdict(list); in_imp = defaultdict(list)
        for e in edges:
            if e.type == "CALLS":
                out_calls[e.source_id].append(e.target_id)
                in_calls[e.target_id].append(e.source_id)
            elif e.type == "IMPORTS":
                out_imp[e.source_id].append(e.target_id)
                in_imp[e.target_id].append(e.source_id)

        def bfs(start: str, adj: dict[str, list[str]]) -> set[str]:
            seen = {start}; frontier = deque([(start, 0)])
            while frontier:
                cur, d = frontier.popleft()
                if d >= depth: continue
                for nxt in adj.get(cur, []):
                    if nxt not in seen:
                        seen.add(nxt); frontier.append((nxt, d + 1))
            seen.discard(start)
            return seen

        callers_ids = bfs(node_id, in_calls)
        callees_ids = bfs(node_id, out_calls)
        deps_ids = bfs(node_id, in_imp) | bfs(node_id, out_imp)

        def as_list(ids):
            return [nmap[i].model_dump() for i in ids if i in nmap][:60]

        target = nmap[node_id].model_dump()
        return {
            "target": target,
            "callers": as_list(callers_ids),
            "callees": as_list(callees_ids),
            "dependents": as_list(deps_ids),
            "summary": {
                "callers": len(callers_ids),
                "callees": len(callees_ids),
                "dependents": len(deps_ids),
            },
        }
