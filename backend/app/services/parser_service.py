"""Tree-sitter parser. Extracts files → classes/functions/imports/calls."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from tree_sitter_languages import get_parser

EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
}

SKIP_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build", ".next", ".cache", "target", ".idea", ".vscode"}
MAX_BYTES = 250_000


@dataclass
class ParsedSymbol:
    type: str  # class | function | method
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    text: str
    parent: str | None = None
    extends: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)


@dataclass
class ParsedFile:
    path: str  # relative
    language: str
    loc: int
    text: str
    imports: list[str] = field(default_factory=list)
    symbols: list[ParsedSymbol] = field(default_factory=list)


def _iter_source_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        lang = EXT_TO_LANG.get(p.suffix.lower())
        if not lang:
            continue
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
        except OSError:
            continue
        yield p, lang


def _node_text(src: bytes, node) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")


def _find_children(node, type_name: str):
    out = []
    for c in node.children:
        if c.type == type_name:
            out.append(c)
    return out


def _identifier_text(src: bytes, node) -> str | None:
    if node is None:
        return None
    return _node_text(src, node)


def _python_extract(src: bytes, root, rel_path: str) -> tuple[list[str], list[ParsedSymbol]]:
    imports: list[str] = []
    symbols: list[ParsedSymbol] = []

    def walk(node, parent_qname: str | None):
        for ch in node.children:
            if ch.type == "import_statement" or ch.type == "import_from_statement":
                imports.append(_node_text(src, ch).strip())
            elif ch.type == "class_definition":
                name_node = ch.child_by_field_name("name")
                name = _identifier_text(src, name_node) or "anon"
                qname = f"{parent_qname}.{name}" if parent_qname else f"{rel_path}::{name}"
                bases = []
                sup = ch.child_by_field_name("superclasses")
                if sup is not None:
                    for c in sup.children:
                        if c.type == "identifier":
                            bases.append(_node_text(src, c))
                sym = ParsedSymbol(
                    type="class", name=name, qualified_name=qname,
                    start_line=ch.start_point[0] + 1, end_line=ch.end_point[0] + 1,
                    text=_node_text(src, ch)[:2000], parent=parent_qname, extends=bases,
                )
                symbols.append(sym)
                body = ch.child_by_field_name("body")
                if body is not None:
                    walk(body, qname)
            elif ch.type == "function_definition":
                name_node = ch.child_by_field_name("name")
                name = _identifier_text(src, name_node) or "anon"
                qname = f"{parent_qname}.{name}" if parent_qname else f"{rel_path}::{name}"
                calls: list[str] = []

                def find_calls(n):
                    if n.type == "call":
                        callee = n.child_by_field_name("function")
                        if callee is not None:
                            t = _node_text(src, callee)
                            calls.append(t.split("(")[0].strip())
                    for c in n.children:
                        find_calls(c)

                find_calls(ch)
                sym = ParsedSymbol(
                    type="method" if parent_qname else "function",
                    name=name, qualified_name=qname,
                    start_line=ch.start_point[0] + 1, end_line=ch.end_point[0] + 1,
                    text=_node_text(src, ch)[:2000], parent=parent_qname, calls=calls,
                )
                symbols.append(sym)
            else:
                walk(ch, parent_qname)

    walk(root, None)
    return imports, symbols


def _js_extract(src: bytes, root, rel_path: str, language: str) -> tuple[list[str], list[ParsedSymbol]]:
    imports: list[str] = []
    symbols: list[ParsedSymbol] = []

    def walk(node, parent_qname: str | None):
        for ch in node.children:
            t = ch.type
            if t in ("import_statement", "import_clause"):
                imports.append(_node_text(src, ch).strip())
            elif t == "class_declaration":
                name_node = ch.child_by_field_name("name")
                name = _identifier_text(src, name_node) or "anon"
                qname = f"{parent_qname}.{name}" if parent_qname else f"{rel_path}::{name}"
                bases: list[str] = []
                heritage = ch.child_by_field_name("superclass")
                if heritage is not None:
                    bases.append(_node_text(src, heritage))
                symbols.append(ParsedSymbol(
                    type="class", name=name, qualified_name=qname,
                    start_line=ch.start_point[0] + 1, end_line=ch.end_point[0] + 1,
                    text=_node_text(src, ch)[:2000], parent=parent_qname, extends=bases,
                ))
                walk(ch, qname)
            elif t in ("function_declaration", "method_definition", "arrow_function", "function"):
                name_node = ch.child_by_field_name("name")
                name = _identifier_text(src, name_node) or "anonymous"
                qname = f"{parent_qname}.{name}" if parent_qname else f"{rel_path}::{name}"
                calls: list[str] = []

                def find_calls(n):
                    if n.type == "call_expression":
                        callee = n.child_by_field_name("function")
                        if callee is not None:
                            txt = _node_text(src, callee)
                            calls.append(txt.split("(")[0].strip())
                    for c in n.children:
                        find_calls(c)

                find_calls(ch)
                symbols.append(ParsedSymbol(
                    type="method" if t == "method_definition" else "function",
                    name=name, qualified_name=qname,
                    start_line=ch.start_point[0] + 1, end_line=ch.end_point[0] + 1,
                    text=_node_text(src, ch)[:2000], parent=parent_qname, calls=calls,
                ))
                walk(ch, qname)
            else:
                walk(ch, parent_qname)

    walk(root, None)
    return imports, symbols


class ParserService:
    """Walks a repo dir and produces ParsedFile records."""

    def parse_repo(self, repo_root: Path) -> list[ParsedFile]:
        results: list[ParsedFile] = []
        for path, lang in _iter_source_files(repo_root):
            try:
                src = path.read_bytes()
            except OSError:
                continue
            parser_lang = "tsx" if lang == "tsx" else ("typescript" if lang == "typescript" else lang)
            try:
                parser = get_parser(parser_lang)
            except Exception:
                continue
            try:
                tree = parser.parse(src)
            except Exception:
                continue
            text = src.decode("utf-8", errors="ignore")
            loc = text.count("\n") + 1
            rel = str(path.relative_to(repo_root))
            if lang == "python":
                imports, symbols = _python_extract(src, tree.root_node, rel)
            else:
                imports, symbols = _js_extract(src, tree.root_node, rel, lang)
            results.append(ParsedFile(path=rel, language=lang, loc=loc, text=text, imports=imports, symbols=symbols))
        return results
