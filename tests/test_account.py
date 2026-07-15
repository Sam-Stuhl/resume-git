"""Account & profile: display name, behind_access flag, delete account."""

import asyncio
import json
import os
from pathlib import Path

import pytest

os.environ["DEV_USER_EMAIL"] = "a@example.com"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_api_pytest.db"

import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402

SAMPLE = json.loads(
    (Path(__file__).resolve().parent.parent / "samples" / "sample_resume.json").read_text()
)
USER_HEADER = "cf-access-authenticated-user-email"


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
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def test_display_name_set_and_clear(client):
    # Unset by default.
    assert (await client.get("/api/me")).json()["display_name"] is None

    await client.put("/api/settings", json={"display_name": "  Sam Stuhl  "})
    assert (await client.get("/api/me")).json()["display_name"] == "Sam Stuhl"  # trimmed

    # Empty string clears it back to null.
    await client.put("/api/settings", json={"display_name": ""})
    assert (await client.get("/api/me")).json()["display_name"] is None

    # Other settings still work alongside display_name.
    await client.put("/api/settings", json={"display_name": "X", "ai_enabled": False})
    me = (await client.get("/api/me")).json()
    assert me["display_name"] == "X" and me["ai_enabled"] is False


async def test_display_name_length_capped(client):
    r = await client.put("/api/settings", json={"display_name": "x" * 201})
    assert r.status_code == 422


async def test_me_reports_created_at(client):
    assert (await client.get("/api/me")).json()["created_at"] is not None


async def test_behind_access_flag(client):
    # Dev shim (no Access header) -> not behind Access, so the UI hides logout.
    assert (await client.get("/api/me")).json()["behind_access"] is False
    # A request carrying the Access identity header -> behind Access.
    r = await client.get("/api/me", headers={USER_HEADER: "edge@example.com"})
    assert r.json()["behind_access"] is True


async def test_concurrent_first_requests_dont_duplicate(client):
    # A brand-new user's first requests race to auto-create the account; the
    # unique-email violation must be swallowed, not surfaced as a 500.
    email = "race@example.com"
    results = await asyncio.gather(
        client.get("/api/me", headers={USER_HEADER: email}),
        client.get("/api/versions", headers={USER_HEADER: email}),
        client.get("/api/me", headers={USER_HEADER: email}),
    )
    assert all(r.status_code == 200 for r in results)


async def test_delete_account_wipes_everything(client):
    await client.post("/api/base", json={"data": SAMPLE, "label": "base"})
    await client.put("/api/settings/api-key", json={"api_key": "sk-ant-api03-x"})
    await client.put("/api/settings", json={"display_name": "Doomed"})
    assert len((await client.get("/api/versions")).json()) == 1

    r = await client.delete("/api/account")
    assert r.status_code == 200 and r.json()["ok"] is True

    # The account is gone; the dev shim re-creates a fresh, empty one on next call.
    assert (await client.get("/api/versions")).json() == []
    me = (await client.get("/api/me")).json()
    assert me["display_name"] is None and me["credential_kind"] is None
