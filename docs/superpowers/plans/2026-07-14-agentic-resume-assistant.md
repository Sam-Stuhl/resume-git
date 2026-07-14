# Agentic, Git-Aware Resume Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Resume Assistant into an agent that reads and acts on the version history (git-style), with the four intents restructured as `/`-invokable, self-describing skills.

**Architecture:** `core/agent.py:stream_chat` becomes a bounded tool loop over the streaming Messages API. Read tools (`core/tools.py`) execute server-side and chain within a turn; content writes surface a `propose_resume` proposal card and structural writes (`checkout`/`restore`) surface confirm cards — both end the turn (executed by the frontend via existing REST endpoints). The four intents move into a SKILL.md-shaped registry (`core/skills/`) with per-skill tool scoping; a `/` menu selects one.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), `anthropic` AsyncAnthropic streaming, React 18 + Vite + TS (frontend). No new dependencies.

## Global Constraints

- **No new dependencies** (backend or frontend). Reuse `anthropic>=0.40`, existing React/CodeMirror.
- **No co-author / "Generated with" trailer** on any commit.
- **OAuth-token path is load-bearing:** for `sk-ant-oat…` credentials keep `auth_token=`, `default_headers={"anthropic-beta": "oauth-2025-04-20"}`, and the Claude Code identity as the FIRST system block (`core/agent.py:CLAUDE_CODE_IDENTITY`).
- **Writes never execute inside the loop** — reads auto, writes surface as UI cards and end the turn.
- **Backend tests must stay green:** currently 29 (`.venv/bin/python -m pytest -q`). Activate with `source .venv/bin/activate`.
- **Frontend build must stay clean:** `cd frontend && npm run build` (strict `tsc -b`; `noUnusedLocals`/`noUnusedParameters` fail the build).
- **Persistence/replay rule:** persist only the user text + assistant final text + a `proposal`/`actions` blob; replay only **text** turns to the model (intermediate tool round-trips are ephemeral to the turn).

---

## File Structure

- **Create** `core/tools.py` — tool JSON schemas + read-tool dispatch (pure, `(session, user_id, name, args) -> dict`).
- **Create** `core/skills/__init__.py` — registry loader; `core/skills/{ask,ats,tailor,base-update}.md` — SKILL.md units.
- **Modify** `core/agent.py` — `stream_chat` → bounded tool loop; import schemas from `core/tools`; compose system prompt from skill + git-tools context.
- **Modify** `core/prompts.py` — add `build_chat_system(shared_preamble, skill_instructions, has_git_tools)`; keep the shared ATS-knowledge preamble; the four mode blocks move to `core/skills/*.md`.
- **Modify** `api/schemas.py` — `ChatSendIn.skill`; `SkillOut`.
- **Modify** `api/routes.py` — `GET /api/skills`; bind a read-dispatch to a stream-lifetime session; pass `skill` + `read_dispatch` to `stream_chat`.
- **Modify** `frontend/src/api.ts`, `types.ts` — `skills()`, `chatStream` `skill` + `onToolStep`/`onAction`; `Skill`/`ToolStep`/`AgentAction` types.
- **Modify** `frontend/src/components/ChatPanel.tsx` — `/` menu, tool-step lines, structural confirm cards.

---

### Task 1: Read tools + tool schemas (`core/tools.py`)

