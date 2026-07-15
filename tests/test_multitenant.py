"""Multi-tenant guardrails: signup cap + fail-closed Access JWT verification.

Shares the dev identity shim and a SQLite file with test_api (same DATABASE_URL
so the module-level engine singleton is consistent regardless of import order).
Each test resets the schema via the fixture; per-test knobs are monkeypatched
onto ``api.deps`` module globals rather than set through the environment (which
is read only once at import).
"""

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


async def test_signup_cap_blocks_new_users_but_not_existing(client, monkeypatch):
    monkeypatch.setattr("api.deps.MAX_USERS", 2)

    # User a (via the dev shim) is created on first authed request.
    assert (await client.get("/api/versions")).status_code == 200
    # User b (via the header) fills the second and last slot.
    r = await client.get("/api/versions", headers={USER_HEADER: "b@example.com"})
    assert r.status_code == 200

    # User c is a brand-new account over the cap -> clean 403.
    r = await client.get("/api/versions", headers={USER_HEADER: "c@example.com"})
    assert r.status_code == 403
    assert "full" in r.json()["detail"].lower()

    # Existing users still get in even though we're at the cap.
    assert (await client.get("/api/versions")).status_code == 200
    r = await client.get("/api/versions", headers={USER_HEADER: "b@example.com"})
    assert r.status_code == 200


async def test_zero_cap_means_unlimited(client, monkeypatch):
    monkeypatch.setattr("api.deps.MAX_USERS", 0)
    for email in ("a@example.com", "b@example.com", "c@example.com", "d@example.com"):
        r = await client.get("/api/versions", headers={USER_HEADER: email})
        assert r.status_code == 200


async def test_require_jwt_rejects_headerless_and_tokenless(client, monkeypatch):
    monkeypatch.setattr("api.deps.REQUIRE_ACCESS_JWT", True)

    # No email header at all -> the dev shim is ignored, 401.
    assert (await client.get("/api/versions")).status_code == 401
    # Email header but no verifiable Access token -> 401 (fail closed).
    r = await client.get("/api/versions", headers={USER_HEADER: "b@example.com"})
    assert r.status_code == 401


async def test_version_quota_rejects_without_destroying(client, monkeypatch):
    monkeypatch.setattr("services.MAX_VERSIONS_PER_USER", 1)

    r = await client.post("/api/base", json={"data": SAMPLE, "label": "base"})
    assert r.status_code == 200

    # A second version (tailor) would exceed the cap -> 403, nothing destroyed.
    r = await client.post("/api/tailor", json={"data": SAMPLE, "label": "t", "jd_text": "jd"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "version_quota_reached"

    # The original base is untouched.
    assert len((await client.get("/api/versions")).json()) == 1


async def test_jd_and_message_length_caps(client):
    from api.schemas import MAX_JD_LEN, MAX_MESSAGE_LEN

    await client.post("/api/base", json={"data": SAMPLE, "label": "base"})
    r = await client.post(
        "/api/tailor", json={"data": SAMPLE, "jd_text": "x" * (MAX_JD_LEN + 1)}
    )
    assert r.status_code == 422
    r = await client.post("/api/chat/main", json={"message": "x" * (MAX_MESSAGE_LEN + 1)})
    assert r.status_code == 422
