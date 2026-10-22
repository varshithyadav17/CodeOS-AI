"""Stable structural graph with conservative static symbol resolution."""
from __future__ import annotations
import ast
import posixpath
import re
from collections import defaultdict
from pathlib import PurePosixPath
from ..models import KGEdge, KGNode
from .parser import stable_id


class GraphBuilder:
    def build(self, repo_id, parsed):
        nodes, edges, file_nodes, symbols, by_name = [], {}, {}, {}, defaultdict(list)
        by_file = defaultdict(dict)
        for file in parsed:
            node = KGNode(id=stable_id(repo_id, "file", file.path), repo_id=repo_id, type="file",
                name=PurePosixPath(file.path).name, qualified_name=file.path, file_path=file.path,
                start_line=1 if file.loc else 0, end_line=file.loc, language=file.language,
                metadata={"loc": file.loc, "imports": file.imports[:100], "parse_error": file.parse_error})
            nodes.append(node)
            file_nodes[file.path] = node
        for file in parsed:
            for symbol in file.symbols:
                node = KGNode(id=stable_id(repo_id, symbol.type, symbol.qualified_name, symbol.start_line),
                    repo_id=repo_id, type=symbol.type, name=symbol.name, qualified_name=symbol.qualified_name,
                    file_path=file.path, start_line=symbol.start_line, end_line=symbol.end_line, language=file.language,
                    metadata={"signature": symbol.text.splitlines()[0][:250] if symbol.text else ""})
                nodes.append(node)
                symbols[(file.path, symbol.qualified_name, symbol.start_line)] = node
                by_file[file.path][symbol.qualified_name] = node
                by_name[symbol.name].append(node)

        def edge(source, target, kind, **meta):
            if not source or not target or source.id == target.id:
                return
            id_ = stable_id(repo_id, source.id, target.id, kind)
            edges[id_] = KGEdge(id=id_, repo_id=repo_id, source_id=source.id, target_id=target.id,
                type=kind, metadata=meta)

        paths = set(file_nodes)
        modules = {p.removesuffix(".py").replace("/", "."): p for p in paths if p.endswith(".py")}
        modules.update({p[:-12].replace("/", "."): p for p in paths if p.endswith("/__init__.py")})
        imported_symbols = defaultdict(dict)

        def js_path(file, module):
            if not module.startswith("."):
                return None
            base = posixpath.normpath(posixpath.join(posixpath.dirname(file), module))
            for suffix in ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", "/index.ts", "/index.tsx", "/index.js", "/index.jsx"):
                if base + suffix in paths:
                    return base + suffix
            return None

        for file in parsed:
            for imp in file.imports:
                targets, aliases = [], []
                if file.language == "python":
                    try:
                        statement = ast.parse(imp).body[0]
                        if isinstance(statement, ast.ImportFrom):
                            base = statement.module or ""
                            if statement.level:
                                parts = list(PurePosixPath(file.path).parent.parts)
                                if statement.level > 1:
                                    parts = parts[:-(statement.level-1)]
                                base = ".".join(parts + ([base] if base else []))
                            target = modules.get(base)
                            if target:
                                targets.append(target)
                                aliases.extend((a.asname or a.name, target, a.name) for a in statement.names)
                            for a in statement.names:
                                sub = modules.get(base + "." + a.name)
                                if sub:
                                    targets.append(sub)
                        elif isinstance(statement, ast.Import):
                            for alias in statement.names:
                                target = modules.get(alias.name)
                                if target:
                                    targets.append(target)
                                    imported_symbols[file.path][alias.asname or alias.name] = (target, None)
                    except (SyntaxError, ValueError):
                        pass
                else:
                    match = re.search(r'''(?:from\s*|import\s*)["']([^"']+)["']''', imp)
                    target = js_path(file.path, match.group(1)) if match else None
                    if target:
                        targets.append(target)
                        named = re.search(r"\{([^}]+)\}", imp)
                        if named:
                            for item in named.group(1).split(","):
                                names = re.split(r"\s+as\s+", item.strip())
                                if names[0]:
                                    aliases.append((names[-1], target, names[0]))
                for target in set(targets):
                    edge(file_nodes[file.path], file_nodes[target], "IMPORTS", resolution="static_module")
                for local, target, name in aliases:
                    imported_symbols[file.path][local] = (target, name)

        def resolve(file, symbol, name):
            short = name.split(".")[-1]
            if name.startswith(("self.", "cls.", "this.")) and symbol.parent:
                return by_file[file.path].get(symbol.parent + "." + short)
            # Prefer lexical scope, then file-level definitions, then explicit imports.
            scope = symbol.qualified_name
            while "." in scope.split("::")[-1]:
                scope = scope.rsplit(".", 1)[0]
                found = by_file[file.path].get(scope + "." + short)
                if found:
                    return found
            local = by_file[file.path].get(file.path + "::" + name)
            if local:
                return local
            alias = imported_symbols[file.path].get(name.split(".")[0])
            if alias:
                target_file, original = alias
                return by_file[target_file].get(target_file + "::" + (original or short))
            candidates = by_name.get(short, [])
            # An unresolved receiver could refer to an unrelated object; don't invent that edge.
            if "." not in name and len(candidates) == 1:
                return candidates[0]
            return None

        for file in parsed:
            for symbol in file.symbols:
                node = symbols[(file.path, symbol.qualified_name, symbol.start_line)]
                parent = by_file[file.path].get(symbol.parent) if symbol.parent else file_nodes[file.path]
                edge(parent, node, "CONTAINS")
                for call in symbol.calls:
                    edge(node, resolve(file, symbol, call), "CALLS", resolution="static_best_effort")
                for base in symbol.extends:
                    edge(node, resolve(file, symbol, base.strip()), "EXTENDS", resolution="static_best_effort")
        return nodes, list(edges.values())
