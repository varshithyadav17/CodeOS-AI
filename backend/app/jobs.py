"""Database-backed jobs with leases, cancellation and per-repository exclusion.

PostgreSQL advisory locks are held across external-store writes. An expired lease
cannot allow a second worker to index/delete while the original connection is alive.
"""
from __future__ import annotations
import asyncio
import hashlib
import logging
import time
import uuid
from contextlib import asynccontextmanager, suppress
from fastapi import HTTPException
from sqlalchemy import and_, insert, or_, select, text, update
from . import database as db
from .config import settings

logger = logging.getLogger(__name__)
_sqlite_lock = asyncio.Lock()



def repository_lock_key(repo_id):
    return int.from_bytes(hashlib.sha256(repo_id.encode()).digest()[:8], "big", signed=True)


@asynccontextmanager
async def repository_guard(repo_id):
    """Serialize request-owned archive uploads with worker-owned cleanup."""
    engine=db.get_engine()
    if engine.dialect.name != "postgresql":
        async with _sqlite_lock:
            yield
        return
    async with engine.connect() as conn:
        await conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": repository_lock_key(repo_id)})
        await conn.commit()
        try:
            yield
        finally:
            await conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": repository_lock_key(repo_id)})
            await conn.commit()


class JobCancelled(Exception):
    pass


async def enqueue(repo_id, user_id, kind="ingest", details=None):
    async with db.get_engine().begin() as conn:
        repo = (await conn.execute(select(db.repositories).where(db.repositories.c.id == repo_id, db.repositories.c.user_id == user_id).with_for_update())).mappings().first()
        if not repo:
            raise HTTPException(404, "Repository not found")
        active = None
        if repo["active_job_id"]:
            active = (await conn.execute(select(db.jobs).where(db.jobs.c.id == repo["active_job_id"]))).mappings().first()
        pending = active and active["status"] in {"queued", "running", "retry"}
        if kind == "delete":
            if pending and active["kind"] == "delete":
                return dict(active)
            await conn.execute(update(db.jobs).where(db.jobs.c.repo_id == repo_id,
                db.jobs.c.status.in_(["queued", "retry"])).values(status="cancelled", cancel_requested=True, updated_at=db.now()))
            await conn.execute(update(db.jobs).where(db.jobs.c.repo_id == repo_id,
                db.jobs.c.status == "running").values(cancel_requested=True, updated_at=db.now()))
        elif pending or repo["status"] in {"deleting", "delete_failed"}:
            raise HTTPException(409, "A repository job is already active; wait for it to finish.")
        if kind == "review" and repo["status"] != "ready":
            raise HTTPException(409, "Repository must be ready before starting a review.")
        job = dict(id=str(uuid.uuid4()), repo_id=repo_id, user_id=user_id, kind=kind,
            status="queued", attempts=0, next_run_at=0.0, lease_until=0.0, lease_token=None,
            cancel_requested=False, error=None, details=details or {}, created_at=db.now(), updated_at=db.now())
        await conn.execute(insert(db.jobs).values(**job))
        patch = {"active_job_id": job["id"], "updated_at": db.now()}
        if kind not in {"review", "cleanup"}:
            patch.update(status="deleting" if kind == "delete" else "queued", progress=0,
                message="Deletion queued" if kind == "delete" else "Analysis queued")
        await conn.execute(update(db.repositories).where(db.repositories.c.id == repo_id).values(**patch))
        return job


async def check_job(job):
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(select(db.jobs.c.cancel_requested, db.jobs.c.lease_token).where(db.jobs.c.id == job["id"]))).first()
        repo = (await conn.execute(select(db.repositories.c.status).where(db.repositories.c.id == job["repo_id"]))).first()
    if not row or row.cancel_requested or row.lease_token != job["lease_token"] or not repo:
        raise JobCancelled()
    if job["kind"] != "delete" and repo.status in {"deleting", "delete_failed"}:
        raise JobCancelled()


