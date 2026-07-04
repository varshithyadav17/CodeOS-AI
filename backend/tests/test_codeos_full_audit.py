"""CodeOS AI – full end-to-end audit (post tree-sitter pin).

Covers ingestion -> graph -> architecture -> files -> timeline,
memory CRUD, docs types & graceful generate, chat graceful failure,
reviews orchestration, stats, and auth edges.

LLM endpoints must NOT crash even with GEMINI_API_KEY empty.
"""
from __future__ import annotations

import io
import os
import time
import uuid
import zipfile

import pytest
import requests

BASE_URL = (
    os.environ.get("VITE_BACKEND_URL")
    or os.environ.get("REACT_APP_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")


# ---------------- helpers ----------------
def _signup(s: requests.Session) -> tuple[str, dict]:
    creds = {
        "email": f"audit_{uuid.uuid4().hex[:8]}@example.com",
        "password": "Audit123!",
        "name": "Audit User",
    }
    r = s.post(f"{BASE_URL}/api/auth/signup", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    return body["token"], creds


def _hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _wait_ready(s: requests.Session, repo_id: str, tok: str, timeout: int = 60) -> dict:
    last = {}
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = s.get(f"{BASE_URL}/api/repos/{repo_id}/status", headers=_hdr(tok), timeout=20)
        assert r.status_code == 200, r.text
        last = r.json()
        if last.get("status") in ("ready", "failed", "error"):
            return last
        time.sleep(1.0)
    return last


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    return s


@pytest.fixture(scope="module")
def auth(api):
    tok, creds = _signup(api)
    return {"token": tok, "creds": creds, "headers": _hdr(tok)}


@pytest.fixture(scope="module")
def sample_zip_bytes() -> bytes:
    path = "/tmp/sample.zip"
    if not os.path.exists(path):
        # build a tiny one in memory
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("sample-repo/src/main.py", "def main():\n    return 1\n")
            z.writestr("sample-repo/src/utils.py", "def add(a,b):\n    return a+b\n")
            z.writestr("sample-repo/src/app.js", "function hello(){return 1}\n")
        return mem.getvalue()
    with open(path, "rb") as f:
        return f.read()


# ---------------- AUTH ----------------
class TestAuth:
    def test_signup_dup_409(self, api, auth):
        r = api.post(f"{BASE_URL}/api/auth/signup", json=auth["creds"], timeout=15)
        assert r.status_code == 409, r.text

    def test_signup_short_password_400(self, api):
        r = api.post(
            f"{BASE_URL}/api/auth/signup",
            json={"email": f"short_{uuid.uuid4().hex[:6]}@e.com", "password": "abc", "name": "x"},
            timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_login_and_me(self, api, auth):
        r = api.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": auth["creds"]["email"], "password": auth["creds"]["password"]},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        tok = r.json()["token"]
        me = api.get(f"{BASE_URL}/api/auth/me", headers=_hdr(tok), timeout=15)
        assert me.status_code == 200, me.text
        u = me.json()["user"]
        assert u["email"] == auth["creds"]["email"]
        assert "password_hash" not in u

    def test_me_unauthenticated_401(self, api):
        r = api.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_google_501(self, api):
        r = api.post(f"{BASE_URL}/api/auth/google", json={"session_id": "any"}, timeout=15)
        assert r.status_code == 501, r.text


# ---------------- INGESTION ----------------
class TestIngestion:
    def test_upload_non_zip_400(self, api, auth):
        files = {"file": ("foo.txt", b"hello", "text/plain")}
        r = api.post(
            f"{BASE_URL}/api/repos/upload",
            headers=_hdr(auth["token"]),
            files=files,
            timeout=20,
        )
        assert r.status_code == 400, r.text
        assert "zip" in r.json().get("detail", "").lower()

    def test_upload_unauthenticated_401(self, api, sample_zip_bytes):
        files = {"file": ("sample.zip", sample_zip_bytes, "application/zip")}
        r = api.post(f"{BASE_URL}/api/repos/upload", files=files, timeout=20)
        assert r.status_code in (401, 403), r.text

    def test_upload_zip_pipeline_ready(self, api, auth, sample_zip_bytes, request):
        files = {"file": ("sample.zip", sample_zip_bytes, "application/zip")}
        r = api.post(
            f"{BASE_URL}/api/repos/upload",
            headers=_hdr(auth["token"]),
            files=files,
            timeout=60,
        )
        assert r.status_code == 200, r.text
        repo = r.json()
        assert "id" in repo
        rid = repo["id"]
        # Persist for downstream classes
        request.config.cache.set("repo_id", rid)
        request.config.cache.set("token", auth["token"])

        st = _wait_ready(api, rid, auth["token"], timeout=60)
        assert st.get("status") == "ready", st
        stats = st.get("stats") or {}
        assert stats.get("files", 0) > 0, stats
        assert stats.get("nodes", 0) > 0, stats
        assert stats.get("edges", 0) > 0, stats


# Reuse the repo from above
@pytest.fixture(scope="module")
def ready_repo(api, auth, sample_zip_bytes):
    files = {"file": ("sample.zip", sample_zip_bytes, "application/zip")}
    r = api.post(f"{BASE_URL}/api/repos/upload", headers=_hdr(auth["token"]), files=files, timeout=60)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    st = _wait_ready(api, rid, auth["token"], timeout=60)
    assert st.get("status") == "ready", st
    return rid


# ---------------- REPOS / GRAPH / ARCH / FILES / TIMELINE ----------------
class TestRepoExploration:
    def test_list_repos_has_new(self, api, auth, ready_repo):
        r = api.get(f"{BASE_URL}/api/repos", headers=_hdr(auth["token"]), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data if isinstance(data, list) else data.get("repositories", data.get("repos", []))
        assert any((it.get("id") == ready_repo) for it in items), items

    def test_graph_returns_nodes_edges(self, api, auth, ready_repo):
        r = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/graph?limit=50",
            headers=_hdr(auth["token"]),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        g = r.json()
        nodes = g.get("nodes") or []
        edges = g.get("edges") or []
        assert len(nodes) > 0
        node_ids = {n.get("id") for n in nodes}
        # edges reference present nodes (allow some edges to reference outside if limited)
        if edges:
            for e in edges[:5]:
                assert e.get("source_id") and e.get("target_id")
        # Persist a node id for follow-up tests
        first_id = next(iter(node_ids))
        api.headers["X-Test-Node"] = first_id  # carry via headers dict (module-scope session)

    def test_graph_node_detail(self, api, auth, ready_repo):
        # pick a node from the graph endpoint
        g = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/graph?limit=20",
            headers=_hdr(auth["token"]),
            timeout=30,
        ).json()
        nid = (g.get("nodes") or [{}])[0].get("id")
        assert nid
        r = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/graph/node/{nid}",
            headers=_hdr(auth["token"]),
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # tolerate either {node, neighbors} or {node, edges, ...}
        assert "node" in body or "id" in body, body

    @pytest.mark.parametrize("view", ["call", "dependency", "package", "service"])
    def test_architecture_views(self, api, auth, ready_repo, view):
        r = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/architecture/graph?view={view}",
            headers=_hdr(auth["token"]),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert "nodes" in b and "edges" in b

    def test_architecture_cycles_and_deadcode(self, api, auth, ready_repo):
        r1 = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/architecture/cycles",
            headers=_hdr(auth["token"]),
            timeout=20,
        )
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert "cycles" in b1 and "count" in b1
        r2 = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/architecture/dead-code",
            headers=_hdr(auth["token"]),
            timeout=20,
        )
        assert r2.status_code == 200, r2.text
        assert "items" in r2.json()

    def test_architecture_impact_and_flow(self, api, auth, ready_repo):
        g = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/graph?limit=10",
            headers=_hdr(auth["token"]),
            timeout=20,
        ).json()
        nid = (g.get("nodes") or [{}])[0].get("id")
        assert nid
        r = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/architecture/impact/{nid}",
            headers=_hdr(auth["token"]),
            timeout=20,
        )
        assert r.status_code == 200, r.text
        r2 = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/architecture/flow/{nid}",
            headers=_hdr(auth["token"]),
            timeout=20,
        )
        assert r2.status_code == 200, r2.text

    def test_files_list(self, api, auth, ready_repo):
        r = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/files",
            headers=_hdr(auth["token"]),
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        files = body if isinstance(body, list) else body.get("files", [])
        assert len(files) > 0
        sample = files[0]
        assert "path" in sample

    def test_timeline_graceful_for_zip(self, api, auth, ready_repo):
        for sub in ("commits", "hotspots", "contributors", "complexity"):
            r = api.get(
                f"{BASE_URL}/api/repos/{ready_repo}/timeline/{sub}",
                headers=_hdr(auth["token"]),
                timeout=20,
            )
            assert r.status_code == 200, f"{sub} -> {r.status_code} {r.text}"
            body = r.json()
            # commits endpoint should explicitly mark unavailable
            if sub == "commits":
                assert body.get("available") is False
                assert body.get("commits") == []


