import pytest
from app.repository.parser import ParserService, EmbeddingService
from app.repository.graph import GraphBuilder
from app.config import settings, validate_startup_config
from app.security import create_token, decode_token, hash_password, verify_password
from app.stores.vectors import QdrantVectorStore
from app.models import CodeChunk
from qdrant_client import AsyncQdrantClient, models
from tests.fakes import TestEmbedder


def test_parser_symbols_imports_inheritance_full_chunks_and_stable_ids(tmp_path):
    source = '''from functools import wraps

class Base:
    def helper(self):
        return True

class Auth(Base):
    @wraps(Base.helper)
    def authenticate(self, token):
        def nested():
            return token
        return self.helper()

'''+"def long_function():\n" + "".join(f"    value_{i} = {i}\n" for i in range(240)) + "    return value_239\n"
    (tmp_path/"auth.py").write_text(source)
    (tmp_path/"api.py").write_text("from auth import Auth\n\ndef login():\n    return Auth()\n")
    (tmp_path/"frontend.tsx").write_text("import React from 'react';\nexport const App = () => <div>Hello</div>;\n")
    parsed = ParserService().parse_repo(tmp_path)
    assert len(parsed) == 3
    symbols = {s.name: s for f in parsed for s in f.symbols}
    assert symbols["nested"].type == "function"
    assert symbols["authenticate"].type == "method"
    assert symbols["App"].name == "App"
    assert "value_239" in symbols["long_function"].text
    nodes, edges = GraphBuilder().build("repo", parsed)
    nodes_again, edges_again = GraphBuilder().build("repo", parsed)
    assert {n.id for n in nodes} == {n.id for n in nodes_again}
    assert {e.id for e in edges} == {e.id for e in edges_again}
    assert any(e.type == "EXTENDS" for e in edges)
    assert any(e.type == "CALLS" for e in edges)
    chunks = EmbeddingService().build_chunks("repo", parsed, {n.qualified_name:n.id for n in nodes})
    assert any("value_239" in c.text for c in chunks)
    # Every nonempty line appears in at least one correctly referenced chunk.
    for file in parsed:
        relevant = [c for c in chunks if c.file_path == file.path]
        for line_number, line in enumerate(file.text.splitlines(),1):
            if line.strip():
                assert any(c.start_line <= line_number <= c.end_line and line in c.text for c in relevant)
    assert len({c.id for c in chunks}) == len(chunks)
    assert {c.id for c in chunks} == {c.id for c in EmbeddingService().build_chunks("repo",parsed)}


def test_ambiguous_calls_do_not_create_invented_edges(tmp_path):
    for name in ("one","two"):
        (tmp_path/f"{name}.py").write_text("def same():\n    return 1\n")
    (tmp_path/"other.py").write_text("def entry(obj):\n    same()\n    obj.same()\n")
    nodes, edges = GraphBuilder().build("repo",ParserService().parse_repo(tmp_path))
    assert not [e for e in edges if e.type == "CALLS"]


def test_syntax_errors_keep_source_evidence_and_skip_generated_secrets(tmp_path):
    (tmp_path/"bad.py").write_text("def broken(\n")
    (tmp_path/".env").write_text("secret=1")
    (tmp_path/"huge.js").write_text("a"*11000)
    (tmp_path/"node_modules").mkdir()
    (tmp_path/"node_modules"/"ignored.js").write_text("function ignored() {}")
    parsed = ParserService().parse_repo(tmp_path)
    assert len(parsed) == 1 and parsed[0].parse_error
    assert EmbeddingService().build_chunks("repo",parsed)


async def test_real_qdrant_client_embedding_shape_idempotency_and_isolation():
    vectors = QdrantVectorStore(client=AsyncQdrantClient(location=":memory:"),embedder=TestEmbedder())
    try:
        await vectors.initialize()
        from app.repository.parser import stable_id
        chunks = [CodeChunk(id=stable_id(repo,"test"),repo_id=repo,file_path="auth.py",text="authenticate token login",start_line=1,end_line=1) for repo in ("one","two")]
        await vectors.upsert(chunks)
        await vectors.upsert(chunks)
        assert await vectors.count() == 2
        found = await vectors.query("one","authentication login")
        assert found and all(c.repo_id == "one" for c in found)
        await vectors.delete_namespace("one")
        await vectors.delete_namespace("one")
        assert await vectors.count() == 1 and await vectors.count("two") == 1
    finally:
        await vectors.close()


async def test_qdrant_rejects_incompatible_collection():
    client = AsyncQdrantClient(location=":memory:")
    vectors = QdrantVectorStore(client=client,embedder=TestEmbedder())
    await client.create_collection(vectors.collection, vectors_config=models.VectorParams(size=384,distance=models.Distance.DOT))
    try:
        with pytest.raises(RuntimeError,match="mismatch"):
            await vectors.initialize()
    finally:
        await vectors.close()


def test_startup_rejects_weak_secret_and_insecure_cookies(monkeypatch):
    monkeypatch.setattr(settings,"JWT_SECRET","short")
    with pytest.raises(RuntimeError,match="JWT_SECRET"):
        validate_startup_config()
    monkeypatch.setattr(settings,"JWT_SECRET","x"*40)
    monkeypatch.setattr(settings,"COOKIE_SAMESITE","none")
    monkeypatch.setattr(settings,"COOKIE_SECURE",False)
    with pytest.raises(RuntimeError,match="SameSite"):
        validate_startup_config()


def test_password_hash_and_jwt_verification(monkeypatch):
    password = "Unicode 😀 password "*5
    hashed = hash_password(password)
    assert password not in hashed
    assert verify_password(password,hashed)
    assert not verify_password("wrong",hashed)
    assert not verify_password(password,"malformed")
    token = create_token("user-id","test@example.com")
    assert decode_token(token)["sub"] == "user-id"
    import jwt
    wrong = jwt.encode({"sub":"id"},settings.JWT_SECRET,algorithm="HS256")
    with pytest.raises(jwt.PyJWTError): decode_token(wrong)


@pytest.mark.parametrize('filename,source,symbol', [
    ('main.go', 'package main\nfunc greet() string { return "hello" }\n', 'greet'),
    ('main.rs', 'pub fn greet() -> i32 { 1 }\n', 'greet'),
    ('Main.java', 'class Main { public int greet() { return 1; } }\n', 'greet'),
    ('main.ts', 'export const greet = (name: string) => name;\n', 'greet'),
    ('main.cpp', 'int greet() { return 1; }\n', 'greet'),
    ('main.c', 'char *greet(void) { return 0; }\n', 'greet'),
    ('main.rb', 'class Example\n  def greet\n    1\n  end\nend\n', 'greet'),
    ('Main.cs', 'class Main { public int greet() { return 1; } }\n', 'greet'),
    ('main.php', '<?php function greet() { return 1; }\n', 'greet'),
])
def test_multilanguage_parser_retains_real_symbols_and_source_lines(tmp_path, filename, source, symbol):
    (tmp_path / filename).write_text(source)
    parsed = ParserService().parse_repo(tmp_path)
    assert len(parsed) == 1 and not parsed[0].parse_error
    assert any(s.name == symbol for s in parsed[0].symbols)
    chunks = EmbeddingService().build_chunks('multilanguage', parsed)
    for number, line in enumerate(source.splitlines(), 1):
        if line.strip():
            assert any(c.start_line <= number <= c.end_line and line in c.text for c in chunks)
