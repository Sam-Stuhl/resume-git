"""Unit tests for the streaming Resume Copilot agent (core/agent.py).

The Anthropic SDK is faked so no network/key is needed: we monkeypatch
``anthropic.AsyncAnthropic`` with a client that records its init kwargs and
replays a scripted stream + final message.
"""

from __future__ import annotations

import anthropic
import pytest

from core import agent

VALID_RESUME = {"personal": {"name": "Jordan Sample"}, "sections": [
    {"type": "text", "title": "Summary", "text": "Engineer."},
]}
BASELINE = {"personal": {"name": "Jordan Sample"}, "sections": []}


# ── Fake SDK plumbing ─────────────────────────────────────────────────────────
class _Delta:
    def __init__(self, text: str):
        self.type = "text_delta"
        self.text = text


class _Event:
    def __init__(self, text: str):
        self.type = "content_block_delta"
        self.delta = _Delta(text)


class _ToolBlock:
    def __init__(self, name: str, inp: dict):
        self.type = "tool_use"
        self.name = name
        self.input = inp


class _TextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _Final:
    def __init__(self, blocks: list):
        self.content = blocks


class _FakeStream:
    def __init__(self, deltas: list[str], final: _Final):
        self._deltas = deltas
        self._final = final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def __aiter__(self):
        for d in self._deltas:
            yield _Event(d)

    async def get_final_message(self):
        return self._final


def _make_client(deltas: list[str], final: _Final, captured: dict):
    class _FakeMessages:
        def stream(self, **kwargs):
            captured["stream_kwargs"] = kwargs
            return _FakeStream(deltas, final)

    class _FakeClient:
        def __init__(self, **kwargs):
            captured["init_kwargs"] = kwargs
            self.messages = _FakeMessages()

    return _FakeClient


async def _collect(gen):
    return [item async for item in gen]


async def _fake_dispatch(name, args):
    return {"ok": name, "args": args}


# ── Credential detection / system-block ordering ──────────────────────────────
def test_is_oauth_token():
    assert agent.is_oauth_token("sk-ant-oat01-abc")
    assert not agent.is_oauth_token("sk-ant-api03-abc")


async def test_system_blocks_oauth_puts_identity_first(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        anthropic, "AsyncAnthropic",
        _make_client(["hi"], _Final([_TextBlock("hi")]), captured),
    )
    await _collect(agent.stream_chat(
        credential="sk-ant-oat01-x", model=None, baseline=BASELINE,
        history=[], user_message="[ASK] hi", read_dispatch=_fake_dispatch,
    ))
    system = captured["stream_kwargs"]["system"]
    assert system[0]["text"] == agent.CLAUDE_CODE_IDENTITY
    assert "resume" in system[1]["text"].lower()

    captured2: dict = {}
    monkeypatch.setattr(
        anthropic, "AsyncAnthropic",
        _make_client(["hi"], _Final([_TextBlock("hi")]), captured2),
    )
    await _collect(agent.stream_chat(
        credential="sk-ant-api03-x", model=None, baseline=BASELINE,
        history=[], user_message="[ASK] hi", read_dispatch=_fake_dispatch,
    ))
    system2 = captured2["stream_kwargs"]["system"]
    assert len(system2) == 1
    assert agent.CLAUDE_CODE_IDENTITY not in system2[0]["text"]


@pytest.mark.parametrize(
    "cred, expect_key",
    [("sk-ant-oat01-x", "auth_token"), ("sk-ant-api03-x", "api_key")],
)
async def test_credential_routes_to_right_client(monkeypatch, cred, expect_key):
    captured: dict = {}
    monkeypatch.setattr(
        anthropic, "AsyncAnthropic",
        _make_client(["hi"], _Final([_TextBlock("hi")]), captured),
    )
    await _collect(agent.stream_chat(
        credential=cred, model="claude-sonnet-5", baseline=BASELINE,
        history=[], user_message="[ASK] hello", read_dispatch=_fake_dispatch,
    ))
    init = captured["init_kwargs"]
    assert expect_key in init
    if expect_key == "auth_token":
        assert init["default_headers"]["anthropic-beta"] == agent.OAUTH_BETA


# ── Streaming behavior ────────────────────────────────────────────────────────
async def test_ask_turn_streams_text_only(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        anthropic, "AsyncAnthropic",
        _make_client(["Hi ", "there"], _Final([_TextBlock("Hi there")]), captured),
    )
    events = await _collect(agent.stream_chat(
        credential="sk-ant-api03-x", model=None, baseline=BASELINE,
        history=[], user_message="[ASK] how do I look?", read_dispatch=_fake_dispatch,
    ))
    kinds = [k for k, _ in events]
    assert kinds == ["delta", "delta", "done"]
    assert "".join(p for k, p in events if k == "delta") == "Hi there"


async def test_tailor_turn_emits_validated_proposal(monkeypatch):
    captured: dict = {}
    final = _Final([
        _TextBlock("Here's a tailored version."),
        _ToolBlock("propose_resume", {"resume": VALID_RESUME, "intent": "tailor"}),
    ])
    monkeypatch.setattr(
        anthropic, "AsyncAnthropic", _make_client(["ok"], final, captured),
    )
    events = await _collect(agent.stream_chat(
        credential="sk-ant-api03-x", model=None, baseline=BASELINE,
        history=[], user_message="[TAILOR] SWE role", read_dispatch=_fake_dispatch,
    ))
    kinds = [k for k, _ in events]
    assert kinds == ["delta", "proposal", "done"]
    proposal = next(p for k, p in events if k == "proposal")
    assert proposal["intent"] == "tailor"
    assert proposal["data"]["personal"]["name"] == "Jordan Sample"
    assert "diff" in proposal and "section_changes" in proposal


async def test_invalid_proposal_becomes_error(monkeypatch):
    captured: dict = {}
    final = _Final([_ToolBlock("propose_resume", {"resume": {"sections": []}})])  # no name
    monkeypatch.setattr(
        anthropic, "AsyncAnthropic", _make_client(["x"], final, captured),
    )
    events = await _collect(agent.stream_chat(
        credential="sk-ant-api03-x", model=None, baseline=BASELINE,
        history=[], user_message="[TAILOR] role", read_dispatch=_fake_dispatch,
    ))
    kinds = [k for k, _ in events]
    assert "error" in kinds and kinds[-1] == "done"
    assert "proposal" not in kinds


# ── Tool loop (multi-step reads / structural writes / skill scoping / cap) ────
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