async def save_details(job, **patch):
    job["details"] = {**job["details"], **patch}
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.jobs).where(db.jobs.c.id == job["id"], db.jobs.c.lease_token == job["lease_token"]).values(details=job["details"], updated_at=db.now()))


async def _heartbeat(job):
    while True:
        await asyncio.sleep(max(1, settings.JOB_LEASE_SECONDS / 3))
        async with db.get_engine().begin() as conn:
            await conn.execute(update(db.jobs).where(db.jobs.c.id == job["id"], db.jobs.c.lease_token == job["lease_token"]).values(lease_until=time.time() + settings.JOB_LEASE_SECONDS))


async def _delete(job):
    repo = await db.get_repo_repo().get(job["repo_id"])
    if not repo:
        return
    actions = [("graph", lambda: db.get_graph_service().delete_repo(repo.id)),
               ("vectors", lambda: db.get_vector_store().delete_namespace(repo.id)),
               ("archive", lambda: db.get_storage().delete(repo.archive_key))]
    for name, action in actions:
        await check_job(job)
        if not job["details"].get(name):
            if name != "archive" or repo.archive_key:
                await action()
            await save_details(job, **{name: True})
    # Cascades remove conversations/messages, reviews, memory, docs, activity and jobs.
    await db.get_repo_repo().delete(repo.id)


async def _execute(job):
    await check_job(job)
    if job["kind"] == "delete":
        await _delete(job)
    elif job["kind"] == "cleanup":
        await db.get_graph_service().delete_repo(job["repo_id"])
        await check_job(job)
        await db.get_vector_store().delete_namespace(job["repo_id"])
        await save_details(job, graph=True, vectors=True)
        async with db.get_engine().begin() as conn:
            await conn.execute(update(db.repositories).where(db.repositories.c.id == job["repo_id"],
                db.repositories.c.active_job_id == job["id"]).values(message="Analysis failed; partial indexes were cleaned. Check service health and retry.",updated_at=db.now()))
    elif job["kind"] == "review":
        from .ai.routes import get_review_service
        await get_review_service().kickoff(job["details"]["review_id"])
        await check_job(job)
    else:
        from .repository.service import IngestionService
        await IngestionService().run(job)


async def _record_failure(job, exc):
    permanent = isinstance(exc, ValueError)
    retry = not permanent and job["attempts"] < settings.JOB_MAX_ATTEMPTS
    status = "retry" if retry else "failed"
    cleanup_pending = False
    if job["kind"] == "ingest":
        cleanup = {}
        for name,operation in (("graph", lambda: db.get_graph_service().delete_repo(job["repo_id"])),
            ("vectors", lambda: db.get_vector_store().delete_namespace(job["repo_id"]))):
            try:
                await operation()
                cleanup[name]=True
            except Exception:
                cleanup[name]=False
                cleanup_pending=True
        await save_details(job,failed_ingestion_cleanup=cleanup)
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.jobs).where(db.jobs.c.id == job["id"], db.jobs.c.lease_token == job["lease_token"]).values(
            status=status, lease_until=0, error=type(exc).__name__, next_run_at=time.time() + min(60, 5 * 2**job["attempts"]), updated_at=db.now()))
        if job["kind"] == "review" and not retry:
            await conn.execute(update(db.reviews).where(db.reviews.c.id == job["details"].get("review_id")).values(status="failed", summary="Review failed. Check service health and retry.", updated_at=db.now()))
        if job["kind"] != "review":
            repo_status = "failed" if job["kind"] == "cleanup" else "deleting" if retry and job["kind"] == "delete" else "delete_failed" if job["kind"] == "delete" else "queued" if retry else "failed"
            message = str(exc)[:250] if isinstance(exc, ValueError) else "A service operation failed. Retrying shortly." if retry else "Analysis failed. Check service health and retry."
            if job["kind"] == "delete":
                message = "Cleanup will retry shortly." if retry else "Cleanup incomplete. Use Delete again to retry safely."
            await conn.execute(update(db.repositories).where(db.repositories.c.id == job["repo_id"], db.repositories.c.active_job_id == job["id"]).values(status=repo_status, message=message, updated_at=db.now()))

    if cleanup_pending and not retry:
        try:
            await enqueue(job["repo_id"],job["user_id"],"cleanup")
        except HTTPException:
            # A concurrent re-ingestion/deletion already owns the next cleanup attempt.
            pass


