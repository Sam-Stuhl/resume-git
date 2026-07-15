"""Resume Assistant — the streaming, tool-using chat agent.

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
from collections.abc import AsyncIterator, Awaitable, Callable

from core import schema
from core import tools as agent_tools
from core.diff import diff_lines, section_changes, summarize_changes
from core.prompts import build_chat_system
from core.sections import normalize
from core.skills import get_skill

DEFAULT_MODEL = "claude-sonnet-5"

# Load-bearing for OAuth tokens: must be the first system block, verbatim.
CLAUDE_CODE_IDENTITY = "You are Claude Code, Anthropic's official CLI for Claude."
OAUTH_BETA = "oauth-2025-04-20"

MAX_STEPS = 8


def is_oauth_token(credential: str) -> bool:
    """True for a Claude Code OAuth token (vs a normal API key)."""
    return credential.strip().startswith("sk-ant-oat")


def _tools_for(skill_name: str | None) -> list[dict]:
    """Tool schemas offered to the model: the skill's allow-list, or everything
    (all reads + structural writes + propose_resume) in free-chat advisor mode."""
    skill = get_skill(skill_name)
    if skill is None:  # advisor default: everything, in a stable order for prompt-cache reuse
        names = ([t["name"] for t in agent_tools.READ_TOOL_SCHEMAS]
                 + [t["name"] for t in agent_tools.STRUCTURAL_TOOL_SCHEMAS]
                 + ["propose_resume"])
        return [agent_tools.ALL_TOOL_SCHEMAS_BY_NAME[n] for n in names]
    return [agent_tools.ALL_TOOL_SCHEMAS_BY_NAME[n] for n in skill.allowed_tools]


def _summarize_action(name: str, args: dict) -> str:
    if name == "checkout":
        return f"Checkout v{int(args.get('version', 0)):04d}"
    if name == "restore":
        return f"Restore v{int(args.get('version', 0)):04d} as a new commit"
    return name


def _read_summary(name: str, args) -> str:
    if name == "diff_versions":
        return f"diff v{int(args.get('a', 0)):04d}…v{int(args.get('b', 0)):04d}"
    if name == "get_version":
        return f"read v{int(args.get('version', 0)):04d}"
    if name == "get_current":
        return "read HEAD"
    return "list versions"


def _proposal_from(tool_input: dict, current: dict) -> dict:
    """Validate a tool call's resume and package it with a diff vs ``current``."""
    data = schema.validate(tool_input.get("resume") or {})  # raises schema.SchemaError
    return {
        "data": data,
        "intent": tool_input.get("intent"),
        "branch_name": tool_input.get("branch_name"),
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
    skill: str | None = None,
    head: dict | None = None,
    read_dispatch: Callable[[str, dict], Awaitable[dict]],
) -> AsyncIterator[tuple[str, object]]:
    """Stream one assistant turn as a bounded, git-aware tool loop.

    Each step gives the model a chance to call read tools (executed
    server-side via ``read_dispatch`` and fed back in) or a write tool
    (``checkout``/``restore``/``propose_resume``, surfaced to the UI and the
    turn ends). Yields ``("delta", text)`` for streamed prose,
    ``("tool_step", {"name","summary"})`` per read tool call, at most one
    ``("proposal", {...})`` when Claude calls ``propose_resume``,
    ``("action", {"tool","args","summary"})`` for a structural write,
    ``("error", msg)`` for recoverable failures, and a terminal
    ``("done", None)``. Never raises — all failures are surfaced as an
    ``error`` event so the SSE stream stays intact.
    """
    try:
        import anthropic
    except ImportError:
        yield ("error", "The anthropic SDK is not installed on the server.")
        yield ("done", None)
        return

    skill_obj = get_skill(skill)
    system_text = build_chat_system(baseline, skill_obj.instructions if skill_obj else None)
    if head is not None:
        system_text += (
            f"\n\nCURRENT HEAD: version {head.get('version')} "
            f"(branch {head.get('branch')}). This is where the repo is right now — "
            "trust it over older chat history."
        )
    if current_data is not None and normalize(current_data) != normalize(baseline):
        system_text += (
            "\n\nCURRENTLY VIEWED VERSION (treat as the working resume this turn):\n"
            + json.dumps(current_data, indent=2, ensure_ascii=False)
        )

    oauth = is_oauth_token(credential)
    system = ([{"type": "text", "text": CLAUDE_CODE_IDENTITY}] if oauth else []) + \
             [{"type": "text", "text": system_text}]
    if oauth:
        client = anthropic.AsyncAnthropic(
            auth_token=credential.strip(),
            default_headers={"anthropic-beta": OAUTH_BETA},
        )
    else:
        client = anthropic.AsyncAnthropic(api_key=credential.strip())

    tool_schemas = _tools_for(skill)
    messages = list(history) + [{"role": "user", "content": user_message}]
    current = current_data if current_data is not None else baseline

    for _ in range(MAX_STEPS):
        try:
            async with client.messages.stream(
                model=model or DEFAULT_MODEL,
                max_tokens=8000,
                system=system,
                messages=messages,
                tools=tool_schemas,
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

        tool_uses = [b for b in final.content if getattr(b, "type", None) == "tool_use"]
        reads = [b for b in tool_uses if b.name in agent_tools.READ_TOOL_NAMES]
        writes = [b for b in tool_uses
                 if b.name in agent_tools.WRITE_TOOL_NAMES or b.name == "propose_resume"]

        # A turn mixing reads + writes routes to the write branch below; the reads are
        # intentionally dropped since the turn ends on the write anyway.
        if reads and not writes:
            tool_results = []
            for b in reads:
                try:
                    result = await read_dispatch(b.name, dict(b.input))
                except Exception as exc:  # noqa: BLE001
                    result = {"error": str(exc)}
                yield ("tool_step", {"name": b.name, "summary": _read_summary(b.name, b.input)})
                tool_results.append({
                    "type": "tool_result", "tool_use_id": b.id, "content": json.dumps(result),
                })
            messages.append({"role": "assistant", "content": [
                {"type": "tool_use", "id": b.id, "name": b.name, "input": dict(b.input)}
                for b in reads
            ]})
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
                    yield ("action", {
                        "tool": b.name, "args": dict(b.input),
                        "summary": _summarize_action(b.name, dict(b.input)),
                    })
            break

        break  # end_turn — no tool calls, plain prose answer

    yield ("done", None)
