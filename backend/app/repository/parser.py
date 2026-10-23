"""AST parsing and complete, bounded code chunks with stable identifiers."""
from __future__ import annotations
import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from tree_sitter_languages import get_parser
from ..config import settings
from .archive import is_sensitive

EXT_TO_LANG = {".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx", ".java": "java", ".go": "go", ".rs": "rust", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cs": "c_sharp", ".rb": "ruby", ".php": "php", ".md": "markdown", ".json": "json",
    ".yml": "yaml", ".yaml": "yaml", ".toml": "toml", ".sh": "bash", ".css": "css", ".html": "html", ".sql": "sql", ".txt": "text"}
BASENAME_LANG = {"Dockerfile": "dockerfile", "Makefile": "makefile", "README": "markdown", "LICENSE": "text", "Procfile": "text", ".gitignore": "text", ".dockerignore": "text", ".env.example": "text", ".env.sample": "text", ".env.template": "text"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build", ".next", ".cache", "target", ".idea", ".vscode", "vendor", ".aws", ".ssh"}
SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock"}


def stable_id(*parts):
    return str(uuid5(NAMESPACE_URL, "codeos:" + ":".join(str(p) for p in parts)))


@dataclass
class ParsedSymbol:
    type: str
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
    path: str
    language: str
    loc: int
    text: str
    imports: list[str] = field(default_factory=list)
    symbols: list[ParsedSymbol] = field(default_factory=list)
    parse_error: bool = False


def _python(text: str, path: str):
    tree = ast.parse(text)
    lines, imports, symbols = text.splitlines(), [], []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.unparse(node))

    def calls_in(node):
        calls = []
        def visit(current):
            if current is not node and isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                return
            if isinstance(current, ast.Call):
                calls.append(ast.unparse(current.func))
            for child in ast.iter_child_nodes(current):
                visit(child)
        visit(node)
        return list(dict.fromkeys(calls))[:200]

    def walk(node, parent=None, parent_type=None):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(child, ast.ClassDef) else "method" if parent_type == "class" else "function"
                qname = f"{parent}.{child.name}" if parent else f"{path}::{child.name}"
                start = min([child.lineno] + [d.lineno for d in getattr(child, "decorator_list", [])])
                end = child.end_lineno or child.lineno
                symbols.append(ParsedSymbol(kind, child.name, qname, start, end, "\n".join(lines[start-1:end]), parent,
                    [ast.unparse(b) for b in child.bases] if kind == "class" else [], calls_in(child) if kind != "class" else []))
                walk(child, qname, kind)
            else:
                walk(child, parent, parent_type)
    walk(tree)
    return imports, symbols


def _tree_extract(src: bytes, root, path: str):
    imports, symbols = [], []
    function_types = {"function_declaration", "function_definition", "method_definition", "method_declaration", "arrow_function", "function", "function_expression", "function_item", "method", "singleton_method"}
    class_types = {"class_declaration", "class_definition", "class_specifier", "struct_item", "class"}
    def txt(node):
        return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace") if node else ""
    def walk(node, parent=None, parent_kind=None):
        for child in node.children:
            if child.type in {"import_statement", "import_from_statement", "use_declaration", "import_declaration"}:
                imports.append(txt(child))
            if child.type in function_types | class_types:
                name = txt(child.child_by_field_name("name"))
                if not name and child.type == "function_definition":
                    # C/C++ put names inside function/pointer declarators, not
                    # directly on the function node. Keep scoped names intact.
                    declarator = child.child_by_field_name("declarator")
                    while declarator is not None:
                        nested = declarator.child_by_field_name("declarator")
                        if nested is None:
                            name = txt(declarator)
                            break
                        declarator = nested
                if not name and child.parent and child.parent.type in {"variable_declarator", "pair", "assignment_expression"}:
                    name = txt(child.parent.child_by_field_name("name") or child.parent.child_by_field_name("key") or child.parent.child_by_field_name("left"))
                name = name or f"anonymous@{child.start_point[0]+1}:{child.start_point[1]}"
                qname = f"{parent}.{name}" if parent else f"{path}::{name}"
                kind = "class" if child.type in class_types else "method" if "method" in child.type or parent_kind == "class" else "function"
                calls = []
                def find_calls(n):
                    if n is not child and n.type in function_types | class_types:
                        return
                    if n.type in {"call_expression", "call", "method_invocation"}:
                        callee = n.child_by_field_name("function") or n.child_by_field_name("name")
                        if callee:
                            calls.append(txt(callee))
                    for c in n.children:
                        find_calls(c)
                if kind != "class":
                    find_calls(child)
                bases = []
                for c in child.children:
                    if c.type in {"class_heritage", "superclass", "base_class_clause"}:
                        bases.extend(txt(c).replace("extends", "").strip().split(","))
                symbols.append(ParsedSymbol(kind, name, qname, child.start_point[0]+1, child.end_point[0]+1, txt(child), parent, bases, list(dict.fromkeys(calls))[:200]))
                walk(child, qname, kind)
            else:
                walk(child, parent, parent_kind)
    walk(root)
    return imports, symbols


