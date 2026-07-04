"""Builds CodeChunks from parsed files."""
from __future__ import annotations
from .parser_service import ParsedFile
from ..core.models.code import CodeChunk

MAX_CHUNK_LINES = 80
OVERLAP = 10


class EmbeddingService:
    """For Phase-1 we produce text chunks; vector_store handles TF-IDF.
    Phase-2: call Gemini Embeddings here and persist dense vectors."""

    def build_chunks(self, repo_id: str, parsed: list[ParsedFile], node_id_by_qname: dict[str, str] | None = None) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        node_id_by_qname = node_id_by_qname or {}
        for f in parsed:
            # Prefer symbol-level chunks
            if f.symbols:
                for s in f.symbols:
                    chunks.append(CodeChunk(
                        repo_id=repo_id,
                        node_id=node_id_by_qname.get(s.qualified_name),
                        file_path=f.path,
                        start_line=s.start_line,
                        end_line=s.end_line,
                        language=f.language,
                        text=f"# {f.path} :: {s.qualified_name}\n{s.text}",
                        token_count=len(s.text.split()),
                    ))
            else:
                # File-level sliding-window chunks
                lines = f.text.splitlines()
                i = 0
                while i < len(lines):
                    j = min(i + MAX_CHUNK_LINES, len(lines))
                    block = "\n".join(lines[i:j])
                    chunks.append(CodeChunk(
                        repo_id=repo_id, file_path=f.path,
                        start_line=i + 1, end_line=j, language=f.language,
                        text=f"# {f.path}\n{block}",
                        token_count=len(block.split()),
                    ))
                    if j == len(lines):
                        break
                    i = j - OVERLAP
        return chunks
