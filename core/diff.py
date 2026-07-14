"""Diffing two resume documents (section model).

Both functions normalize their inputs first, so a legacy version and a
section-model version compare cleanly (apples to apples).
"""

from __future__ import annotations

import difflib
import json

from core.sections import normalize


def summarize_changes(old: dict, new: dict) -> list[str]:
    """High-level, section-level summary of what changed."""
    o = normalize(old)
    n = normalize(new)
    changes: list[str] = []

    if o["personal"] != n["personal"]:
        changes.append("Personal details changed")

    o_secs = {s.get("title", ""): s for s in o["sections"]}
    n_secs = {s.get("title", ""): s for s in n["sections"]}

    for title in n_secs:
        if title not in o_secs:
            changes.append(f"Added section '{title}'")
    for title in o_secs:
        if title not in n_secs:
            changes.append(f"Removed section '{title}'")
    for title in o_secs:
        if title in n_secs and o_secs[title] != n_secs[title]:
            changes.append(f"'{title}' modified")

    o_order = [s.get("title", "") for s in o["sections"]]
    n_order = [s.get("title", "") for s in n["sections"]]
    if [t for t in o_order if t in n_secs] != [t for t in n_order if t in o_secs]:
        changes.append("Sections reordered")

    if not changes:
        changes.append("No structural changes detected")
    return changes


def _unified(old_lines: list[str], new_lines: list[str], context: int = 2) -> list[dict]:
    """Tag the lines of a unified diff for the frontend's color mapping."""
    out: list[dict] = []
    for line in difflib.unified_diff(
        old_lines, new_lines, fromfile="previous", tofile="updated",
        n=context, lineterm="",
    ):
        if line.startswith("+++") or line.startswith("---"):
            tag = "meta"
        elif line.startswith("@@"):
            tag = "hunk"
        elif line.startswith("+"):
            tag = "add"
        elif line.startswith("-"):
            tag = "del"
        else:
            tag = "ctx"
        out.append({"tag": tag, "text": line})
    return out


def diff_lines(old: dict, new: dict, context: int = 2) -> list[dict]:
    """Structured unified diff of the two normalized documents.

    Returns ``{"tag": ..., "text": ...}`` where tag is ``meta``/``hunk``/
    ``add``/``del``/``ctx``. The frontend maps tags to colors.
    """
    old_text = json.dumps(normalize(old), indent=2, ensure_ascii=False).splitlines()
    new_text = json.dumps(normalize(new), indent=2, ensure_ascii=False).splitlines()
    return _unified(old_text, new_text, context)


def _section_key(sec: dict) -> str:
    return f"{sec.get('type', '')}::{sec.get('title', '')}"


def _pretty(value) -> list[str]:
    if value is None:
        return []
    return json.dumps(value, indent=2, ensure_ascii=False).splitlines()


def section_changes(current: dict, proposed: dict) -> list[dict]:
    """Section-level diff powering granular accept/reject in the proposal UI.

    Compares two ``{personal, sections}`` docs (normalized first). ``personal`` is
    treated as one pseudo-section (``key="personal"``); real sections match by
    ``(type, title)``. Returns one entry per *changed* unit — unchanged units are
    omitted — each ``{key, title, status, before, after, diff}`` where ``status``
    is ``added``/``removed``/``modified`` and ``diff`` is the tagged line diff for
    just that unit. The frontend merges accepted entries back onto the working copy.
    """
    cur, prop = normalize(current), normalize(proposed)
    changes: list[dict] = []

    if cur["personal"] != prop["personal"]:
        changes.append({
            "key": "personal",
            "title": "Contact / Personal",
            "status": "modified",
            "before": cur["personal"],
            "after": prop["personal"],
            "diff": _unified(_pretty(cur["personal"]), _pretty(prop["personal"])),
        })

    cur_secs = {_section_key(s): s for s in cur["sections"]}
    prop_secs = {_section_key(s): s for s in prop["sections"]}

    # Walk proposed order first (added/modified), then current-only (removed).
    for key, sec in prop_secs.items():
        title = sec.get("title", "") or "(untitled)"
        if key not in cur_secs:
            changes.append({
                "key": key, "title": title, "status": "added",
                "before": None, "after": sec,
                "diff": _unified([], _pretty(sec)),
            })
        elif cur_secs[key] != sec:
            changes.append({
                "key": key, "title": title, "status": "modified",
                "before": cur_secs[key], "after": sec,
                "diff": _unified(_pretty(cur_secs[key]), _pretty(sec)),
            })
    for key, sec in cur_secs.items():
        if key not in prop_secs:
            changes.append({
                "key": key, "title": sec.get("title", "") or "(untitled)",
                "status": "removed", "before": sec, "after": None,
                "diff": _unified(_pretty(sec), []),
            })

    return changes
