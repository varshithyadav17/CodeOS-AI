"""One ingestion path for uploads, GitHub snapshots and re-ingestion."""
from __future__ import annotations
import asyncio
import base64
import hashlib
import ipaddress
import logging
import os
import re
import shutil
import socket
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse
from sqlalchemy import update
from .. import database as db
from ..config import settings
from ..jobs import check_job, JobCancelled, save_details
from ..security import decrypt_credential
from ..models import RepoStats
from ..embedding_limits import EmbeddingDeferred, embedding_batches
from ..utils import blocking
from .archive import safe_extract, archive_tree, sha256
from .graph import GraphBuilder
from .parser import EmbeddingService, ParserService

logger = logging.getLogger(__name__)
_safe_extract = safe_extract


class UnsafeGitURLError(ValueError):
    pass


def validate_git_url(url: str, resolve=True) -> str:
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError as exc:
        raise UnsafeGitURLError("Invalid GitHub URL.") from exc
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.username or parsed.password or port not in {None, 443} or parsed.query or parsed.fragment:
        raise UnsafeGitURLError("Use an HTTPS GitHub repository URL without credentials or query parameters.")
    path = parsed.path.rstrip("/").removesuffix(".git")
    if not re.fullmatch(r"/[A-Za-z0-9][A-Za-z0-9-]{0,99}/[A-Za-z0-9_.-]{1,100}", path) or path.split("/")[-1] in {".", ".."}:
        raise UnsafeGitURLError("Use https://github.com/owner/repository.")
    if resolve:
        try:
            addresses = socket.getaddrinfo("github.com", 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ConnectionError("GitHub DNS is temporarily unavailable.") from exc
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise UnsafeGitURLError("GitHub must resolve to a public address.")
    return "https://github.com" + path + ".git"


def validate_branch(branch):
    if branch and (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]{0,199}", branch) or ".." in branch or "//" in branch or branch.endswith(("/", ".", ".lock"))):
        raise ValueError("Invalid GitHub branch name.")


async def clone_github(url, dest, branch=None, job=None):
    url = await blocking(validate_git_url, url)
    validate_branch(branch)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_LFS_SKIP_SMUDGE": "1"}
    command = ["git", "-c", "http.followRedirects=false", "-c", "protocol.file.allow=never", "-c", "protocol.ext.allow=never",
        "-c", f"core.hooksPath={os.devnull}", "clone", "--quiet", "--depth=1", "--single-branch", "--no-tags"]
    if branch:
        command.extend(["--branch", branch])
    encrypted = (job or {}).get("details", {}).get("github_credential")
    if encrypted:
        token = decrypt_credential(encrypted)
        credential = base64.b64encode(("x-access-token:" + token).encode()).decode()
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraheader", GIT_CONFIG_VALUE_0="AUTHORIZATION: basic " + credential)
    command.extend(["--", url, str(dest)])
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE, env=env)
    output = asyncio.create_task(process.communicate())
    started = time.monotonic()
    try:
        while not output.done():
            await asyncio.sleep(0.5)
            if job:
                await check_job(job)
            if time.monotonic() - started > min(settings.INGEST_TIMEOUT_SECONDS, 300):
                raise TimeoutError("GitHub clone timed out.")
            # Include the .git object database in the disk budget.
            count, size = await blocking(_tree_size, dest)
            if count > settings.MAX_FILES * 2 or size > settings.MAX_EXTRACT_BYTES:
                raise ValueError("GitHub clone exceeds the configured resource limit.")
        _, stderr = await output
        if process.returncode:
            failure = stderr.decode("utf-8", errors="replace").lower()
            if any(term in failure for term in ("could not resolve host", "failed to connect", "connection timed out", "connection reset")):
                raise ConnectionError("GitHub could not be reached. The import will retry.")
            if "remote branch" in failure or "couldn't find remote ref" in failure:
                raise ValueError("That branch was not found. Leave Branch empty to use the repository's default branch.")
            if "repository not found" in failure or "authentication failed" in failure or "could not read username" in failure:
                raise ValueError("GitHub could not open this repository. Check its URL; private repositories need a token with repository contents read access.")
            raise ValueError("GitHub clone failed. Check the URL, branch, and provided token's repository access.")
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
        if not output.done():
            await output
    sha_process = await asyncio.create_subprocess_exec("git", "-C", str(dest), "rev-parse", "HEAD", stdout=asyncio.subprocess.PIPE)
    stdout, _ = await sha_process.communicate()
    if sha_process.returncode:
        raise ValueError("Could not read the cloned commit.")
    return stdout.decode().strip()


