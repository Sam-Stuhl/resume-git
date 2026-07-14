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


# ── Credential detection / system-block ordering ──────────────────────────────
def test_is_oauth_token():
    assert agent.is_oauth_token("sk-ant-oat01-abc")
    assert not agent.is_oauth_token("sk-ant-api03-abc")


def test_system_blocks_oauth_puts_identity_first():
    blocks = agent._build_system(BASELINE, None, oauth=True)
    assert blocks[0]["text"] == agent.CLAUDE_CODE_IDENTITY
    assert "resume" in blocks[1]["text"].lower()

    api_blocks = agent._build_system(BASELINE, None, oauth=False)
    assert len(api_blocks) == 1
    assert agent.CLAUDE_CODE_IDENTITY not in api_blocks[0]["text"]


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
        history=[], user_message="[ASK] hello",
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
        history=[], user_message="[ASK] how do I look?",
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
        history=[], user_message="[TAILOR] SWE role",
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
        history=[], user_message="[TAILOR] role",
    ))
    kinds = [k for k, _ in events]
    assert "error" in kinds and kinds[-1] == "done"
    assert "proposal" not in kinds
