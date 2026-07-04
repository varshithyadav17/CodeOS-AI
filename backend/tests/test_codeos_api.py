"""CodeOS AI – post-merge contract tests.

Covers the wiring guarantees that the merge of the original CodeOS AI
implementation + the standalone migration (Vite + google-genai) must
preserve. LLM-dependent endpoints (chat, docs generate, multi-agent review)
are intentionally NOT exercised because no GEMINI_API_KEY is configured.

Targets the preview ingress (REACT_APP_BACKEND_URL / VITE_BACKEND_URL).
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests

BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or os.environ.get("VITE_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")

# Required routes that the merge must keep mounted under /api.
REQUIRED_ROUTES = [
    "/api/",
    "/api/auth/signup",
    "/api/auth/login",
    "/api/auth/me",
    "/api/auth/google",
    "/api/repos",
    "/api/repos/github",
    "/api/repos/upload",
    "/api/repos/{repo_id}",
    "/api/repos/{repo_id}/status",
    "/api/repos/{repo_id}/files",
    "/api/repos/{repo_id}/reingest",
    "/api/repos/{repo_id}/graph",
    "/api/repos/{repo_id}/graph/node/{node_id}",
    "/api/repos/{repo_id}/chat",
    "/api/repos/{repo_id}/conversations",
    "/api/conversations/{conversation_id}",
    "/api/repos/{repo_id}/reviews",
    "/api/reviews/{review_id}",
    "/api/repos/{repo_id}/architecture/graph",
    "/api/repos/{repo_id}/architecture/cycles",
    "/api/repos/{repo_id}/architecture/dead-code",
    "/api/repos/{repo_id}/architecture/impact/{node_id}",
    "/api/repos/{repo_id}/architecture/flow/{node_id}",
    "/api/repos/{repo_id}/docs",
    "/api/repos/{repo_id}/docs/generate",
    "/api/repos/{repo_id}/docs/export",
    "/api/repos/{repo_id}/docs/types",
    "/api/memory",
    "/api/memory/search",
    "/api/memory/stats",
    "/api/memory/{mid}",
    "/api/memory/import/{review_id}",
    "/api/stats",
    "/api/repos/{repo_id}/timeline/commits",
    "/api/repos/{repo_id}/timeline/complexity",
    "/api/repos/{repo_id}/timeline/contributors",
    "/api/repos/{repo_id}/timeline/file",
    "/api/repos/{repo_id}/timeline/hotspots",
]


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def signup_creds():
    return {
        "email": f"merge_test_{uuid.uuid4().hex[:8]}@example.com",
        "password": "Passw0rd123",
        "name": "Merge Test",
    }


@pytest.fixture(scope="module")
def auth_token(api_client, signup_creds):
    r = api_client.post(f"{BASE_URL}/api/auth/signup", json=signup_creds, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "token" in body and "user" in body
    return body["token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# --- Bootstrap / OpenAPI ----------------------------------------------------
class TestBootstrap:
    def test_root_endpoint(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data == {"name": "CodeOS AI", "version": "0.1.0", "status": "ok"}

    def test_openapi_lists_all_routes_internal(self):
        # OpenAPI is local-only behind the preview ingress; hit container directly.
        r = requests.get("http://localhost:8001/openapi.json", timeout=15)
        assert r.status_code == 200, r.text
        paths = set(r.json().get("paths", {}).keys())
        assert "CodeOS AI" == r.json()["info"]["title"]
        assert r.json()["info"]["version"] == "0.1.0"
        missing = [p for p in REQUIRED_ROUTES if p not in paths]
        assert not missing, f"Missing required routes: {missing}"
        assert len(paths) >= 39, f"Expected >=39 routes, got {len(paths)}"


# --- Auth -------------------------------------------------------------------
class TestAuth:
    def test_signup_returns_token_and_user(self, api_client, signup_creds, auth_token):
        # auth_token fixture already exercised /signup once.
        assert isinstance(auth_token, str) and len(auth_token) > 10
        # No password / password_hash leaked.
        r = api_client.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": signup_creds["email"], "password": signup_creds["password"]},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "token" in body
        user = body["user"]
        assert "password_hash" not in user
        assert "password" not in user
        assert user["email"] == signup_creds["email"]
        assert user["name"] == signup_creds["name"]

    def test_login_token_works_on_me(self, api_client, signup_creds):
        login = api_client.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": signup_creds["email"], "password": signup_creds["password"]},
            timeout=15,
        )
        assert login.status_code == 200, login.text
        token = login.json()["token"]
        me = api_client.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert me.status_code == 200, me.text
        u = me.json()["user"]
        assert u["email"] == signup_creds["email"]
        assert "password_hash" not in u

    def test_me_without_token_unauthorized(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_signup_short_password_returns_400(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/auth/signup",
            json={
                "email": f"shortpw_{uuid.uuid4().hex[:6]}@example.com",
                "password": "abc",
                "name": "Short",
            },
            timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_signup_duplicate_email_returns_409(self, api_client, signup_creds):
        # signup_creds was already used by the auth_token fixture
        r = api_client.post(f"{BASE_URL}/api/auth/signup", json=signup_creds, timeout=15)
        assert r.status_code == 409, r.text

    def test_google_endpoint_is_placeholder_501(self, api_client):
        r = api_client.post(
            f"{BASE_URL}/api/auth/google",
            json={"session_id": "anything"},
            timeout=15,
        )
        assert r.status_code == 501, r.text
        detail = r.json().get("detail", "")
        assert (
            "Google sign-in is not configured" in detail
            or "Google OAuth" in detail
            or "not yet implemented" in detail
        ), detail


# --- Repos / Stats / Memory (no LLM) ---------------------------------------
class TestNonLLMEndpoints:
    def test_list_repos_empty_or_list(self, api_client, auth_headers):
        r = api_client.get(f"{BASE_URL}/api/repos", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # Either a list or {repositories: [...]} shape – accept either.
        if isinstance(data, dict):
            assert any(k in data for k in ("repositories", "repos", "items")) or data == {}
        else:
            assert isinstance(data, list)

    def test_repos_requires_auth(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/repos", timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_stats_returns_payload(self, api_client, auth_headers):
        r = api_client.get(f"{BASE_URL}/api/stats", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)
        # No mongo _id leaks
        assert "_id" not in data

    def test_stats_requires_auth(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/stats", timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_memory_list(self, api_client, auth_headers):
        r = api_client.get(f"{BASE_URL}/api/memory", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        if isinstance(data, list):
            for item in data:
                assert "_id" not in item
        else:
            assert isinstance(data, dict)

    def test_memory_requires_auth(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/memory", timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_memory_stats(self, api_client, auth_headers):
        r = api_client.get(
            f"{BASE_URL}/api/memory/stats", headers=auth_headers, timeout=20
        )
        # Endpoint exists; auth required; payload is a dict
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), (dict, list))
