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


def diff_lines(old: dict, new: dict, context: int = 2) -> list[dict]:
    """Structured unified diff of the two normalized documents.

    Returns ``{"tag": ..., "text": ...}`` where tag is ``meta``/``hunk``/
    ``add``/``del``/``ctx``. The frontend maps tags to colors.
    """
    old_text = json.dumps(normalize(old), indent=2, ensure_ascii=False).splitlines()
    new_text = json.dumps(normalize(new), indent=2, ensure_ascii=False).splitlines()
    out: list[dict] = []
    for line in difflib.unified_diff(
        old_text, new_text, fromfile="previous", tofile="updated",
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