def _tree_size(path):
    count = size = 0
    if path.exists():
        for directory, _, files in os.walk(path, followlinks=False):
            for name in files:
                p = Path(directory) / name
                if p.is_symlink():
                    continue
                try:
                    size += p.stat().st_size
                    count += 1
                except FileNotFoundError:
                    pass
    return count, size


class IngestionService:
    def __init__(self):
        self.repos = db.get_repo_repo()
        self.graph = db.get_graph_service()
        self.vectors = db.get_vector_store()
        self.storage = db.get_storage()

    async def _update(self, job, **patch):
        await check_job(job)
        async with db.get_engine().begin() as conn:
            result = await conn.execute(update(db.repositories).where(db.repositories.c.id == job["repo_id"],
                db.repositories.c.active_job_id == job["id"], ~db.repositories.c.status.in_(["deleting", "delete_failed"])).values(**patch, updated_at=db.now()))
        if not result.rowcount:
            raise JobCancelled()

    async def run(self, job):
        repo = await self.repos.get(job["repo_id"])
        started = time.monotonic()
        checkpoint = job.get("details", {}).get("index_checkpoint", {})
        # Context management covers success, exceptions, cancellation and timeouts.
        with tempfile.TemporaryDirectory(prefix="codeos-ingest-") as temporary:
            work = Path(temporary)
            archive, root = work / "source.zip", work / "src"
            await self._update(job, status="embedding" if checkpoint.get("graph_ready") else "cloning",
                progress=repo.progress if checkpoint.get("graph_ready") else 5,
                message="Resuming saved AI indexing" if checkpoint.get("graph_ready") else "Loading repository archive")
            if repo.source == "github" and not repo.archive_sha256:
                clone = work / "clone"
                commit = await clone_github(repo.source_url, clone, repo.branch, job)
                # Persist a bounded metadata snapshot, not the .git directory.
                from ..memory.service import TimelineService
                timeline = await blocking(TimelineService(str(clone)).snapshot)
                await blocking(archive_tree, clone, archive)
                checksum = await blocking(sha256, archive)
                await check_job(job)
                await self.storage.put_archive(repo.archive_key, archive, checksum)
                await self._update(job, archive_sha256=checksum, source_commit=commit, timeline=timeline)
                await save_details(job, github_credential=None)
                repo = await self.repos.get(repo.id)
                await blocking(shutil.rmtree, clone)
            else:
                if not repo.archive_key or not repo.archive_sha256:
                    raise ValueError("No durable repository archive exists. Upload the repository again.")
                await self.storage.get_archive(repo.archive_key, archive)
            if await blocking(sha256, archive) != repo.archive_sha256:
                raise ValueError("Repository archive checksum verification failed.")
            await blocking(safe_extract, archive, root)
            # Normalize GitHub-style ZIPs with a single wrapper directory.
            children = [p for p in root.iterdir() if p.name != "__MACOSX"]
            source_root = children[0] if repo.source == "zip" and len(children) == 1 and children[0].is_dir() else root
            if not checkpoint.get("graph_ready"):
                await self._update(job, status="parsing", progress=25, message="Parsing source and building symbols")
            parsed = await blocking(ParserService().parse_repo, source_root)
            if not parsed:
                raise ValueError("No supported source or documentation files were found in the archive.")
            prefix = source_root.relative_to(root).as_posix()
            manifest = [{"path": f.path, "archive_path": f"{prefix}/{f.path}" if prefix != "." else f.path,
                "language": f.language, "loc": f.loc, "parse_error": f.parse_error} for f in parsed]
            nodes, edges = await blocking(GraphBuilder().build, repo.id, parsed)
            qnames = {n.qualified_name: n.id for n in nodes}
            chunks = await blocking(EmbeddingService().build_chunks, repo.id, parsed, qnames)
            if not chunks:
                raise ValueError("Repository contains no non-empty text to index.")
            fingerprint = hashlib.sha256(("index-v2:" + repo.archive_sha256 + ":" + self.vectors.fingerprint
                + ":" + ":".join(c.id for c in chunks)).encode()).hexdigest()
            await self.graph.initialize()
            await self.vectors.initialize()
            await check_job(job)
            resume = checkpoint.get("fingerprint") == fingerprint and checkpoint.get("graph_ready")
            if resume:
                resume = (await self.graph.count_nodes(repo.id), await self.graph.count_edges(repo.id)) == (len(nodes), len(edges))
                resume = resume and await self.vectors.count(repo.id) >= checkpoint.get("offset", 0)
            if not resume:
                await self._update(job, status="parsing", progress=50, message="Building repository relationships")
                await save_details(job, index_checkpoint={})
                await self.graph.delete_repo(repo.id)
                await self.vectors.delete_namespace(repo.id)
                await check_job(job)
                await self.graph.upsert_nodes(nodes)
                await self.graph.upsert_edges(edges)
                if (await self.graph.count_nodes(repo.id), await self.graph.count_edges(repo.id)) != (len(nodes), len(edges)):
                    raise RuntimeError("Graph count verification failed.")
                checkpoint = {"fingerprint": fingerprint, "graph_ready": True, "offset": 0}
                await save_details(job, index_checkpoint=checkpoint)
            languages = {}
            for file in parsed:
                languages[file.language] = languages.get(file.language, 0) + 1
            offset = checkpoint.get("offset", 0)
            stats = RepoStats(files=len(parsed), loc=sum(f.loc for f in parsed), nodes=len(nodes),
                edges=len(edges), chunks=offset, chunks_total=len(chunks))
            await self._update(job, status="embedding", progress=70 + int(24 * offset / len(chunks)),
                message=f"Files and graph ready. AI indexing: {offset}/{len(chunks)} chunks.",
                file_manifest=manifest, language_breakdown=languages, stats=stats.model_dump())
            logger.info("ingestion_index repo_id=%s files=%d nodes=%d edges=%d chunks=%d completed=%d resumed=%s",
                repo.id, len(parsed), len(nodes), len(edges), len(chunks), offset, bool(resume))
            # Checkpoint only completed writes. Each batch also reuses existing
            # Qdrant IDs if shutdown interrupted the checkpoint transaction.
            for batch in embedding_batches(chunks[offset:], text=lambda c: c.text):
                await check_job(job)
                if time.monotonic() - started > max(30, settings.INGEST_TIMEOUT_SECONDS - 120):
                    raise EmbeddingDeferred(5, "continuation")
                await self.vectors.upsert(batch)
                offset += len(batch)
                checkpoint = {**checkpoint, "offset": offset}
                await save_details(job, index_checkpoint=checkpoint, quota_deferrals=0)
                logger.info("embedding_progress repo_id=%s completed=%d total=%d", repo.id, offset, len(chunks))
                stats.chunks = offset
                await self._update(job, progress=min(94, 70 + int(24 * offset / len(chunks))),
                    message=f"Files and graph ready. AI indexing: {offset}/{len(chunks)} chunks.", stats=stats.model_dump())
            await check_job(job)
            actual = (await self.graph.count_nodes(repo.id), await self.graph.count_edges(repo.id), await self.vectors.count(repo.id))
            if actual != (len(nodes), len(edges), len(chunks)):
                raise RuntimeError("Index count verification failed.")
            logger.info("ingestion_ready repo_id=%s files=%d chunks=%d", repo.id, len(parsed), len(chunks))
            stats.chunks = len(chunks)
            await self._update(job, status="ready", progress=100, message="Ready", file_manifest=manifest,
                language_breakdown=languages, stats=stats.model_dump())