class ParserService:
    def parse_repo(self, root: Path):
        results, parsers = [], {}
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (Path(directory)/d).is_symlink())
            for name in sorted(files):
                path = Path(directory) / name
                rel = path.relative_to(root).as_posix()
                language = EXT_TO_LANG.get(path.suffix.lower()) or BASENAME_LANG.get(name)
                if not language or name in SKIP_FILES or is_sensitive(rel) or path.is_symlink() or path.stat().st_size > settings.MAX_SOURCE_BYTES:
                    continue
                src = path.read_bytes()
                if b"\x00" in src:
                    continue
                text = src.decode("utf-8", errors="replace")
                # Generated/minified lines are poor code evidence and can exceed model limits.
                if any(len(line) > 10000 for line in text.splitlines()):
                    continue
                imports, symbols, error = [], [], False
                try:
                    if language == "python":
                        imports, symbols = _python(text, rel)
                    elif language in {"javascript", "typescript", "tsx", "java", "go", "rust", "c", "cpp", "c_sharp", "ruby", "php"}:
                        if language not in parsers:
                            parsers[language] = get_parser(language)
                        tree = parsers[language].parse(src)
                        error = tree.root_node.has_error
                        imports, symbols = _tree_extract(src, tree.root_node, rel)
                except (SyntaxError, RecursionError, ValueError):
                    error = True
                results.append(ParsedFile(rel, language, len(text.splitlines()), text, imports, symbols, error))
        return results


class EmbeddingService:
    """Chunk every source line, including module-level imports and configuration.

    Symbol references annotate overlapping windows; long functions are never silently truncated.
    """
    def build_chunks(self, repo_id, parsed, node_id_by_qname=None):
        from ..models import CodeChunk
        nodes = node_id_by_qname or {}
        chunks = []
        for file in parsed:
            lines, i = file.text.splitlines(), 0
            while i < len(lines):
                j, chars = i, 0
                while j < len(lines) and j-i < 80 and (chars + len(lines[j]) < 6000 or j == i):
                    chars += len(lines[j]) + 1
                    j += 1
                overlaps = [s for s in file.symbols if s.start_line <= i+1 <= s.end_line]
                symbol = min(overlaps, key=lambda s: s.end_line-s.start_line) if overlaps else None
                text = "\n".join(lines[i:j])
                chunks.append(CodeChunk(id=stable_id(repo_id, "chunk", file.path, i+1, j, text), repo_id=repo_id,
                    node_id=nodes.get(symbol.qualified_name if symbol else file.path), file_path=file.path,
                    start_line=i+1, end_line=j, language=file.language, text=text, token_count=max(1, len(text)//4)))
                if j == len(lines):
                    break
                i = max(i+1, j-8)
        return chunks
