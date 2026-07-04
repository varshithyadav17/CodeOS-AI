"""Mongo-backed vector store using TF-IDF sparse vectors. Swap to Qdrant later."""
from __future__ import annotations
import math
import re
from ...core.interfaces.vector import IVectorStore
from ...core.models.code import CodeChunk
from . import db

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text) if len(t) > 1]


def tfidf(text: str, df: dict[str, int], n_docs: int) -> tuple[dict[str, float], float]:
    tokens = tokenize(text)
    if not tokens:
        return {}, 0.0
    tf: dict[str, int] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    vec: dict[str, float] = {}
    for t, c in tf.items():
        idf = math.log((1 + n_docs) / (1 + df.get(t, 0))) + 1.0
        vec[t] = (c / len(tokens)) * idf
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return vec, norm


def cosine(a: dict[str, float], a_norm: float, b: dict[str, float], b_norm: float) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    s = sum(v * b.get(t, 0.0) for t, v in a.items())
    return s / ((a_norm * b_norm) or 1.0)


class MongoVectorStore(IVectorStore):
    def __init__(self):
        self.col = db["code_chunks"]

    async def upsert(self, chunks: list[CodeChunk]) -> int:
        if not chunks:
            return 0
        # Compute repo-wide DF for proper IDF
        df: dict[str, int] = {}
        for c in chunks:
            seen = set(tokenize(c.text))
            for t in seen:
                df[t] = df.get(t, 0) + 1
        n = len(chunks)
        from pymongo import UpdateOne
        ops = []
        for c in chunks:
            vec, norm = tfidf(c.text, df, n)
            c.sparse_vec = vec
            c.norm = norm
            ops.append(UpdateOne({"id": c.id}, {"$set": c.model_dump()}, upsert=True))
        res = await self.col.bulk_write(ops, ordered=False)
        return (res.upserted_count or 0) + (res.modified_count or 0)

    async def query(self, repo_id: str, query_text: str, k: int = 8) -> list[CodeChunk]:
        # Pull repo chunks (typical repo fits comfortably; index by repo_id)
        docs = await self.col.find({"repo_id": repo_id}, {"_id": 0}).to_list(length=5000)
        if not docs:
            return []
        # Build local DF for the query encoding
        df: dict[str, int] = {}
        for d in docs:
            for t in (d.get("sparse_vec") or {}).keys():
                df[t] = df.get(t, 0) + 1
        q_vec, q_norm = tfidf(query_text, df, len(docs))
        scored: list[tuple[float, dict]] = []
        for d in docs:
            score = cosine(q_vec, q_norm, d.get("sparse_vec") or {}, d.get("norm") or 1.0)
            if score > 0:
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [CodeChunk(**d) for _, d in scored[:k]]
        return top

    async def delete_namespace(self, repo_id: str) -> None:
        await self.col.delete_many({"repo_id": repo_id})

    async def count(self, repo_id: str | None = None) -> int:
        return await self.col.count_documents({"repo_id": repo_id} if repo_id else {})
