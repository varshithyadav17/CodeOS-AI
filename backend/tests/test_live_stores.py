"""Opt-in tests against real servers, isolated by repository and collection IDs.

CODEOS_LIVE_STORE_TESTS=1 pytest -q tests/test_live_stores.py
Uses NEO4J_URI/NEO4J_PASSWORD and QDRANT_URL from the test environment.
"""
import os
import uuid
import pytest
from qdrant_client import AsyncQdrantClient
from app.stores.graph import Neo4jGraphService
from app.stores.vectors import QdrantVectorStore
from app.repository.parser import ParserService, EmbeddingService
from app.repository.graph import GraphBuilder
from tests.fakes import TestEmbedder

pytestmark = pytest.mark.skipif(os.getenv("CODEOS_LIVE_STORE_TESTS") != "1",reason="Real Neo4j/Qdrant servers not requested")


async def test_real_neo4j_constraints_upsert_scope_traversal_and_delete(tmp_path):
    graph = Neo4jGraphService()
    one,two = str(uuid.uuid4()),str(uuid.uuid4())
    try:
        await graph.initialize()
        await graph.ping()
        (tmp_path/"auth.py").write_text("def authenticate(token):\n    return token\n")
        (tmp_path/"api.py").write_text("from auth import authenticate\n\ndef login(token):\n    return authenticate(token)\n")
        parsed = ParserService().parse_repo(tmp_path)
        nodes,edges = GraphBuilder().build(one,parsed)
        other_nodes,other_edges = GraphBuilder().build(two,parsed)
        for _ in range(2):
            await graph.upsert_nodes(nodes)
            await graph.upsert_edges(edges)
        await graph.upsert_nodes(other_nodes)
        await graph.upsert_edges(other_edges)
        assert await graph.count_nodes(one) == len(nodes)
        assert await graph.count_edges(one) == len(edges)
        selected = await graph.find_node_by_qname(one,"api.py::login")
        related = await graph.neighbors(one,selected.id,2)
        assert any(e.type == "CALLS" for e in related["edges"])
        assert all(n.repo_id == one for n in related["nodes"])
        assert await graph.get_node(two,selected.id) is None
        assert await graph.find_node_by_qname(one,"' MATCH (n) DETACH DELETE n //") is None
        assert len(await graph.list_nodes(one,limit=1,offset=1)) == 1
        api_nodes = [n.id for n in nodes if n.file_path == 'api.py']
        visible = await graph.list_edges(one, node_ids=api_nodes)
        assert visible and all(e.source_id in api_nodes and e.target_id in api_nodes for e in visible)
        assert await graph.list_edges(one, node_ids=[]) == []
        await graph.delete_repo(one)
        await graph.delete_repo(one)
        assert await graph.count_nodes(one) == 0
        assert await graph.count_edges(one) == 0
        assert await graph.count_nodes(two) == len(other_nodes)
    finally:
        await graph.delete_repo(one)
        await graph.delete_repo(two)
        await graph.close()


async def test_real_qdrant_upsert_search_filter_and_delete(tmp_path):
    from app.config import settings
    client = AsyncQdrantClient(url=settings.QDRANT_URL,trust_env=False)
    vectors = QdrantVectorStore(client=client,embedder=TestEmbedder())
    vectors.collection = "codeos_test_" + uuid.uuid4().hex
    try:
        await vectors.initialize()
        (tmp_path/"auth.py").write_text("def authenticate(token):\n    return token\n")
        parsed = ParserService().parse_repo(tmp_path)
        chunks = EmbeddingService().build_chunks("one",parsed) + EmbeddingService().build_chunks("two",parsed)
        await vectors.upsert(chunks)
        await vectors.upsert(chunks)
        assert await vectors.count() == len(chunks)
        found = await vectors.query("one","authenticate token")
        assert found and all(c.repo_id == "one" for c in found)
        await vectors.delete_namespace("one")
        assert await vectors.count("one") == 0
        assert await vectors.count("two") > 0
    finally:
        await client.delete_collection(vectors.collection)
        await vectors.close()
