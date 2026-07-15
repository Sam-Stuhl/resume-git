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
            "branch_name": {
                "type": "string",
                "description": ("For a tailor: a short slug-friendly branch name from the "
                                "company/role, e.g. 'halcyon-backend'. Omit for base_update."),
            },
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