**Files:**
- Create: `core/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Produces:
  - `READ_TOOL_SCHEMAS: list[dict]`, `STRUCTURAL_TOOL_SCHEMAS: list[dict]`, `PROPOSE_RESUME_TOOL: dict`
  - `READ_TOOL_NAMES: set[str]`, `WRITE_TOOL_NAMES: set[str]` (= structural), `ALL_TOOL_SCHEMAS_BY_NAME: dict[str, dict]`
  - `async def dispatch_read(session, user_id: int, name: str, args: dict) -> dict`
  - `def branch_of(label: str | None, is_base: bool) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/test_tools.py -q`
Expected: FAIL (`ModuleNotFoundError: core.tools`).

- [ ] **Step 3: Write `core/tools.py`**

```python
"""Tools the Resume Assistant can use.

Read tools execute server-side inside the agent loop (auto). Write tools are
NOT executed here — their schemas are exposed to the model, but a write tool
call is surfaced to the UI as a confirm/proposal card and the turn ends. Read
dispatch is a pure async function over the DB, scoped to one user.
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from core.diff import diff_lines, summarize_changes
from core.sections import normalize
from db import repo


def branch_of(label: str | None, is_base: bool) -> str:
    """Mirror of frontend lib/git.ts:branchName — 'main' for base, else a slug."""
    if is_base:
        return "main"
    s = re.sub(r"[^a-z0-9]+", "-", (label or "").lower()).strip("-")[:40]
    return s or "tailored"


# ── Tool schemas exposed to the model ────────────────────────────────────────
READ_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "list_versions",
        "description": "List every resume version (commit) newest first, with branch, "
                       "lineage, and which one is HEAD. Use this to orient before acting.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_version",
        "description": "Fetch one version's full resume content and metadata by number.",
        "input_schema": {"type": "object",
                         "properties": {"version": {"type": "integer"}},
                         "required": ["version"]},
    },
    {
        "name": "diff_versions",
        "description": "Diff two versions (a vs b): a plain-English summary plus a line diff.",
        "input_schema": {"type": "object",
                         "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                         "required": ["a", "b"]},
    },
    {
        "name": "get_current",
        "description": "Get the current HEAD version (the one checked out right now).",
        "input_schema": {"type": "object", "properties": {}},
    },
]

STRUCTURAL_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "checkout",
        "description": "Move HEAD to an existing version (like `git checkout`). Requires the "
                       "user to confirm. Explain why before calling.",
        "input_schema": {"type": "object",
                         "properties": {"version": {"type": "integer"}},
                         "required": ["version"]},
    },
    {
        "name": "restore",
        "description": "Non-destructively restore a version's contents as a new commit "
                       "(like reverting to it). Requires the user to confirm.",
        "input_schema": {"type": "object",
                         "properties": {"version": {"type": "integer"}},
                         "required": ["version"]},
    },
]

PROPOSE_RESUME_TOOL: dict = {
    "name": "propose_resume",
    "description": ("Propose a complete updated resume for the user to review and apply "
                    "(a job TAILOR or a BASE UPDATE). Pass the ENTIRE {personal, sections} "
                    "document, not a fragment. Do not call for advice or audits."),
    "input_schema": {
        "type": "object",
        "properties": {
            "resume": {"type": "object", "description": "Complete updated resume document."},
            "intent": {"type": "string", "enum": ["tailor", "base_update"]},
        },
        "required": ["resume"],
    },
}

READ_TOOL_NAMES: set[str] = {t["name"] for t in READ_TOOL_SCHEMAS}
WRITE_TOOL_NAMES: set[str] = {t["name"] for t in STRUCTURAL_TOOL_SCHEMAS}
ALL_TOOL_SCHEMAS_BY_NAME: dict[str, dict] = {
    t["name"]: t for t in [*READ_TOOL_SCHEMAS, *STRUCTURAL_TOOL_SCHEMAS, PROPOSE_RESUME_TOOL]
}


# ── Read dispatch (executed server-side in the loop) ─────────────────────────
async def _version_row(session: AsyncSession, user_id: int, v: int) -> dict:
    row = await repo.get_version(session, user_id, v)
    if row is None:
        return {"error": f"v{v:04d} not found"}
    return {
        "version": row.version, "label": row.label, "is_base": row.is_base,
        "forked_from": row.forked_from, "branch": branch_of(row.label, row.is_base),
        "data": normalize(row.data),
    }


async def dispatch_read(session: AsyncSession, user_id: int, name: str, args: dict) -> dict:
    if name == "list_versions":
        cur = await repo.current_version(session, user_id)
        rows = await repo.list_versions(session, user_id)
        return {"versions": [{
            "version": r.version, "label": r.label, "is_base": r.is_base,
            "forked_from": r.forked_from, "branch": branch_of(r.label, r.is_base),
            "is_head": r.version == cur,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        } for r in rows]}
    if name == "get_version":
        return await _version_row(session, user_id, int(args["version"]))
    if name == "get_current":
        cur = await repo.current_version(session, user_id)
        if cur is None:
            return {"error": "no current version"}
        return await _version_row(session, user_id, cur)
    if name == "diff_versions":
        a = await repo.get_version(session, user_id, int(args["a"]))
        b = await repo.get_version(session, user_id, int(args["b"]))
        if a is None or b is None:
            return {"error": "version not found"}
        return {"summary": summarize_changes(a.data, b.data), "diff": diff_lines(a.data, b.data)}
    raise ValueError(f"unknown read tool {name!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tools.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add core/tools.py tests/test_tools.py
git commit -m "Add read tools + tool schemas for the agentic assistant"
```

---

### Task 2: Skill registry (`core/skills/`)

**Files:**
- Create: `core/skills/__init__.py`, `core/skills/ask.md`, `core/skills/ats.md`, `core/skills/tailor.md`, `core/skills/base-update.md`
- Modify: `core/prompts.py` (add `SHARED_PREAMBLE` accessor — see Step 3)
- Test: `tests/test_skills.py`

**Interfaces:**
- Produces:
  - `@dataclass Skill(name: str, description: str, allowed_tools: list[str], instructions: str)`
  - `REGISTRY: dict[str, Skill]`
  - `def get_skill(name: str | None) -> Skill | None`
  - `def skill_list() -> list[dict]`  (`[{name, description}]`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_skills.py
import pytest


def test_registry_has_four_skills():
    from core.skills import REGISTRY, skill_list
    assert set(REGISTRY) == {"ask", "ats", "tailor", "base-update"}
    for s in skill_list():
        assert s["name"] and s["description"] and len(s["description"]) < 120


def test_tool_scoping():
    from core.skills import REGISTRY
    from core.tools import READ_TOOL_NAMES
    # ask/ats are read-only; tailor/base-update may propose.
    assert set(REGISTRY["ats"].allowed_tools) <= READ_TOOL_NAMES
    assert "propose_resume" in REGISTRY["tailor"].allowed_tools
    assert "propose_resume" in REGISTRY["base-update"].allowed_tools
    assert "propose_resume" not in REGISTRY["ask"].allowed_tools


def test_allowed_tools_are_real():
    from core.skills import REGISTRY
    from core.tools import ALL_TOOL_SCHEMAS_BY_NAME
    for s in REGISTRY.values():
        for t in s.allowed_tools:
            assert t in ALL_TOOL_SCHEMAS_BY_NAME, f"{s.name} references unknown tool {t}"


def test_instructions_present():
    from core.skills import get_skill
    assert get_skill("tailor").instructions.strip()
    assert get_skill(None) is None
    assert get_skill("bogus") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_skills.py -q`
Expected: FAIL (`ModuleNotFoundError: core.skills`).

- [ ] **Step 3: Create the four SKILL.md files**

Each file is YAML frontmatter + an instructions body. Frontmatter is exact; the body is the corresponding mode block **moved verbatim** from `core/prompts.py:SESSION_PROMPT_TEMPLATE`.

`core/skills/ask.md`:
```markdown
---
name: ask
description: Get honest advice on your resume — nothing is changed.
allowed_tools: [list_versions, get_version, diff_versions, get_current]
---
You are giving honest, specific resume advice. Do NOT call propose_resume — you are not
committing a change, only advising. You may read history (list_versions/get_version/
diff_versions/get_current) to ground your answer. Answer in concise prose.
```

`core/skills/ats.md`:
```markdown
---
name: ats
description: Audit a version against a job description before you submit.
allowed_tools: [list_versions, get_version, diff_versions, get_current]
---
Run a structured ATS/AI-screener audit of the current (or named) version against the
pasted job description. Respond in plain English: keywords hit, keywords missing,
acronym alignment, weak bullets, a predicted score range, and the top 3 fixes. Do NOT
call propose_resume — this is an audit, not a change. Read versions as needed.
<MOVE HERE: the "ATS MODE" section body from core/prompts.py:SESSION_PROMPT_TEMPLATE
(the block describing the [ATS] audit output), verbatim.>
```

`core/skills/tailor.md`:
```markdown
---
name: tailor
description: Adapt your resume to a job and open it as a branch.
allowed_tools: [list_versions, get_version, diff_versions, get_current, propose_resume]
---
<MOVE HERE: the "TAILOR MODE — strict, presentation only, ATS-optimized" block from
core/prompts.py:SESSION_PROMPT_TEMPLATE starting at the line "When I send a [TAILOR]
message with a job description…" through the end of its "Required tailoring moves"
list, verbatim.>
When you have the tailored resume, call propose_resume with intent="tailor" and the
COMPLETE {personal, sections} document. Add one sentence explaining what you changed.
```

`core/skills/base-update.md`:
```markdown
---
name: base-update
description: Apply a real life change to your baseline resume.
allowed_tools: [list_versions, get_version, diff_versions, get_current, propose_resume]
---
<MOVE HERE: the "BASE UPDATE" block from core/prompts.py:SESSION_PROMPT_TEMPLATE
starting at "When I send a [BASE UPDATE] message…", verbatim, including its removal
guidance.>
When ready, call propose_resume with intent="base_update" and the COMPLETE updated
{personal, sections} document. Add one sentence explaining what you changed.
```

After moving, delete the now-duplicated mode blocks from `SESSION_PROMPT_TEMPLATE` **only if** they are no longer referenced (the copy-paste CLI still uses the full template — see Step 4). If the CLI path still needs them, leave `SESSION_PROMPT_TEMPLATE` intact and treat the SKILL.md bodies as the canonical copies for the chat path.

- [ ] **Step 4: Write `core/skills/__init__.py`**

```python
"""Skill registry — one self-describing unit per intent, loaded from SKILL.md files.