async def run_once():
    """Claim one due job. Returns False when idle. Public for integration tests."""
    engine = db.get_engine()
    postgres = engine.dialect.name == "postgresql"
    if not postgres:
        await _sqlite_lock.acquire()
    lock_key, acquired, job = None, False, None
    async with engine.connect() as conn:
        try:
            due = or_(and_(db.jobs.c.status.in_(["queued", "retry"]), db.jobs.c.next_run_at <= time.time()),
                and_(db.jobs.c.status == "running", db.jobs.c.lease_until < time.time()))
            stmt = select(db.jobs).where(due).order_by(db.jobs.c.created_at).limit(20)
            if postgres:
                stmt = stmt.with_for_update(skip_locked=True)
            rows = (await conn.execute(stmt)).mappings().all()
            for row in rows:
                key = repository_lock_key(row["repo_id"])
                if postgres and not (await conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})).scalar_one():
                    continue
                lock_key, acquired = key, True
                job = dict(row)
                job.update(status="running", attempts=row["attempts"] + 1, lease_token=str(uuid.uuid4()), lease_until=time.time() + settings.JOB_LEASE_SECONDS)
                await conn.execute(update(db.jobs).where(db.jobs.c.id == row["id"]).values(status="running", attempts=job["attempts"], lease_token=job["lease_token"], lease_until=job["lease_until"], updated_at=db.now()))
                break
            await conn.commit()
            if not job:
                return False
            started = time.monotonic()
            pulse = asyncio.create_task(_heartbeat(job))
            try:
                if job["attempts"] > settings.JOB_MAX_ATTEMPTS:
                    raise ValueError("Job recovery limit reached. Check service health and retry.")
                async with asyncio.timeout(settings.INGEST_TIMEOUT_SECONDS):
                    await _execute(job)
                async with engine.begin() as done:
                    await done.execute(update(db.jobs).where(db.jobs.c.id == job["id"], db.jobs.c.lease_token == job["lease_token"]).values(status="done", error=None, lease_until=0, updated_at=db.now()))
            except JobCancelled:
                async with engine.begin() as done:
                    await done.execute(update(db.jobs).where(db.jobs.c.id == job["id"]).values(status="cancelled", lease_until=0, updated_at=db.now()))
            except asyncio.CancelledError:
                # Release this job for another worker; do not consume an attempt on graceful shutdown.
                async with engine.begin() as done:
                    await done.execute(update(db.jobs).where(db.jobs.c.id == job["id"]).values(status="retry", lease_until=0, attempts=max(0, job["attempts"]-1), next_run_at=0, updated_at=db.now()))
                raise
            except Exception as exc:
                logger.exception("job_failed job_id=%s repo_id=%s kind=%s attempt=%s", job["id"], job["repo_id"], job["kind"], job["attempts"])
                await _record_failure(job, exc)
            finally:
                pulse.cancel()
                with suppress(asyncio.CancelledError):
                    await pulse
                logger.info("job_finished job_id=%s repo_id=%s kind=%s seconds=%.3f", job["id"], job["repo_id"], job["kind"], time.monotonic()-started)
            return True
        finally:
            if postgres and acquired:
                await conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
                await conn.commit()
            if not postgres:
                _sqlite_lock.release()


async def worker_loop():
    while True:
        try:
            if await run_once():
                continue
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("worker_poll_failed")
        await asyncio.sleep(settings.JOB_POLL_SECONDS)
