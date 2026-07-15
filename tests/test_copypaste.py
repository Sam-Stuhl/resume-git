"""Keyless copy-paste assistant: prompt assembly + paste-back preview."""

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


async def test_copy_prompt_requires_base_then_injects_jd(client):
    # No base yet -> 400 (the wizard's onboarding path handles the pre-base case).
    r = await client.post("/api/prompts/copy", json={"intent": "tailor", "jd_text": "JD"})
    assert r.status_code == 400

    await client.post("/api/base", json={"data": SAMPLE, "label": "base"})
    r = await client.post(
        "/api/prompts/copy", json={"intent": "tailor", "jd_text": "Backend role at Acme"}
    )
    assert r.status_code == 200
    prompt = r.json()["prompt"]
    assert "[TAILOR]" in prompt and "Backend role at Acme" in prompt


async def test_copy_prompt_rejects_unknown_intent(client):
    await client.post("/api/base", json={"data": SAMPLE, "label": "base"})
    r = await client.post("/api/prompts/copy", json={"intent": "nonsense"})
    assert r.status_code == 422


async def test_paste_preview_bootstrap_from_empty(client):
    # Keyless onboarding bootstrap: no base yet, diff is against an empty resume.
    r = await client.post(
        "/api/paste/preview", json={"text": json.dumps(SAMPLE), "intent": "base-update"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["personal"]["name"] == SAMPLE["personal"]["name"]
    assert isinstance(body["diff"], list) and isinstance(body["summary"], list)

    # The returned data commits cleanly as a base.
    r = await client.post("/api/base", json={"data": body["data"], "label": "base"})
    assert r.status_code == 200


async def test_paste_preview_strips_markdown_fences(client):
    fenced = "Here you go:\n```json\n" + json.dumps(SAMPLE) + "\n```\nHope that helps!"
    r = await client.post("/api/paste/preview", json={"text": fenced, "intent": "tailor"})
    assert r.status_code == 200
    assert r.json()["data"]["personal"]["name"] == SAMPLE["personal"]["name"]


async def test_paste_preview_rejects_garbage_and_invalid(client):
    r = await client.post("/api/paste/preview", json={"text": "no json here", "intent": "tailor"})
    assert r.status_code == 422
    r = await client.post(
        "/api/paste/preview", json={"text": json.dumps({"personal": {}}), "intent": "base-update"}
    )
    assert r.status_code == 422
    assert "problems" in r.json()["detail"]
