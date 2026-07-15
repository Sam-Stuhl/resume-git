"""Multi-tenant guardrails: signup cap, version quota, input length caps.

Shares the dev identity shim and a SQLite file with test_api (same DATABASE_URL
so the module-level engine singleton is consistent regardless of import order).
"""

import json
import os
from pathlib import Path

import pytest

os.environ["DEV_USER_EMAIL"] = "a@example.com"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_api_pytest.db"
os.environ.setdefault("SESSION_SECRET", "test-session-secret-at-least-32bytes!")

import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402

SAMPLE = json.loads(
    (Path(__file__).resolve().parent.parent / "samples" / "sample_resume.json").read_text()
)


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


async def test_signup_cap_blocks_new_but_not_existing(client, monkeypatch):
    # The cap lives in auth.resolve_or_create_user (the OAuth/dev sign-in path).
    from fastapi import HTTPException
    from api import auth
    from db.session import SessionLocal

    monkeypatch.setattr("api.auth.MAX_USERS", 2)
    async with SessionLocal() as s:
        await auth.resolve_or_create_user(s, "one@example.com")
        await auth.resolve_or_create_user(s, "two@example.com")
        await s.commit()
        # A third *new* account is over the cap.
        with pytest.raises(HTTPException) as ei:
            await auth.resolve_or_create_user(s, "three@example.com")
        assert ei.value.status_code == 403 and "full" in ei.value.detail.lower()
        # Existing accounts still resolve even at the cap.
        u = await auth.resolve_or_create_user(s, "one@example.com")
        assert u.email == "one@example.com"


async def test_zero_cap_means_unlimited(client, monkeypatch):
    from api import auth
    from db.session import SessionLocal

    monkeypatch.setattr("api.auth.MAX_USERS", 0)
    async with SessionLocal() as s:
        for email in ("a@example.com", "b@example.com", "c@example.com", "d@example.com"):
            await auth.resolve_or_create_user(s, email)
        await s.commit()


async def test_version_quota_rejects_without_destroying(client, monkeypatch):
    monkeypatch.setattr("services.MAX_VERSIONS_PER_USER", 1)

    r = await client.post("/api/base", json={"data": SAMPLE, "label": "base"})
    assert r.status_code == 200

    # A second version (tailor) would exceed the cap -> 403, nothing destroyed.
    r = await client.post("/api/tailor", json={"data": SAMPLE, "label": "t", "jd_text": "jd"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "version_quota_reached"

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
