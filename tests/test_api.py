"""Integration tests for the API, using an in-memory-ish SQLite file and the
dev identity shim. Exercises base -> tailor -> diff -> restore and isolation.
"""

import copy
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
    from api.main import app  # imported after env is set
    from db.models import Base
    from db.session import engine

    # Reset schema between tests without unlinking the file (which would leave
    # the shared engine's pooled connection pointing at a deleted inode).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def test_base_tailor_diff_restore(client):
    r = await client.get("/health")
    assert r.status_code == 200

    r = await client.post("/api/base", json={"data": SAMPLE, "label": "base"})
    assert r.status_code == 200 and r.json()["is_base"] is True

    tail = copy.deepcopy(SAMPLE)
    tail["summary"] = "Tailored summary."
    r = await client.post("/api/tailor", json={"data": tail, "label": "t", "jd_text": "jd"})
    body = r.json()
    assert r.status_code == 200 and body["is_base"] is False and body["forked_from"] == 1

    r = await client.get("/api/versions")
    assert len(r.json()) == 2

    r = await client.get("/api/versions/1/diff/2")
    assert any("Summary" in s for s in r.json()["summary"])

    r = await client.post("/api/versions/1/restore")
    assert r.json()["version"] == 3

    r = await client.get("/api/versions/current")
    assert r.json()["version"] == 3


async def test_schema_rejection(client):
    r = await client.post("/api/base", json={"data": {"summary": "x"}, "label": "bad"})
    assert r.status_code == 422
    assert "problems" in r.json()["detail"]


async def test_tailor_requires_base(client):
    r = await client.post("/api/tailor", json={"data": SAMPLE, "label": "t"})
    assert r.status_code == 400


async def test_preview_pdf(client):
    from core.pdf import pdflatex_available

    # Missing personal -> 422 regardless of pdflatex.
    r = await client.post("/api/preview/pdf", json={"data": {"summary": "x"}})
    assert r.status_code == 422

    if not pdflatex_available():
        return
    # Full data compiles.
    r = await client.post("/api/preview/pdf", json={"data": SAMPLE})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    # Partial data (only a name) still renders — preview is lenient.
    r = await client.post("/api/preview/pdf", json={"data": {"personal": {"name": "A"}}})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


async def test_chat_streams_and_persists(client, monkeypatch):
    # A base + a configured credential are the preconditions for chat.
    await client.post("/api/base", json={"data": SAMPLE, "label": "base"})
    await client.put("/api/settings/api-key", json={"api_key": "sk-ant-api03-test"})

    proposal = {
        "data": {"personal": {"name": "A"}, "sections": []},
        "intent": "tailor", "summary": ["Tailored"], "diff": [], "section_changes": [],
    }

    async def fake_stream(**kwargs):
        assert kwargs["credential"] == "sk-ant-api03-test"
        yield ("delta", "Hello ")
        yield ("delta", "world")
        yield ("proposal", proposal)
        yield ("done", None)

    monkeypatch.setattr("core.agent.stream_chat", fake_stream)

    r = await client.post("/api/chat/main", json={"message": "[TAILOR] SWE"})
    assert r.status_code == 200
    frames = [
        json.loads(line[len("data: "):])
        for line in r.text.splitlines()
        if line.startswith("data: ")
    ]
    kinds = [f["type"] for f in frames]
    assert kinds == ["delta", "delta", "proposal", "done"]
    assert frames[2]["data"]["intent"] == "tailor"

    # History: user turn + assistant turn (with the proposal attached).
    hist = (await client.get("/api/chat/main")).json()
    assert [m["role"] for m in hist] == ["user", "assistant"]
    assert hist[0]["content"] == "[TAILOR] SWE"
    assert hist[1]["content"] == "Hello world"
    assert hist[1]["proposal"]["intent"] == "tailor"

    # A different thread is isolated; clear removes a thread's messages.
    assert (await client.get("/api/chat/other")).json() == []
    await client.delete("/api/chat/main")
    assert (await client.get("/api/chat/main")).json() == []


async def test_chat_requires_credential(client):
    await client.post("/api/base", json={"data": SAMPLE, "label": "base"})
    r = await client.post("/api/chat/main", json={"message": "[ASK] hi"})
    assert r.status_code == 400


async def test_skills_endpoint(client):
    r = await client.get("/api/skills")
    assert r.status_code == 200
    names = {s["name"] for s in r.json()}
    assert names == {"ask", "ats", "tailor", "base-update"}


async def test_chat_read_tool_streams_tool_step(client, monkeypatch):
    await client.post("/api/base", json={"data": SAMPLE, "label": "base"})
    await client.put("/api/settings/api-key", json={"api_key": "sk-ant-api03-test"})

    async def fake_stream(**kwargs):
        # The route must pass a working read_dispatch + skill through.
        assert "read_dispatch" in kwargs
        res = await kwargs["read_dispatch"]("list_versions", {})
        assert res["versions"][0]["version"] == 1
        yield ("tool_step", {"name": "list_versions", "summary": "list versions"})
        yield ("delta", "one version")
        yield ("done", None)

    monkeypatch.setattr("core.agent.stream_chat", fake_stream)
    r = await client.post("/api/chat/main", json={"message": "how many?", "skill": "ask"})
    frames = [json.loads(l[6:]) for l in r.text.splitlines() if l.startswith("data: ")]
    assert [f["type"] for f in frames] == ["tool_step", "delta", "done"]


async def test_import_bundle(client):
    bundle = {
        "current_version": 2,
        "versions": [
            {"version": 1, "label": "base", "is_base": True, "forked_from": None,
             "json_hash": "x", "data": SAMPLE},
            {"version": 2, "label": "t", "is_base": False, "forked_from": 1,
             "json_hash": "y", "data": SAMPLE},
        ],
    }
    # empty account -> imports
    r = await client.post("/api/import", json={**bundle, "replace": False})
    assert r.status_code == 200 and r.json()["imported"] == 2
    assert len((await client.get("/api/versions")).json()) == 2
    assert (await client.get("/api/versions/current")).json()["version"] == 2

    # non-empty without replace -> 409
    r = await client.post("/api/import", json={**bundle, "replace": False})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "account_not_empty"

    # replace -> clean re-import, still 2 (no duplicates)
    r = await client.post("/api/import", json={**bundle, "replace": True})
    assert r.status_code == 200
    assert len((await client.get("/api/versions")).json()) == 2
