"""Read-tool dispatch — pure over the DB, scoped per user."""
import json, os
from pathlib import Path
import pytest

os.environ["DEV_USER_EMAIL"] = "a@example.com"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_tools_pytest.db"

SAMPLE = json.loads((Path(__file__).resolve().parent.parent / "samples" / "sample_resume.json").read_text())


@pytest.fixture()
async def seeded():
    Path("./data").mkdir(exist_ok=True)
    from db.models import Base
    from db.session import SessionLocal, engine
    from db import repo
    from core.util import hash_json
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    async with SessionLocal() as s:
        u = await repo.get_or_create_user(s, "a@example.com")
        await repo.insert_version(s, u.id, version=1, data=SAMPLE, json_hash=hash_json(SAMPLE),
                                  label="Base", jd_text=None, is_base=True, forked_from=None)
        tail = {**SAMPLE, "summary": "Tailored."}
        await repo.insert_version(s, u.id, version=2, data=tail, json_hash=hash_json(tail),
                                  label="Notion Internship", jd_text="jd", is_base=False, forked_from=1)
        await repo.set_current_version(s, u.id, 2)
        await s.commit()
        yield s, u.id


def test_branch_of():
    from core.tools import branch_of
    assert branch_of("Base", True) == "main"
    assert branch_of("Notion Internship", False) == "notion-internship"


async def test_list_versions(seeded):
    from core.tools import dispatch_read
    s, uid = seeded
    out = await dispatch_read(s, uid, "list_versions", {})
    assert [v["version"] for v in out["versions"]] == [2, 1]
    head = next(v for v in out["versions"] if v["is_head"])
    assert head["version"] == 2 and head["branch"] == "notion-internship"


async def test_get_version_and_current(seeded):
    from core.tools import dispatch_read
    s, uid = seeded
    v1 = await dispatch_read(s, uid, "get_version", {"version": 1})
    assert v1["is_base"] and "personal" in v1["data"]
    cur = await dispatch_read(s, uid, "get_current", {})
    assert cur["version"] == 2


async def test_diff_versions(seeded):
    from core.tools import dispatch_read
    s, uid = seeded
    d = await dispatch_read(s, uid, "diff_versions", {"a": 1, "b": 2})
    assert any("Summary" in line for line in d["summary"])
    assert {ln["tag"] for ln in d["diff"]} & {"add", "del"}


async def test_unknown_tool_raises(seeded):
    from core.tools import dispatch_read
    s, uid = seeded
    with pytest.raises(ValueError):
        await dispatch_read(s, uid, "nope", {})
