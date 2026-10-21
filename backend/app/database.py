"""PostgreSQL application records and service factories.

Graph nodes live only in Neo4j; code vectors and chunk payloads only in Qdrant.
SQLite is accepted exclusively by the isolated test suite.
"""
from __future__ import annotations
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel
from sqlalchemy import (
    JSON, Boolean, Column, Float, ForeignKey, Index, Integer, MetaData,
    String, Table, Text, UniqueConstraint, delete, event, func, insert, select, update,
)
from sqlalchemy.ext.asyncio import create_async_engine
from .config import settings

metadata = MetaData()


def ident():
    return Column("id", String(36), primary_key=True)


def owner():
    return Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)


def repo_fk(nullable=False):
    return Column("repo_id", String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=nullable, index=True)


def timestamps(updated=True):
    return [Column("created_at", String(40), nullable=False)] + ([Column("updated_at", String(40), nullable=False)] if updated else [])


users = Table("users", metadata, ident(),
    Column("email", String(320), nullable=False, unique=True), Column("name", String(120), nullable=False),
    Column("password_hash", Text), Column("picture", Text), Column("provider", String(20), nullable=False),
    Column("google_subject", String(255)), *timestamps())
Index("uq_users_google_subject", users.c.google_subject, unique=True)
repositories = Table("repositories", metadata, ident(), owner(),
    Column("name", String(200), nullable=False), Column("source", String(20), nullable=False),
    Column("source_url", Text), Column("branch", String(200)), Column("archive_key", Text),
    Column("archive_sha256", String(64)), Column("source_commit", String(40)), Column("active_job_id", String(36)),
    Column("status", String(30), nullable=False, index=True), Column("progress", Integer, nullable=False), Column("message", Text),
    Column("language_breakdown", JSON, nullable=False), Column("stats", JSON, nullable=False),
    Column("file_manifest", JSON, nullable=False), Column("timeline", JSON, nullable=False), *timestamps())
conversations = Table("conversations", metadata, ident(), repo_fk(), owner(), Column("title", String(100), nullable=False), *timestamps())
messages = Table("messages", metadata, ident(),
    Column("conversation_id", String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("role", String(20), nullable=False), Column("content", Text, nullable=False),
    Column("context_nodes", JSON, nullable=False), Column("sources", JSON, nullable=False), Column("relationships", JSON, nullable=False), *timestamps(False))
activities = Table("activity_events", metadata, ident(), owner(), repo_fk(True),
    Column("type", String(80), nullable=False), Column("message", Text, nullable=False), *timestamps(False))
reviews = Table("reviews", metadata, ident(), repo_fk(), owner(),
    Column("status", String(20), nullable=False), Column("progress", Integer, nullable=False), Column("overall_score", Integer, nullable=False),
    Column("summary", Text, nullable=False), Column("action_plan", JSON, nullable=False), Column("agents", JSON, nullable=False), *timestamps())
memories = Table("memories", metadata, ident(), repo_fk(), owner(),
    Column("source", String(20), nullable=False), Column("category", String(80), nullable=False), Column("title", String(300), nullable=False),
    Column("description", Text, nullable=False), Column("severity", String(20), nullable=False), Column("confidence", Float, nullable=False),
    Column("status", String(20), nullable=False), Column("file_path", Text), Column("symbol", Text), Column("tags", JSON, nullable=False),
    Column("review_id", String(36), ForeignKey("reviews.id", ondelete="SET NULL")), Column("finding_id", String(36)),
    *timestamps(), UniqueConstraint("user_id", "finding_id", name="uq_memory_finding"))
documentation = Table("documentation", metadata, ident(), repo_fk(), owner(),
    Column("doc_type", String(80), nullable=False), Column("content", Text, nullable=False), *timestamps(),
    UniqueConstraint("repo_id", "user_id", "doc_type", name="uq_document_type"))
user_settings = Table("user_settings", metadata, Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True), Column("key", String(80), primary_key=True),
    Column("value", JSON, nullable=False), UniqueConstraint("user_id", "key", name="uq_user_setting"))
jobs = Table("jobs", metadata, ident(), repo_fk(), owner(),
    Column("kind", String(20), nullable=False), Column("status", String(20), nullable=False),
    Column("attempts", Integer, nullable=False, default=0), Column("next_run_at", Float, nullable=False, default=0),
    Column("lease_until", Float, nullable=False, default=0), Column("lease_token", String(36)),
    Column("cancel_requested", Boolean, nullable=False, default=False), Column("error", Text),
    Column("details", JSON, nullable=False, default=dict), *timestamps())
Index("ix_jobs_claim", jobs.c.status, jobs.c.next_run_at, jobs.c.lease_until)
Index("ix_repos_owner_created", repositories.c.user_id, repositories.c.created_at)
Index("ix_conversations_repo_updated", conversations.c.repo_id, conversations.c.updated_at)
Index("ix_messages_conversation_created", messages.c.conversation_id, messages.c.created_at)
Index("ix_memories_owner_status", memories.c.user_id, memories.c.status)