Each file is YAML-ish frontmatter (name/description/allowed_tools) + an instructions
body. Kept SKILL.md-shaped so it could port to the real Skills system later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    allowed_tools: list[str]
    instructions: str


def _parse(md: str) -> Skill:
    assert md.startswith("---"), "SKILL.md must start with frontmatter"
    _, front, body = md.split("---", 2)
    meta: dict = {}
    for line in front.strip().splitlines():
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if key == "allowed_tools":
            val = [t.strip() for t in val.strip("[]").split(",") if t.strip()]
        meta[key] = val
    return Skill(name=meta["name"], description=meta["description"],
                 allowed_tools=meta["allowed_tools"], instructions=body.strip())


REGISTRY: dict[str, Skill] = {
    (s := _parse(p.read_text())).name: s for p in sorted(_DIR.glob("*.md"))
}


def get_skill(name: str | None) -> Skill | None:
    return REGISTRY.get(name) if name else None


def skill_list() -> list[dict]:
    return [{"name": s.name, "description": s.description} for s in REGISTRY.values()]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_skills.py -q`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add core/skills tests/test_skills.py core/prompts.py
git commit -m "Add skill registry (SKILL.md) for the four resume intents"
```

---

### Task 3: Agent tool loop (`core/agent.py`)

**Files:**
- Modify: `core/agent.py` (rewrite `stream_chat` into a loop; drop the local `PROPOSE_RESUME_TOOL` in favor of `core.tools`)
- Modify: `core/prompts.py` (add `build_chat_system`)
- Test: `tests/test_agent.py` (extend)

