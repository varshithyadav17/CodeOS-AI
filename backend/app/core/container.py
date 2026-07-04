"""Dependency container — single place to wire adapters to interfaces.

Swap implementations here when migrating Mongo → Neo4j/Qdrant/etc.
"""
from __future__ import annotations
from functools import lru_cache

from .interfaces import IGraphService, IVectorStore, IMetadataRepository, ICacheService, IStorageService
from .models import User, Repository, Conversation, Message, ActivityEvent

from ..infrastructure.mongodb.metadata_repo import MongoMetadataRepository
from ..infrastructure.mongodb.graph_service import MongoGraphService
from ..infrastructure.mongodb.vector_store import MongoVectorStore
from ..infrastructure.mongodb.cache_service import InMemoryCacheService
from ..infrastructure.storage.local_fs import LocalFileStorage


@lru_cache
def get_graph_service() -> IGraphService:
    return MongoGraphService()


@lru_cache
def get_vector_store() -> IVectorStore:
    return MongoVectorStore()


@lru_cache
def get_cache() -> ICacheService:
    return InMemoryCacheService()


@lru_cache
def get_storage() -> IStorageService:
    return LocalFileStorage()


@lru_cache
def get_user_repo() -> IMetadataRepository[User]:
    return MongoMetadataRepository("users", User)


@lru_cache
def get_repo_repo() -> IMetadataRepository[Repository]:
    return MongoMetadataRepository("repositories", Repository)


@lru_cache
def get_conversation_repo() -> IMetadataRepository[Conversation]:
    return MongoMetadataRepository("conversations", Conversation)


@lru_cache
def get_message_repo() -> IMetadataRepository[Message]:
    return MongoMetadataRepository("messages", Message)


@lru_cache
def get_activity_repo() -> IMetadataRepository[ActivityEvent]:
    return MongoMetadataRepository("activity_events", ActivityEvent)
