"""Orchestrates the repository ingestion pipeline."""
from __future__ import annotations
import asyncio
import ipaddress
import logging
import shutil
import socket
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import git

from ..core.interfaces.graph import IGraphService
from ..core.interfaces.vector import IVectorStore
from ..core.interfaces.metadata import IMetadataRepository
from ..core.interfaces.storage import IStorageService
from ..core.models.repository import Repository, RepoStatus, RepoStats
from .parser_service import ParserService
from .graph_builder import GraphBuilder
from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class UnsafeGitURLError(ValueError):
    """Raised when a git/GitHub URL fails SSRF/scheme validation."""


class UnsafeZipError(ValueError):
    """Raised when a zip archive contains a path-traversal ('zip slip') entry."""


_ALLOWED_GIT_SCHEMES = {"https"}
_ALLOWED_GIT_HOSTS = {"github.com", "www.github.com", "gitlab.com", "www.gitlab.com", "bitbucket.org"}


def _is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def validate_git_url(url: str) -> None:
    """Guard against SSRF: only allow https URLs to known public git hosts
    whose resolved addresses are public (not internal/link-local/metadata IPs)."""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_GIT_SCHEMES:
        raise UnsafeGitURLError(f"URL scheme '{parsed.scheme}' is not allowed; only https is permitted")
    if not parsed.hostname:
        raise UnsafeGitURLError("URL has no hostname")
    host = parsed.hostname.lower()
    if host not in _ALLOWED_GIT_HOSTS:
        raise UnsafeGitURLError(f"Host '{host}' is not an allowed git host")
    if parsed.username or parsed.password:
        raise UnsafeGitURLError("URLs with embedded credentials are not allowed")
    try:
        infos = socket.getaddrinfo(host, 443)
    except socket.gaierror as e:
        raise UnsafeGitURLError(f"Could not resolve host '{host}': {e}") from e
    for info in infos:
        ip = info[4][0]
        if not _is_public_ip(ip):
            raise UnsafeGitURLError(f"Host '{host}' resolves to a non-public address ({ip})")


def _safe_extract(zip_path: Path, dest_dir: Path) -> None:
    """Extract a zip file, rejecting any member whose resolved path would
    escape dest_dir (zip-slip protection) and skipping symlinks."""
    dest_dir = dest_dir.resolve()
    with zipfile.ZipFile(zip_path) as z:
        for member in z.infolist():
            member_path = (dest_dir / member.filename).resolve()
            if member_path != dest_dir and dest_dir not in member_path.parents:
                raise UnsafeZipError(f"Blocked unsafe zip entry (path traversal): {member.filename}")
            mode = member.external_attr >> 16
            if mode and (mode & 0o170000) == 0o120000:
                logger.warning("Skipping symlink entry in zip: %s", member.filename)
                continue
        z.extractall(dest_dir)


class IngestionService:
    def __init__(
        self,
        repos: IMetadataRepository[Repository],
        graph: IGraphService,
        vectors: IVectorStore,
        storage: IStorageService,
    ):
        self.repos = repos
        self.graph = graph
        self.vectors = vectors
        self.storage = storage
        self.parser = ParserService()
        self.builder = GraphBuilder()
        self.embedder = EmbeddingService()

    async def _update(self, repo_id: str, status: RepoStatus, progress: int, message: str | None = None):
        await self.repos.update(repo_id, {"status": status.value, "progress": progress, "message": message})

    async def kickoff(self, repo: Repository, github_url: str | None = None, zip_bytes: bytes | None = None):
        """Background task — runs full pipeline."""
        try:
            workdir = await self.storage.ensure_dir(f"repos/{repo.id}")
            # 1) acquire source
            if github_url:
                validate_git_url(github_url)
                await self._update(repo.id, RepoStatus.CLONING, 5, f"Cloning {github_url}")
                clone_dir = workdir / "src"
                if clone_dir.exists():
                    shutil.rmtree(clone_dir)
                await asyncio.to_thread(self._clone, github_url, clone_dir, repo.branch)
                repo_root = clone_dir
            elif zip_bytes is not None:
                await self._update(repo.id, RepoStatus.CLONING, 5, "Extracting ZIP")
                zip_path = workdir / "src.zip"
                zip_path.write_bytes(zip_bytes)
                clone_dir = workdir / "src"
                if clone_dir.exists():
                    shutil.rmtree(clone_dir)
                clone_dir.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(_safe_extract, zip_path, clone_dir)
                # If zip extracted a single root folder, drill in
                contents = [p for p in clone_dir.iterdir() if not p.name.startswith(".")]
                if len(contents) == 1 and contents[0].is_dir():
                    repo_root = contents[0]
                else:
                    repo_root = clone_dir
            else:
                raise ValueError("No source provided")

            await self.repos.update(repo.id, {"local_path": str(repo_root)})

            # 2) parse
            await self._update(repo.id, RepoStatus.PARSING, 25, "Parsing source with tree-sitter")
            parsed = await asyncio.to_thread(self.parser.parse_repo, repo_root)
            if not parsed:
                await self._update(repo.id, RepoStatus.FAILED, 100, "No parseable source files found")
                return
            lang_breakdown: dict[str, int] = {}
            for f in parsed:
                lang_breakdown[f.language] = lang_breakdown.get(f.language, 0) + 1
            total_loc = sum(f.loc for f in parsed)

            # 3) graph
            await self._update(repo.id, RepoStatus.PARSING, 55, "Building knowledge graph")
            nodes, edges = self.builder.build(repo.id, parsed)
            await self.graph.upsert_nodes(nodes)
            await self.graph.upsert_edges(edges)
            qname_to_id = {n.qualified_name: n.id for n in nodes}

            # 4) chunks + embeddings
            await self._update(repo.id, RepoStatus.EMBEDDING, 75, "Indexing code chunks")
            chunks = self.embedder.build_chunks(repo.id, parsed, qname_to_id)
            await self.vectors.upsert(chunks)

            # 5) finalize
            stats = RepoStats(files=len(parsed), loc=total_loc, nodes=len(nodes), edges=len(edges), chunks=len(chunks))
            await self.repos.update(repo.id, {
                "status": RepoStatus.READY.value, "progress": 100, "message": "Ready",
                "language_breakdown": lang_breakdown, "stats": stats.model_dump(),
            })
        except Exception as e:
            logger.exception("Ingestion failed for repo %s", repo.id)
            await self._update(repo.id, RepoStatus.FAILED, 100, f"Error: {e}")

    @staticmethod
    def _clone(url: str, dest: Path, branch: str | None):
        kwargs = {}
        if branch:
            kwargs["branch"] = branch
        # Full clone (no depth) so Timeline Intelligence can compute commit stats.
        git.Repo.clone_from(url, dest, **kwargs)
