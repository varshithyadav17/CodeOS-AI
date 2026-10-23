"""Gemini embeddings and Qdrant code index, with no SQL vector mirror."""
from __future__ import annotations
import asyncio
import hashlib
import math
import httpx

from qdrant_client import AsyncQdrantClient, models
from ..config import settings
from ..models import CodeChunk
from ..embedding_limits import EmbeddingBudget, EmbeddingDeferred, embedding_batches, embedding_retry_hint

_budgets = {}


def _embedding_budget():
    key = (settings.GEMINI_API_KEY, settings.EMBEDDING_MODEL)
    if key not in _budgets:
        _budgets[key] = EmbeddingBudget(settings.EMBEDDING_REQUESTS_PER_MINUTE,
            settings.EMBEDDING_INPUTS_PER_MINUTE, settings.EMBEDDING_TOKENS_PER_MINUTE)
    return _budgets[key]


class GeminiEmbedder:
    def __init__(self):
        self._client = None

    async def embed(self, texts: list[str], query=False):
        from google import genai
        from google.genai import types
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("Set GEMINI_API_KEY to enable code embeddings and AI answers.")
        if self._client is None:
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=settings.AI_TIMEOUT_SECONDS * 1000,
                    retry_options=types.HttpRetryOptions(attempts=1)))
        vectors = []
        budget = _embedding_budget()
        for batch in embedding_batches(texts):
            await budget.wait(batch)
            try:
                async with asyncio.timeout(settings.AI_TIMEOUT_SECONDS):
                    result = await self._client.aio.models.embed_content(
                        model=settings.EMBEDDING_MODEL, contents=batch,
                        config=types.EmbedContentConfig(
                            task_type="RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT",
                            output_dimensionality=settings.EMBEDDING_DIMENSIONS))
            except Exception as exc:
                code = getattr(exc, "code", None)
                if code not in {429, 500, 502, 503, 504} and not isinstance(exc, (TimeoutError, ConnectionError, httpx.TransportError)):
                    raise
                delay, reason = embedding_retry_hint(exc)
                budget.defer(delay, reason)
                raise EmbeddingDeferred(delay, reason) from exc
            received = [list(e.values) for e in (result.embeddings or [])]
            if len(received) != len(batch):
                raise RuntimeError("Embedding service returned an unexpected number of vectors.")
            vectors.extend(received)
        if len(vectors) != len(texts):
            raise RuntimeError("Embedding service returned an unexpected number of vectors.")
        for vector in vectors:
            if len(vector) != settings.EMBEDDING_DIMENSIONS or not all(math.isfinite(v) for v in vector):
                raise RuntimeError("Invalid embedding dimensions or values; check the embedding configuration.")
            norm = math.sqrt(sum(x*x for x in vector))
            if not norm:
                raise RuntimeError("Embedding service returned a zero vector.")
            vector[:] = [x / norm for x in vector]
        return vectors

    async def close(self):
        if self._client:
            await self._client.aio.aclose()


class QdrantVectorStore:
    def __init__(self, client=None, embedder=None):
        self.client = client or AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=30)
        self.embedder = embedder or GeminiEmbedder()
        self.collection = settings.QDRANT_COLLECTION
        self.fingerprint = hashlib.sha256(f"{settings.EMBEDDING_MODEL}:{settings.EMBEDDING_DIMENSIONS}:cosine:v1".encode()).hexdigest()[:16]
        # A named vector prevents accidentally reusing same-sized embeddings from a different model.
        self.vector_name = "embedding_" + self.fingerprint

    async def initialize(self):
        if not await self.client.collection_exists(self.collection):
            try:
                await self.client.create_collection(collection_name=self.collection,
                    vectors_config={self.vector_name: models.VectorParams(size=settings.EMBEDDING_DIMENSIONS, distance=models.Distance.COSINE)})
            except Exception:
                if not await self.client.collection_exists(self.collection):
                    raise
        info = await self.client.get_collection(self.collection)
        config = info.config.params.vectors
        vector = config.get(self.vector_name) if isinstance(config, dict) else None
        if not vector or vector.size != settings.EMBEDDING_DIMENSIONS or vector.distance != models.Distance.COSINE:
            raise RuntimeError("Qdrant collection embedding model/dimension/metric mismatch. Use a new collection and re-ingest.")
        if not getattr(self.client, "_client", None).__class__.__name__.endswith("Local"):
            for field in ("repo_id", "embedding_fingerprint", "file_path"):
                await self.client.create_payload_index(self.collection, field_name=field, field_schema=models.PayloadSchemaType.KEYWORD, wait=True)

    def _filter(self, repo_id):
        return models.Filter(must=[models.FieldCondition(key="repo_id", match=models.MatchValue(value=repo_id)),
            models.FieldCondition(key="embedding_fingerprint", match=models.MatchValue(value=self.fingerprint))])

    async def upsert(self, chunks):
        for candidates in embedding_batches(chunks, text=lambda c: c.text):
            # Stable content IDs let a resumed batch reuse points saved before
            # a worker restart or a quota pause, without embedding them again.
            existing = await self.client.retrieve(self.collection, ids=[c.id for c in candidates],
                with_payload=["repo_id", "embedding_fingerprint"], with_vectors=False)
            owned = {p.id for p in existing if (p.payload or {}).get("embedding_fingerprint") == self.fingerprint
                     and any(c.id == p.id and c.repo_id == (p.payload or {}).get("repo_id") for c in candidates)}
            batch = [c for c in candidates if c.id not in owned]
            if not batch:
                continue
            vectors = await self.embedder.embed([c.text for c in batch])
            points = [models.PointStruct(id=c.id, vector={self.vector_name: v},
                payload={**c.model_dump(exclude={"score"}), "embedding_fingerprint": self.fingerprint}) for c, v in zip(batch, vectors)]
            await self.client.upsert(self.collection, points=points, wait=True)
        return len(chunks)

    async def query(self, repo_id, query_text, k=8):
        vector = (await self.embedder.embed([query_text], query=True))[0]
        result = await self.client.query_points(self.collection, query=vector, using=self.vector_name,
            query_filter=self._filter(repo_id), limit=min(k, 50), with_payload=True, with_vectors=False)
        return [CodeChunk(**{**p.payload, "score": p.score}) for p in result.points]

    async def delete_namespace(self, repo_id):
        if await self.client.collection_exists(self.collection):
            # Delete every model version for the authorized repository.
            filt = models.Filter(must=[models.FieldCondition(key="repo_id", match=models.MatchValue(value=repo_id))])
            await self.client.delete(self.collection, points_selector=models.FilterSelector(filter=filt), wait=True)

    async def count(self, repo_id=None):
        result = await self.client.count(self.collection, count_filter=self._filter(repo_id) if repo_id else None, exact=True)
        return result.count

    async def ping(self):
        await self.client.get_collections()

    async def close(self):
        await self.client.close()
        if hasattr(self.embedder, "close"):
            await self.embedder.close()