def now():
    return datetime.now(timezone.utc).isoformat()


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        options = {"pool_pre_ping": True}
        if settings.DATABASE_URL.startswith("postgresql"):
            options.update(pool_size=settings.DB_POOL_SIZE, max_overflow=10, pool_timeout=30, connect_args={"timeout": 10, "command_timeout": 30})
        _engine = create_async_engine(settings.DATABASE_URL, **options)
        if settings.DATABASE_URL.startswith("sqlite"):
            @event.listens_for(_engine.sync_engine, "connect")
            def sqlite_foreign_keys(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
    return _engine


T = TypeVar("T", bound=BaseModel)


class IMetadataRepository(Protocol, Generic[T]):
    async def insert(self, entity: T) -> T: ...
    async def get(self, entity_id: str) -> T | None: ...
    async def find_one(self, query: dict) -> T | None: ...
    async def list(self, query: dict | None = None, limit: int = 100, sort=None, offset: int = 0) -> list[T]: ...
    async def update(self, entity_id: str, patch: dict) -> T | None: ...
    async def delete(self, entity_id: str) -> bool: ...
    async def count(self, query: dict | None = None) -> int: ...


class IGraphService(Protocol):
    async def upsert_nodes(self, nodes: list) -> int: ...
    async def upsert_edges(self, edges: list) -> int: ...
    async def get_node(self, repo_id: str, node_id: str): ...
    async def list_nodes(self, repo_id: str, type_: str | None = None, limit: int = 500, offset: int = 0) -> list: ...
    async def list_edges(self, repo_id: str, limit: int = 1000, node_ids: list[str] | None = None) -> list: ...
    async def neighbors(self, repo_id: str, node_id: str, depth: int = 1) -> dict: ...
    async def delete_repo(self, repo_id: str) -> None: ...
    async def find_node_by_qname(self, repo_id: str, qualified_name: str): ...
    async def count_nodes(self, repo_id: str | None = None) -> int: ...
    async def count_edges(self, repo_id: str | None = None) -> int: ...


class IVectorStore(Protocol):
    async def upsert(self, chunks: list) -> int: ...
    async def query(self, repo_id: str, query_text: str, k: int = 8) -> list: ...
    async def delete_namespace(self, repo_id: str) -> None: ...
    async def count(self, repo_id: str | None = None) -> int: ...


class SQLMetadataRepository(Generic[T]):
    def __init__(self, table: Table, model=None):
        self.table, self.model = table, model

    def _decode(self, row):
        if row is None:
            return None
        data = dict(row)
        return self.model(**data) if self.model else data

    def _where(self, query):
        conditions = []
        for key, value in (query or {}).items():
            col = self.table.c[key]
            conditions.append(col.in_(value["$in"]) if isinstance(value, dict) and "$in" in value else col == value)
        return conditions

    async def insert(self, entity):
        data = entity.model_dump(mode="json") if isinstance(entity, BaseModel) else dict(entity)
        if isinstance(entity, BaseModel):
            # These metadata fields are intentionally omitted from API model dumps.
            for key in ("file_manifest", "timeline"):
                if key in self.table.c:
                    data[key] = getattr(entity, key)
        async with get_engine().begin() as conn:
            await conn.execute(insert(self.table).values(**data))
        return entity

    async def get(self, entity_id):
        return await self.find_one({"id": entity_id})

    async def find_one(self, query):
        async with get_engine().connect() as conn:
            row = (await conn.execute(select(self.table).where(*self._where(query)).limit(1))).mappings().first()
        return self._decode(row)

    async def list(self, query=None, limit=100, sort=None, offset=0):
        stmt = select(self.table).where(*self._where(query))
        for key, direction in (sort or [("created_at", -1)]):
            stmt = stmt.order_by(self.table.c[key].desc() if direction < 0 else self.table.c[key].asc())
        stmt = stmt.order_by(self.table.c.id).limit(min(limit, 10000)).offset(max(0, offset))
        async with get_engine().connect() as conn:
            rows = (await conn.execute(stmt)).mappings().all()
        return [self._decode(r) for r in rows]

    async def update(self, entity_id, patch):
        patch = dict(patch)
        if "updated_at" in self.table.c:
            patch["updated_at"] = now()
        if patch:
            async with get_engine().begin() as conn:
                await conn.execute(update(self.table).where(self.table.c.id == entity_id).values(**patch))
        return await self.get(entity_id)

    async def delete(self, entity_id):
        async with get_engine().begin() as conn:
            res = await conn.execute(delete(self.table).where(self.table.c.id == entity_id))
        return res.rowcount > 0

    async def count(self, query=None):
        async with get_engine().connect() as conn:
            return (await conn.execute(select(func.count()).select_from(self.table).where(*self._where(query)))).scalar_one()


DictRepo = SQLMetadataRepository


@lru_cache
def get_user_repo():
    from .models import User
    return SQLMetadataRepository(users, User)


@lru_cache
def get_repo_repo():
    from .models import Repository
    return SQLMetadataRepository(repositories, Repository)


@lru_cache
def get_conversation_repo():
    from .models import Conversation
    return SQLMetadataRepository(conversations, Conversation)


@lru_cache
def get_message_repo():
    from .models import Message
    return SQLMetadataRepository(messages, Message)


@lru_cache
def get_activity_repo():
    from .models import ActivityEvent
    return SQLMetadataRepository(activities, ActivityEvent)


@lru_cache
def get_review_repo():
    from .models import Review
    return SQLMetadataRepository(reviews, Review)


@lru_cache
def get_memory_repo():
    from .models import Memory
    return SQLMetadataRepository(memories, Memory)


@lru_cache
def get_docs_repo():
    return DictRepo(documentation)


@lru_cache
def get_graph_service():
    from .stores.graph import Neo4jGraphService
    return Neo4jGraphService()


@lru_cache
def get_vector_store():
    from .stores.vectors import QdrantVectorStore
    return QdrantVectorStore()


@lru_cache
def get_storage():
    from .storage.s3 import S3Storage
    return S3Storage()


class InMemoryCacheService:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        expires, value = self.values.get(key, (0, None))
        return value if expires > time.time() else None

    async def set(self, key, value, ttl_seconds=3600):
        if len(self.values) > 1000:
            self.values.clear()
        self.values[key] = (time.time() + ttl_seconds, value)

    async def delete(self, key):
        self.values.pop(key, None)


@lru_cache
def get_cache():
    return InMemoryCacheService()