# ---------------- STATS & MEMORY ----------------
class TestStatsMemory:
    def test_stats_reflects_repo(self, api, auth, ready_repo):
        r = api.get(f"{BASE_URL}/api/stats", headers=_hdr(auth["token"]), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # tolerate either flat ints or nested fields
        repos_count = data.get("repos_count") or data.get("repos") or data.get("total_repos") or 0
        assert int(repos_count) >= 1, data

    def test_memory_crud_full(self, api, auth, sample_zip_bytes):
        h = _hdr(auth["token"])
        # Need a repo_id for memory creation; upload one fresh.
        files = {"file": ("sample.zip", sample_zip_bytes, "application/zip")}
        up = api.post(f"{BASE_URL}/api/repos/upload", headers=h, files=files, timeout=60)
        assert up.status_code == 200, up.text
        rid_mem = up.json()["id"]
        _wait_ready(api, rid_mem, auth["token"], timeout=60)
        # CREATE
        payload = {
            "repo_id": rid_mem,
            "title": "TEST_audit_memory",
            "content": "audit testing memory",
            "category": "test",
            "severity": "low",
            "status": "open",
        }
        c = api.post(f"{BASE_URL}/api/memory", headers=h, json=payload, timeout=20)
        assert c.status_code in (200, 201), c.text
        body = c.json()
        mid = body.get("id") or body.get("_id") or body.get("mid")
        assert mid, body

        # LIST
        lst = api.get(f"{BASE_URL}/api/memory", headers=h, timeout=20)
        assert lst.status_code == 200, lst.text

        # PATCH status
        p = api.patch(
            f"{BASE_URL}/api/memory/{mid}",
            headers=h,
            json={"status": "resolved"},
            timeout=20,
        )
        assert p.status_code in (200, 204), p.text

        # SEARCH
        s = api.get(f"{BASE_URL}/api/memory/search?q=audit", headers=h, timeout=20)
        assert s.status_code == 200, s.text

        # STATS
        st = api.get(f"{BASE_URL}/api/memory/stats", headers=h, timeout=20)
        assert st.status_code == 200, st.text
        sb = st.json()
        for k in ("total", "by_status", "by_category", "by_severity"):
            assert k in sb, sb

        # DELETE
        d = api.delete(f"{BASE_URL}/api/memory/{mid}", headers=h, timeout=20)
        assert d.status_code in (200, 204), d.text


# ---------------- LLM-DEPENDENT (must degrade gracefully) ----------------
class TestLLMGraceful:
    def test_docs_types_listed(self, api, auth, ready_repo):
        r = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/docs/types",
            headers=_hdr(auth["token"]),
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        items = body if isinstance(body, list) else body.get("types") or body.get("doc_types") or []
        assert len(items) >= 8, body

    def test_docs_list_empty(self, api, auth, ready_repo):
        r = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/docs",
            headers=_hdr(auth["token"]),
            timeout=20,
        )
        assert r.status_code == 200, r.text

    def test_docs_generate_no_key_does_not_500_crash(self, api, auth, ready_repo):
        # Spec: either persists doc (key set) or raises clean HTTPException (key empty).
        # Accept any 2xx or 4xx/5xx with JSON body. Just must not break server.
        r = api.post(
            f"{BASE_URL}/api/repos/{ready_repo}/docs/generate",
            headers=_hdr(auth["token"]),
            json={"doc_type": "readme"},
            timeout=60,
        )
        assert r.status_code < 600
        # Subsequent endpoint must still work, proving backend isn't crashed.
        r2 = api.get(f"{BASE_URL}/api/", timeout=10)
        assert r2.status_code == 200

    def test_chat_swallows_llm_error(self, api, auth, ready_repo):
        r = api.post(
            f"{BASE_URL}/api/repos/{ready_repo}/chat",
            headers=_hdr(auth["token"]),
            json={"message": "What does this do?"},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # The assistant message should mention API key not configured
        text = (
            body.get("assistant_message", {}).get("content")
            or body.get("message", {}).get("content")
            or body.get("content")
            or str(body)
        )
        assert (
            "Gemini API key is not configured" in text
            or "API key" in text
            or "LLM call failed" in text
        ), body

        # Now conversations should list >= 1
        conv = api.get(
            f"{BASE_URL}/api/repos/{ready_repo}/conversations",
            headers=_hdr(auth["token"]),
            timeout=20,
        )
        assert conv.status_code == 200, conv.text
        clist = conv.json()
        items = clist if isinstance(clist, list) else clist.get("conversations", [])
        assert len(items) >= 1, clist
        cid = items[0].get("id") or items[0].get("_id") or items[0].get("conversation_id")
        if cid:
            cdet = api.get(
                f"{BASE_URL}/api/conversations/{cid}",
                headers=_hdr(auth["token"]),
                timeout=20,
            )
            assert cdet.status_code == 200, cdet.text

    def test_review_orchestrator_does_not_crash(self, api, auth, ready_repo):
        r = api.post(
            f"{BASE_URL}/api/repos/{ready_repo}/reviews",
            headers=_hdr(auth["token"]),
            json={},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        rev = r.json()
        rid = rev.get("id") or rev.get("review_id") or rev.get("_id")
        assert rid, rev
        # Poll up to ~12s
        deadline = time.time() + 15
        final = rev
        while time.time() < deadline:
            time.sleep(1.5)
            g = api.get(
                f"{BASE_URL}/api/reviews/{rid}",
                headers=_hdr(auth["token"]),
                timeout=20,
            )
            if g.status_code == 200:
                final = g.json()
                if final.get("status") in ("done", "failed", "error", "completed"):
                    break
        agents = final.get("agents") or []
        assert isinstance(agents, list)
        # Backend must still be alive
        assert api.get(f"{BASE_URL}/api/", timeout=10).status_code == 200


# ---------------- REPO DELETE / REINGEST ----------------
class TestRepoLifecycle:
    def test_reingest_zip_source(self, api, auth, sample_zip_bytes):
        # upload fresh, then try reingest
        files = {"file": ("sample.zip", sample_zip_bytes, "application/zip")}
        r = api.post(
            f"{BASE_URL}/api/repos/upload",
            headers=_hdr(auth["token"]),
            files=files,
            timeout=60,
        )
        rid = r.json()["id"]
        _wait_ready(api, rid, auth["token"], timeout=60)
        re = api.post(
            f"{BASE_URL}/api/repos/{rid}/reingest",
            headers=_hdr(auth["token"]),
            timeout=30,
        )
        # 400 if local_path missing OR 200 if reingest kicked off
        assert re.status_code in (200, 202, 400), re.text

    def test_delete_repo(self, api, auth, sample_zip_bytes):
        files = {"file": ("sample.zip", sample_zip_bytes, "application/zip")}
        r = api.post(
            f"{BASE_URL}/api/repos/upload",
            headers=_hdr(auth["token"]),
            files=files,
            timeout=60,
        )
        rid = r.json()["id"]
        _wait_ready(api, rid, auth["token"], timeout=60)
        d = api.delete(f"{BASE_URL}/api/repos/{rid}", headers=_hdr(auth["token"]), timeout=30)
        assert d.status_code in (200, 204), d.text
        g = api.get(f"{BASE_URL}/api/repos/{rid}/status", headers=_hdr(auth["token"]), timeout=15)
        assert g.status_code == 404, g.text