**Interfaces:**
- Consumes: `core.tools.{READ_TOOL_NAMES, WRITE_TOOL_NAMES, ALL_TOOL_SCHEMAS_BY_NAME}`, `core.skills.get_skill`.
- Produces (new signature):
  ```python
  async def stream_chat(*, credential, model, baseline, history, user_message,
                        current_data=None, skill=None, read_dispatch) -> AsyncIterator[tuple[str, object]]
  ```
  `read_dispatch: Callable[[str, dict], Awaitable[dict]]`. Yields `("delta", str)`,
  `("tool_step", {"name","summary"})`, `("proposal", {...})`, `("action", {"tool","args","summary"})`,
  `("error", str)`, terminal `("done", None)`.

- [ ] **Step 1: Write the failing tests (extend `tests/test_agent.py`)**

Add a fake multi-step stream helper and these tests. The existing fakes (`_Delta`, `_ToolBlock`, `_TextBlock`, `_Final`, `_make_client`) stay; add a client that returns a **scripted sequence** of finals so the loop can iterate.

```python
# append to tests/test_agent.py

class _ToolUse:
    def __init__(self, name, inp, _id="t1"):
        self.type = "tool_use"; self.name = name; self.input = inp; self.id = _id


def _make_seq_client(scripts, captured):
    """scripts: list of (deltas, final_blocks) played one per model call."""
    calls = {"i": 0}
    class _Stream:
        def __init__(self, deltas, final): self._d = deltas; self._f = final
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def __aiter__(self):
            for d in self._d: yield _Event(d)
        async def get_final_message(self):
            class F: content = self._f
            return F()
    class _Msgs:
        def stream(self, **kw):
            captured.setdefault("tools", []).append([t["name"] for t in kw["tools"]])
            i = calls["i"]; calls["i"] += 1
            d, f = scripts[i]
            return _Stream(d, f)
    class _Client:
        def __init__(self, **kw): self.messages = _Msgs()
    return _Client


async def _fake_dispatch(name, args):
    return {"ok": name, "args": args}


async def test_loop_executes_read_then_answers(monkeypatch):
    import anthropic
    captured = {}
    scripts = [
        (["Let me check. "], [_TextBlock("Let me check. "), _ToolUse("list_versions", {})]),
        (["You have 2 versions."], [_TextBlock("You have 2 versions.")]),
    ]
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _make_seq_client(scripts, captured))
    events = await _collect(agent.stream_chat(
        credential="sk-ant-api03-x", model=None, baseline=BASELINE, history=[],
        user_message="how many versions?", read_dispatch=_fake_dispatch))
    kinds = [k for k, _ in events]
    assert "tool_step" in kinds and kinds[-1] == "done"
    assert "proposal" not in kinds and "action" not in kinds


async def test_structural_write_emits_action(monkeypatch):
    import anthropic
    captured = {}
    scripts = [(["Checking out."], [_TextBlock("Checking out."), _ToolUse("checkout", {"version": 5})])]
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _make_seq_client(scripts, captured))
    events = await _collect(agent.stream_chat(
        credential="sk-ant-api03-x", model=None, baseline=BASELINE, history=[],
        user_message="go to v5", read_dispatch=_fake_dispatch))
    kinds = [k for k, _ in events]
    assert "action" in kinds and kinds[-1] == "done"
    action = next(p for k, p in events if k == "action")
    assert action["tool"] == "checkout" and action["args"]["version"] == 5


async def test_ats_skill_is_read_only(monkeypatch):
    import anthropic
    captured = {}
    scripts = [(["Audit."], [_TextBlock("Audit.")])]
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _make_seq_client(scripts, captured))
    await _collect(agent.stream_chat(
        credential="sk-ant-api03-x", model=None, baseline=BASELINE, history=[],
        user_message="[audit]", skill="ats", read_dispatch=_fake_dispatch))
    offered = set(captured["tools"][0])
    assert "propose_resume" not in offered and "checkout" not in offered


async def test_max_steps_terminates(monkeypatch):
    import anthropic
    captured = {}
    # Always calls a read tool -> would loop forever without the cap.
    loop_script = (["."], [_TextBlock("."), _ToolUse("list_versions", {})])
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _make_seq_client([loop_script] * 20, captured))
    events = await _collect(agent.stream_chat(
        credential="sk-ant-api03-x", model=None, baseline=BASELINE, history=[],
        user_message="loop", read_dispatch=_fake_dispatch))
    assert events[-1] == ("done", None)
    assert len(captured["tools"]) <= agent.MAX_STEPS
```

