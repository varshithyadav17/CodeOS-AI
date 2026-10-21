"""Generic helper utilities shared across modules."""
from __future__ import annotations
import math
import re

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")


def tokenize(text: str) -> list[str]:
    """Extract lowercase identifier tokens from text."""
    return [t.lower() for t in TOKEN_RE.findall(text) if len(t) > 1]


def tfidf(text: str, df: dict[str, int], n_docs: int) -> tuple[dict[str, float], float]:
    """Compute a TF-IDF sparse vector and its L2 norm for *text*."""
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


def cosine(
    a: dict[str, float], a_norm: float,
    b: dict[str, float], b_norm: float,
) -> float:
    """Cosine similarity between two sparse TF-IDF vectors."""
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    s = sum(v * b.get(t, 0.0) for t, v in a.items())
    return s / ((a_norm * b_norm) or 1.0)


def extract_json(text: str) -> dict | None:
    """Best-effort extraction of a JSON object from an LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        import json
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            import json
            return json.loads(text[start: end + 1])
        except Exception:
            return None
    return None


async def blocking(function, *args, **kwargs):
    """Finish a blocking operation before its caller tears down temporary paths.

    Cancelling to_thread alone leaves a running thread accessing a deleted workspace.
    """
    import asyncio
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        finally:
            raise
