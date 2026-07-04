"""Convert parsed files → KGNode/KGEdge collections."""
from __future__ import annotations
from .parser_service import ParsedFile, ParsedSymbol
from ..core.models.kg import KGNode, KGEdge


class GraphBuilder:
    def build(self, repo_id: str, parsed: list[ParsedFile]) -> tuple[list[KGNode], list[KGEdge]]:
        nodes: list[KGNode] = []
        edges: list[KGEdge] = []
        # qname → node_id index, scoped per repo
        qname_to_id: dict[str, str] = {}
        name_to_id: dict[str, str] = {}  # last-resort match by short name

        # 1) File nodes
        for f in parsed:
            file_node = KGNode(
                repo_id=repo_id, type="file", name=f.path.split("/")[-1],
                qualified_name=f.path, file_path=f.path,
                start_line=1, end_line=f.loc, language=f.language,
                metadata={"loc": f.loc, "imports": f.imports[:50]},
            )
            nodes.append(file_node)
            qname_to_id[f.path] = file_node.id

        # 2) Symbol nodes
        for f in parsed:
            file_id = qname_to_id[f.path]
            for s in f.symbols:
                n = KGNode(
                    repo_id=repo_id, type=s.type, name=s.name,
                    qualified_name=s.qualified_name, file_path=f.path,
                    start_line=s.start_line, end_line=s.end_line, language=f.language,
                    metadata={"signature": s.text.splitlines()[0][:200] if s.text else ""},
                )
                nodes.append(n)
                qname_to_id[s.qualified_name] = n.id
                name_to_id.setdefault(s.name, n.id)
                # CONTAINS edge: file → symbol (top-level) or parent → symbol
                parent_id = qname_to_id.get(s.parent) if s.parent else file_id
                if parent_id:
                    edges.append(KGEdge(repo_id=repo_id, source_id=parent_id, target_id=n.id, type="CONTAINS"))

        # 3) IMPORTS edges (file → file approximation: match by suffix)
        path_index = {f.path: qname_to_id[f.path] for f in parsed}
        for f in parsed:
            file_id = qname_to_id[f.path]
            for imp in f.imports:
                # crude: look for any module token that matches another file's stem
                token = imp.replace("from", "").replace("import", "").strip().split()[0] if imp.strip() else ""
                token = token.strip(",;\"'").split(".")[0]
                if not token:
                    continue
                for path, pid in path_index.items():
                    stem = path.split("/")[-1].split(".")[0]
                    if stem and stem == token and pid != file_id:
                        edges.append(KGEdge(repo_id=repo_id, source_id=file_id, target_id=pid, type="IMPORTS"))
                        break

        # 4) CALLS edges (best-effort name match)
        for f in parsed:
            for s in f.symbols:
                src_id = qname_to_id[s.qualified_name]
                for callee in s.calls[:50]:
                    callee_short = callee.split(".")[-1]
                    target_id = name_to_id.get(callee_short)
                    if target_id and target_id != src_id:
                        edges.append(KGEdge(repo_id=repo_id, source_id=src_id, target_id=target_id, type="CALLS"))

        # 5) EXTENDS edges
        for f in parsed:
            for s in f.symbols:
                if s.type != "class" or not s.extends:
                    continue
                src_id = qname_to_id[s.qualified_name]
                for base in s.extends:
                    base_short = base.split(".")[-1].strip("() ")
                    target_id = name_to_id.get(base_short)
                    if target_id and target_id != src_id:
                        edges.append(KGEdge(repo_id=repo_id, source_id=src_id, target_id=target_id, type="EXTENDS"))

        return nodes, edges