Update the existing `test_tailor_turn_emits_validated_proposal` / `test_ask_turn_streams_text_only` / `test_credential_routes_to_right_client` / `test_invalid_proposal_becomes_error` calls to pass `read_dispatch=_fake_dispatch` (new required kwarg).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent.py -q`
Expected: FAIL (`stream_chat() missing 1 required keyword-only argument: 'read_dispatch'` / new tests error).

- [ ] **Step 3: Add `build_chat_system` to `core/prompts.py`**

```python
GIT_TOOLS_CONTEXT = """\

─────────────────────────
YOU CAN OPERATE THE RESUME REPO (git-style)

You have tools to read the version history and act on it:
- Read freely to ground yourself: list_versions, get_version, diff_versions, get_current.
- To change resume CONTENT, call propose_resume (the user reviews a diff and applies it).
- To move HEAD or revert, call checkout / restore — these ask the user to confirm, so
  explain why first, then call the tool as your final action.
Never claim you performed a write; you propose or request it and the user confirms.
─────────────────────────
"""


def build_chat_system(baseline: dict, skill_instructions: str | None) -> str:
    """Shared advisor preamble + git-tools context + (skill instructions or advisor default)."""
    base = build_session_prompt(baseline)  # reuse identity + ATS knowledge + baseline
    focus = skill_instructions or (
        "\nYou are in free-chat advisor mode. Answer questions, read history to ground "
        "yourself, and offer to tailor, update the baseline, audit (ATS), checkout, or "
        "restore when useful."
    )
    return base + GIT_TOOLS_CONTEXT + "\n" + focus
```

- [ ] **Step 4: Rewrite `stream_chat` in `core/agent.py`**

Replace the body from the `PROPOSE_RESUME_TOOL` definition and `stream_chat` down. Keep `CLAUDE_CODE_IDENTITY`, `OAUTH_BETA`, `is_oauth_token`, `_build_system` (retitle its prompt source), `_proposal_from`.

```python
from core import tools as agent_tools
from core.skills import get_skill

MAX_STEPS = 8


def _tools_for(skill_name: str | None) -> list[dict]:
    skill = get_skill(skill_name)
    if skill is None:  # advisor default: everything
        return [agent_tools.ALL_TOOL_SCHEMAS_BY_NAME[n]
                for n in [*agent_tools.READ_TOOL_NAMES, *agent_tools.WRITE_TOOL_NAMES, "propose_resume"]]
    return [agent_tools.ALL_TOOL_SCHEMAS_BY_NAME[n] for n in skill.allowed_tools]


def _summarize_action(name: str, args: dict) -> str:
    if name == "checkout":
        return f"Checkout v{int(args.get('version', 0)):04d}"
    if name == "restore":
        return f"Restore v{int(args.get('version', 0)):04d} as a new commit"
    return name


