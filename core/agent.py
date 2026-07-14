"""Resume Copilot — the streaming, tool-using chat agent.

Wraps the existing curated resume-advisor system prompt (``core.prompts``) in a
streaming Claude conversation. Unlike the single-shot ``core.ai`` path this is
async (``anthropic.AsyncAnthropic``) and yields normalized events so the API can
forward them as Server-Sent Events.

Two credential kinds are supported, auto-detected from the token prefix:

* **API key** (``sk-ant-api…``) → normal ``x-api-key`` auth, one system block.
* **Claude Code OAuth token** (``sk-ant-oat…``) → ``Authorization: Bearer`` auth
  (bills the user's Claude subscription). Anthropic only authorizes these for
  Claude-Code-shaped requests, so we send the ``oauth-2025-04-20`` beta header and
  put the Claude Code identity as the FIRST system block, with our resume prompt
  as the second. Drop either and the API rejects the token.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from core import schema
from core.diff import diff_lines, section_changes, summarize_changes
from core.prompts import build_chat_system
from core.sections import normalize

DEFAULT_MODEL = "claude-sonnet-5"

# Load-bearing for OAuth tokens: must be the first system block, verbatim.
CLAUDE_CODE_IDENTITY = "You are Claude Code, Anthropic's official CLI for Claude."
OAUTH_BETA = "oauth-2025-04-20"

PROPOSE_RESUME_TOOL = {
    "name": "propose_resume",
    "description": (
        "Propose a concrete, complete updated resume for the user to review and "
        "apply. Call this only when the user wants a real change (a job TAILOR or a "
        "BASE UPDATE life change). Pass the ENTIRE updated resume document, not a "
        "fragment. Do not call this for advice (ASK) or audit (ATS) turns."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "resume": {
                "type": "object",
                "description": (
                    "The complete updated resume as a {personal, sections} document, "
                    "in the same shape as the baseline."
                ),
            },
            "intent": {
                "type": "string",
                "enum": ["tailor", "base_update"],
                "description": (
                    "tailor = adapt to a specific job (apply as a new branch); "
                    "base_update = a real change to the baseline (stage into the editor)."
                ),
            },
        },
        "required": ["resume"],
    },
}


def is_oauth_token(credential: str) -> bool:
    """True for a Claude Code OAuth token (vs a normal API key)."""
    return credential.strip().startswith("sk-ant-oat")


def _build_system(baseline: dict, current_data: dict | None, oauth: bool) -> list[dict]:
    """System blocks: (CC identity for OAuth) + resume prompt (+ current-view note)."""
    text = build_chat_system(baseline)
    if current_data is not None and normalize(current_data) != normalize(baseline):
        text += (
            "\n\nCURRENTLY VIEWED VERSION — this is the branch the user is working "
            "on right now. Treat it as the working resume for edits and audits this "
            "turn (the baseline above is the canonical life-facts reference):\n"
            + json.dumps(current_data, indent=2, ensure_ascii=False)
        )
    blocks: list[dict] = []
    if oauth:
        blocks.append({"type": "text", "text": CLAUDE_CODE_IDENTITY})
    blocks.append({"type": "text", "text": text})
    return blocks


def _proposal_from(tool_input: dict, current: dict) -> dict:
    """Validate a tool call's resume and package it with a diff vs ``current``."""
    data = schema.validate(tool_input.get("resume") or {})  # raises schema.SchemaError
    return {
        "data": data,
        "intent": tool_input.get("intent"),
        "summary": summarize_changes(current, data),
        "diff": diff_lines(current, data),
        "section_changes": section_changes(current, data),
    }


async def stream_chat(
    *,
    credential: str,
    model: str | None,
    baseline: dict,
    history: list[dict],
    user_message: str,
    current_data: dict | None = None,
) -> AsyncIterator[tuple[str, object]]:
    """Stream one assistant turn.

    Yields ``("delta", text)`` for streamed prose, at most one
    ``("proposal", {...})`` when Claude calls ``propose_resume``, ``("error", msg)``
    for recoverable failures, and a terminal ``("done", None)``. Never raises —
    all failures are surfaced as an ``error`` event so the SSE stream stays intact.
    """
    try:
        import anthropic
    except ImportError:
        yield ("error", "The anthropic SDK is not installed on the server.")
        yield ("done", None)
        return

    oauth = is_oauth_token(credential)
    system = _build_system(baseline, current_data, oauth)
    messages = list(history) + [{"role": "user", "content": user_message}]
    current = current_data if current_data is not None else baseline

    if oauth:
        client = anthropic.AsyncAnthropic(
            auth_token=credential.strip(),
            default_headers={"anthropic-beta": OAUTH_BETA},
        )
    else:
        client = anthropic.AsyncAnthropic(api_key=credential.strip())

    try:
        async with client.messages.stream(
            model=model or DEFAULT_MODEL,
            max_tokens=8000,
            system=system,
            messages=messages,
            tools=[PROPOSE_RESUME_TOOL],
        ) as stream:
            async for event in stream:
                if (
                    event.type == "content_block_delta"
                    and getattr(event.delta, "type", None) == "text_delta"
                ):
                    yield ("delta", event.delta.text)
            final = await stream.get_final_message()
    except Exception as exc:  # noqa: BLE001 — surface any SDK/network/auth error
        yield ("error", f"Claude request failed: {exc}")
        yield ("done", None)
        return

    for block in final.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "propose_resume":
            try:
                yield ("proposal", _proposal_from(block.input, current))
            except schema.SchemaError as exc:
                yield ("error", f"Claude proposed an invalid resume: {exc}")
            break

    yield ("done", None)
