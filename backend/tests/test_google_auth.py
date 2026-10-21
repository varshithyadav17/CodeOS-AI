"""Exercise Google's real token verifier with local RSA keys, never a live account."""
import time
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.oauth2 import id_token
from app import database as db
from app.config import settings
from app.models import User


@pytest.fixture
def google_signer(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "codeos-test.apps.googleusercontent.com")
    monkeypatch.setattr(id_token, "_fetch_certs", lambda *args, **kwargs: {"test-key": public})
    def sign(nonce, **overrides):
        claims = {"iss": "https://accounts.google.com", "aud": settings.GOOGLE_CLIENT_ID,
            "sub": "google-subject-1001", "iat": int(time.time()), "exp": int(time.time()) + 600,
            "email": "google-user@gmail.com", "email_verified": True, "name": "Google Tester", "nonce": nonce}
        return jwt.encode({**claims, **overrides}, key, algorithm="RS256", headers={"kid": "test-key"})
    return sign


async def challenge(client):
    response = await client.get("/api/auth/google/challenge")
    assert response.status_code == 200 and response.json()["enabled"]
    assert "httponly" in response.headers["set-cookie"].lower()
    return response.json()["nonce"]


async def test_google_signup_stable_subject_logout_and_cookie_replay(system, google_signer):
    client, *_ = system
    credential = google_signer(await challenge(client))
    response = await client.post("/api/auth/google", json={"credential": credential})
    assert response.status_code == 200, response.text
    user = response.json()["user"]
    assert user["provider"] == "google" and "google_subject" not in user
    assert (await client.get("/api/auth/me")).json()["user"]["id"] == user["id"]
    assert (await client.post("/api/auth/google", json={"credential": credential})).status_code == 401
    await client.post("/api/auth/logout")
    assert (await client.get("/api/auth/me")).status_code == 401
    credential = google_signer(await challenge(client), email="changed@gmail.com")
    response = await client.post("/api/auth/google", json={"credential": credential})
    assert response.json()["user"]["id"] == user["id"]
    assert await db.get_user_repo().count() == 1


@pytest.mark.parametrize("overrides", [
    {"aud": "another-client"}, {"iss": "https://evil.example"}, {"exp": 1},
    {"iat": 4102444800, "exp": 4102444900}, {"email_verified": False},
    {"email_verified": "true"}, {"nonce": "another-browser"}, {"sub": ""},
])
async def test_invalid_google_claims_are_rejected(system, google_signer, overrides):
    client, *_ = system
    nonce = await challenge(client)
    token = google_signer(nonce, **overrides) if "nonce" not in overrides else google_signer(overrides["nonce"])
    assert (await client.post("/api/auth/google", json={"credential": token})).status_code == 401
    assert await db.get_user_repo().count() == 0


async def test_signature_and_challenge_required(system, google_signer):
    client, *_ = system
    assert (await client.post("/api/auth/google", json={"credential": google_signer("missing")})).status_code == 401
    token = google_signer(await challenge(client))
    parts = token.split(".")
    parts[-1] = "A" * len(parts[-1])
    assert (await client.post("/api/auth/google", json={"credential": ".".join(parts)})).status_code == 401
    client.cookies.set("codeos_google_nonce", "tampered", domain="test.local", path="/api/auth")
    assert (await client.post("/api/auth/google", json={"credential": token})).status_code == 401


async def test_local_account_link_requires_password_and_subject_cannot_be_replaced(system, google_signer):
    client, *_ = system
    response = await client.post("/api/auth/signup", json={"email": "google-user@gmail.com", "name": "Local", "password": "local-password-123"})
    original = response.json()["user"]["id"]
    await client.post("/api/auth/logout")
    token = google_signer(await challenge(client))
    response = await client.post("/api/auth/google", json={"credential": token})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "google_link_required"
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.post("/api/auth/google", json={"credential": token, "link_password": "wrong"})).status_code == 401
    response = await client.post("/api/auth/google", json={"credential": token, "link_password": "local-password-123"})
    assert response.status_code == 200 and response.json()["user"]["id"] == original
    await client.post("/api/auth/logout")
    token = google_signer(await challenge(client), sub="different-subject")
    assert (await client.post("/api/auth/google", json={"credential": token, "link_password": "local-password-123"})).status_code == 409
    assert (await db.get_user_repo().get(original)).google_subject == "google-subject-1001"


async def test_unconfigured_provider_and_outage(system, google_signer, monkeypatch):
    import app.auth.auth as auth
    client, *_ = system
    token = google_signer(await challenge(client))
    def unavailable(*args):
        raise ConnectionError("sensitive provider detail")
    monkeypatch.setattr(auth, "verify_google_credential", unavailable)
    response = await client.post("/api/auth/google", json={"credential": token})
    assert response.status_code == 503 and "sensitive" not in response.text
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    assert (await client.get("/api/auth/google/challenge")).json() == {"enabled": False}
    assert (await client.post("/api/auth/google", json={"credential": token})).status_code == 503


async def test_legacy_third_party_email_is_not_linked_automatically(system, google_signer):
    client, *_ = system
    user = User(email="legacy@example.com", name="Legacy", provider="google")
    await db.get_user_repo().insert(user)
    token = google_signer(await challenge(client), email=user.email)
    assert (await client.post("/api/auth/google", json={"credential": token})).status_code == 409
    assert (await db.get_user_repo().get(user.id)).google_subject is None