async def stream_chat(*, credential, model, baseline, history, user_message,
                      current_data=None, skill=None, read_dispatch):
    try:
        import anthropic
    except ImportError:
        yield ("error", "The anthropic SDK is not installed on the server."); yield ("done", None); return

    skill_obj = get_skill(skill)
    system_text = build_chat_system(baseline, skill_obj.instructions if skill_obj else None)
    if current_data is not None and normalize(current_data) != normalize(baseline):
        system_text += ("\n\nCURRENTLY VIEWED VERSION (treat as the working resume this turn):\n"
                        + json.dumps(current_data, indent=2, ensure_ascii=False))

    oauth = is_oauth_token(credential)
    system = ([{"type": "text", "text": CLAUDE_CODE_IDENTITY}] if oauth else []) + \
             [{"type": "text", "text": system_text}]
    if oauth:
        client = anthropic.AsyncAnthropic(auth_token=credential.strip(),
                                          default_headers={"anthropic-beta": OAUTH_BETA})
    else:
        client = anthropic.AsyncAnthropic(api_key=credential.strip())

    tool_schemas = _tools_for(skill)
    messages = list(history) + [{"role": "user", "content": user_message}]
    current = current_data if current_data is not None else baseline

    for _ in range(MAX_STEPS):
        try:
            async with client.messages.stream(model=model or DEFAULT_MODEL, max_tokens=8000,
                                              system=system, messages=messages, tools=tool_schemas) as stream:
                async for event in stream:
                    if event.type == "content_block_delta" and getattr(event.delta, "type", None) == "text_delta":
                        yield ("delta", event.delta.text)
                final = await stream.get_final_message()
        except Exception as exc:  # noqa: BLE001
            yield ("error", f"Claude request failed: {exc}"); yield ("done", None); return

        tool_uses = [b for b in final.content if getattr(b, "type", None) == "tool_use"]
        reads = [b for b in tool_uses if b.name in agent_tools.READ_TOOL_NAMES]
        writes = [b for b in tool_uses if b.name in agent_tools.WRITE_TOOL_NAMES or b.name == "propose_resume"]

        if reads and not writes:
            tool_results = []
            for b in reads:
                try:
                    result = await read_dispatch(b.name, dict(b.input))
                except Exception as exc:  # noqa: BLE001
                    result = {"error": str(exc)}
                yield ("tool_step", {"name": b.name, "summary": _read_summary(b.name, b.input)})
                tool_results.append({"type": "tool_result", "tool_use_id": b.id,
                                     "content": json.dumps(result)})
            messages.append({"role": "assistant", "content": [
                {"type": "tool_use", "id": b.id, "name": b.name, "input": dict(b.input)} for b in reads]})
            messages.append({"role": "user", "content": tool_results})
            continue

        if writes:
            for b in writes:
                if b.name == "propose_resume":
                    try:
                        yield ("proposal", _proposal_from(dict(b.input), current))
                    except schema.SchemaError as exc:
                        yield ("error", f"Claude proposed an invalid resume: {exc}")
                else:
                    yield ("action", {"tool": b.name, "args": dict(b.input),
                                      "summary": _summarize_action(b.name, dict(b.input))})
            break
        break  # end_turn

    yield ("done", None)


def _read_summary(name: str, args) -> str:
    if name == "diff_versions":
        return f"diff v{int(args.get('a',0)):04d}…v{int(args.get('b',0)):04d}"
    if name == "get_version":
        return f"read v{int(args.get('version',0)):04d}"
    if name == "get_current":
        return "read HEAD"
    return "list versions"
```

Delete the old module-level `PROPOSE_RESUME_TOOL` in `core/agent.py` (now `agent_tools.PROPOSE_RESUME_TOOL`). Keep `_proposal_from` (it uses `agent_tools`? no — it uses `schema`, `diff`, `section_changes`; unchanged).

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_agent.py tests/test_tools.py tests/test_skills.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/agent.py core/prompts.py tests/test_agent.py
git commit -m "Rewrite the assistant as a bounded git-aware tool loop"
```

---

### Task 4: API wiring (`api/`)

**Files:**
- Modify: `api/schemas.py` (add `SkillOut`, `ChatSendIn.skill`)
- Modify: `api/routes.py` (`GET /api/skills`; stream-lifetime session + `read_dispatch`; pass `skill`)
- Test: `tests/test_api.py` (extend)

**Interfaces:**
- Consumes: `core.skills.skill_list`, `core.tools.dispatch_read`, `core.agent.stream_chat` (new signature).
- Produces: `GET /api/skills -> list[SkillOut]`; chat SSE now also emits `tool_step`/`action` frames.

- [ ] **Step 1: Write the failing tests (extend `tests/test_api.py`)**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_api.py -q -k "skills or tool_step"`
Expected: FAIL (`GET /api/skills` 404; `read_dispatch` not passed).

- [ ] **Step 3: Update `api/schemas.py`**

```python
class SkillOut(BaseModel):
    name: str
    description: str


class ChatSendIn(BaseModel):
    message: str
    model: str | None = None
    current_data: dict | None = None
    skill: str | None = None
```

- [ ] **Step 4: Update `api/routes.py`**

Add the endpoint (near the chat routes) and thread `read_dispatch` + `skill` through the SSE generator. The generator opens one `SessionLocal` for the stream's lifetime and binds `read_dispatch` to it.

```python
from core import skills as skills_registry
from core import tools as agent_tools

@router.get("/skills", response_model=list[schemas.SkillOut])
async def list_skills(user: User = Depends(get_current_user)):
    return skills_registry.skill_list()
