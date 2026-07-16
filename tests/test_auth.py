"""Self-serve auth: session cookie, logout, and the Google OAuth callback."""

import os
from pathlib import Path

import pytest

os.environ["DEV_USER_EMAIL"] = "a@example.com"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_api_pytest.db"
os.environ["SESSION_SECRET"] = "test-session-secret-at-least-32bytes!"
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")

import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402


@pytest.fixture()
async def client():
    Path("./data").mkdir(exist_ok=True)
    from api.main import app
    from db.models import Base
    from db.session import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t", follow_redirects=False) as c:
        yield c


async def _make_user(email: str) -> int:
    from api import auth
    from db.session import SessionLocal
    async with SessionLocal() as s:
        u = await auth.resolve_or_create_user(s, email)
        await s.commit()
        return u.id


async def test_no_session_returns_401(client, monkeypatch):
    # With the dev shim disabled and no cookie, the API is closed.
    monkeypatch.setattr("api.deps.DEV_USER_EMAIL", "")
    assert (await client.get("/api/me")).status_code == 401


async def test_session_cookie_authenticates(client, monkeypatch):
    monkeypatch.setattr("api.deps.DEV_USER_EMAIL", "")
    from api import auth
    uid = await _make_user("cookie@example.com")
    client.cookies.set("session", auth.create_session_token(uid))
    r = await client.get("/api/me")
    assert r.status_code == 200 and r.json()["email"] == "cookie@example.com"


async def test_bad_session_cookie_rejected(client, monkeypatch):
    monkeypatch.setattr("api.deps.DEV_USER_EMAIL", "")
    client.cookies.set("session", "not-a-valid-jwt")
    assert (await client.get("/api/me")).status_code == 401


async def test_logout_clears_cookie(client):
    r = await client.post("/api/auth/logout")
    assert r.status_code == 200 and r.json()["ok"] is True
    # The response instructs the browser to drop the session cookie.
    assert "session=" in r.headers.get("set-cookie", "")


async def test_google_callback_creates_user_and_session(client, monkeypatch):
    monkeypatch.setattr("api.deps.DEV_USER_EMAIL", "")
    # Non-Secure so the issued cookie round-trips over the http test transport.
    monkeypatch.setattr("api.auth.SECURE_COOKIES", False)
    from api import auth

    async def fake_exchange(code):
        assert code == "the-code"
        return {"id_token": "fake-id-token"}

    async def fake_verify(id_token):
        assert id_token == "fake-id-token"
        return {"email": "google@example.com", "email_verified": True, "name": "Goog User",
                "iss": "https://accounts.google.com"}

    monkeypatch.setattr("api.auth._exchange_code", fake_exchange)
    monkeypatch.setattr("api.auth._verify_google_id_token", fake_verify)

    # The callback requires the state query param to match the state cookie (CSRF).
    client.cookies.set("oauth_state", "s123", path="/api/auth")
    r = await client.get("/api/auth/google/callback?code=the-code&state=s123")
    assert r.status_code == 302 and r.headers["location"] == "/"
    assert "session=" in r.headers.get("set-cookie", "")

    # The freshly issued session logs the new user in.
    me = (await client.get("/api/me")).json()
    assert me["email"] == "google@example.com" and me["display_name"] == "Goog User"


async def test_google_callback_rejects_bad_state(client):
    client.cookies.set("oauth_state", "real", path="/api/auth")
    r = await client.get("/api/auth/google/callback?code=x&state=forged")
    assert r.status_code == 400