```

Replace the `gen()` in `chat_send`:

```python
    uid = user.id

    async def gen():
        parts: list[str] = []
        proposal = None
        actions: list[dict] = []
        async with SessionLocal() as s2:
            async def read_dispatch(name: str, args: dict) -> dict:
                return await agent_tools.dispatch_read(s2, uid, name, args)
            async for kind, payload in agent.stream_chat(
                credential=key, model=model, baseline=baseline, history=history,
                user_message=body.message, current_data=body.current_data,
                skill=body.skill, read_dispatch=read_dispatch,
            ):
                if kind == "delta":
                    parts.append(payload)
                elif kind == "proposal":
                    proposal = payload
                elif kind == "action":
                    actions.append(payload)
                yield f"data: {json.dumps({'type': kind, 'data': payload})}\n\n"
            await repo.add_message(s2, uid, thread_key, "assistant", "".join(parts),
                                   proposal=proposal or ({"actions": actions} if actions else None))
            await s2.commit()
```

(`body.skill` is validated implicitly — `get_skill` returns `None` for unknown names, so a bad skill just falls back to advisor mode.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_api.py -q`
Expected: PASS (including the two new tests + existing chat tests).

- [ ] **Step 6: Full backend suite + commit**

```bash
python -m pytest -q   # expect all green (was 29, now ~40)
git add api/schemas.py api/routes.py tests/test_api.py
git commit -m "Wire skills endpoint + read-dispatch into the chat route"
```

---

### Task 5: Frontend API + types

**Files:**
- Modify: `frontend/src/types.ts`, `frontend/src/api.ts`

**Interfaces:**
- Produces: `api.skills()`, `chatStream` gains `skill` in the body and `onToolStep`/`onAction` handlers; types `Skill`, `ToolStep`, `AgentAction`.

- [ ] **Step 1: Add types (`frontend/src/types.ts`)**

```ts
export interface Skill { name: string; description: string; }
export interface ToolStep { name: string; summary: string; }
export interface AgentAction { tool: "checkout" | "restore"; args: Record<string, number>; summary: string; }
```

- [ ] **Step 2: Extend the API client (`frontend/src/api.ts`)**

Add to `ChatStreamHandlers`:
```ts
export interface ChatStreamHandlers {
  onDelta: (text: string) => void;
  onProposal: (proposal: ChatProposal) => void;
  onToolStep: (step: ToolStep) => void;
  onAction: (action: AgentAction) => void;
  onError: (message: string) => void;
  onDone: () => void;
}
```
Add `skills` + extend the frame dispatch + `chatStream` body:
```ts
  skills: () => req<Skill[]>("/api/skills"),
```
In `chatStream`, widen the body type to `{ message: string; model?: string; current_data?: unknown; skill?: string }` and add to the dispatch switch:
```ts
        else if (evt.type === "tool_step") h.onToolStep(evt.data as ToolStep);
        else if (evt.type === "action") h.onAction(evt.data as AgentAction);
```
Import the new types at the top (`Skill, ToolStep, AgentAction`).

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: clean (tsc passes). It will still pass because `ChatPanel` (Task 6) is updated next — if tsc flags a missing handler in `ChatPanel`, that is fixed in Task 6; to keep this task independently green, add the two handlers as no-ops in `ChatPanel`'s existing `chatStream` call in THIS step:
```ts
onToolStep: () => {}, onAction: () => {},
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts frontend/src/components/ChatPanel.tsx
git commit -m "Frontend: skills API + tool_step/action stream handlers"
```

---

### Task 6: Frontend ChatPanel — `/` menu, tool steps, confirm cards

**Files:**
- Modify: `frontend/src/components/ChatPanel.tsx`, `frontend/src/styles.css`

**Interfaces:**
- Consumes: `api.skills`, `chatStream` handlers, `AgentAction`, `ToolStep`; `api.setCurrent`, `api.restore` for confirms.

- [ ] **Step 1: `/` skill menu**

Add state and load skills once:
```ts
const [skills, setSkills] = useState<Skill[]>([]);
const [activeSkill, setActiveSkill] = useState<string | null>(null);
useEffect(() => { api.skills().then(setSkills).catch(() => {}); }, []);
```
When `input` starts with `/`, render a menu above the input filtering `skills` by the text after `/`; clicking a skill sets `activeSkill` (shown as a chip on the input) and clears the leading token. Show each skill's `name` + `description`. Include the active skill in the send body: `{ message, model, current_data, skill: activeSkill ?? undefined }`. Reset `activeSkill` after a send.

- [ ] **Step 2: Tool-step + action state during streaming**

Accumulate live steps/actions alongside `liveText`:
```ts
const [liveSteps, setLiveSteps] = useState<ToolStep[]>([]);
const [liveActions, setLiveActions] = useState<AgentAction[]>([]);
```
In the `chatStream` handlers: `onToolStep: s => setLiveSteps(v => [...v, s])`, `onAction: a => setLiveActions(v => [...v, a])`. On finalize, fold `steps`/`actions` into the pushed assistant `ChatMessage` (extend the local message shape to carry `steps?: ToolStep[]` and `actions?: AgentAction[]`). Reset live arrays on send and after finalize.

- [ ] **Step 3: Render tool steps + confirm cards**

In the assistant `Bubble`, render `steps` as muted rows: `▸ {summary}`. Render each `action` as an `ActionCard`:
```tsx
function ActionCard({ action, onDone }: { action: AgentAction; onDone: (msg: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState("");
  const run = async () => {
    setBusy(true);
    try {
      if (action.tool === "checkout") { await api.setCurrent(action.args.version); onDone(`Checked out v${action.args.version}`); }
      else { const r = await api.restore(action.args.version); onDone(`Restored as v${r.version}`); }
      setDone("done");
    } finally { setBusy(false); }
  };
  if (done) return <div className="action-card done">✓ {action.summary}</div>;
  return (
    <div className="action-card">
      <span>{action.summary}?</span>
      <div className="row">
        <button className="green" disabled={busy} onClick={run}>Confirm</button>
        <button disabled={busy} onClick={() => setDone("cancelled")}>Cancel</button>
      </div>
    </div>
  );
}
```
`onDone` triggers `onCommitted`-style refresh so the rest of the app (HEAD badge, rail) updates — thread the existing `onCommitted`/refresh callback into `ChatPanel` if not already present (add an `onRepoChanged: () => void` prop supplied by `Workbench` = `() => onCommitted(currentHeadVersion)`; simplest: reuse `onCreateBranch`'s parent refresh by adding a lightweight `onRefresh` prop wired to `App.refresh`). On reload, persisted `actions` render as static summary lines (no Confirm button).

- [ ] **Step 4: Styles (`frontend/src/styles.css`, end of file)**

```css
.chat-skill-menu { border: 1px solid var(--border); border-radius: var(--radius); background: var(--panel); margin: 0 12px 6px; max-height: 220px; overflow-y: auto; }
.chat-skill-menu button { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; width: 100%; border: none; border-radius: 0; padding: 8px 10px; text-align: left; }
.chat-skill-menu button:hover { background: var(--panel-2); }
.chat-skill-menu .sk-name { font-family: var(--mono); color: var(--accent); }
.chat-skill-menu .sk-desc { color: var(--muted); font-size: 11px; }
.skill-chip { font-family: var(--mono); font-size: 11px; color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, transparent); border: 1px solid color-mix(in srgb, var(--accent) 35%, transparent); border-radius: 999px; padding: 1px 8px; }
.tool-step { color: var(--muted); font-size: 12px; font-family: var(--mono); padding: 1px 0; }
.action-card { border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 8px 10px; display: flex; flex-direction: column; gap: 6px; background: var(--panel); }
.action-card.done { color: var(--commit); }
```

- [ ] **Step 5: Build + manual verification**

Run: `cd frontend && npm run build` (expect clean).
Then rebuild is served by the running dev server (`data/r1.db`, `DEV_USER_EMAIL=dev@example.com`, port 8091). In a browser:
1. Type `/` → the four skills appear with descriptions; pick `/ats`.
2. Free chat: "what changed between my notion branch and main?" → `▸ list versions`, `▸ diff …` steps → grounded answer.
3. "check out my base resume from before NJIT" → a **Checkout vNNNN?** card → Confirm → HEAD badge + rail update.
4. `/tailor <JD>` → proposal card → Create branch.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ChatPanel.tsx frontend/src/styles.css
git commit -m "ChatPanel: / skill menu, tool-step lines, structural confirm cards"
```

---

## Self-Review

- **Spec coverage:** agent loop → Task 3; read tools → Task 1; skills registry + descriptions + tool scoping → Task 2; `GET /api/skills` + `skill` param + `tool_step`/`action` events → Task 4; `/` menu + tool-step lines + confirm cards → Task 6; content proposal unchanged → reused in Task 3/6; per-branch persistence of actions → Task 4 (`{"actions": [...]}` blob). Covered.
- **Type consistency:** `read_dispatch(name, args) -> dict` used identically in Tasks 1/3/4; event tuple kinds (`delta`/`tool_step`/`proposal`/`action`/`error`/`done`) match across agent (Task 3), route (Task 4), and frontend handlers (Tasks 5/6); `AgentAction.tool ∈ {checkout, restore}` matches `WRITE_TOOL_NAMES` (Task 1).
- **Placeholder note:** the only intentional "move this content" markers are the SKILL.md instruction bodies (Task 2 Step 3), which relocate exact, delimited blocks from `core/prompts.py:SESSION_PROMPT_TEMPLATE` — not invented content.

## Execution Handoff — deferred

Do not start execution yet. This plan targets branch `resume-copilot-chat` (unmerged). Confirm with the user whether to (a) execute here, (b) execute after merging the current assistant to `main`, or (c) branch fresh.
```
