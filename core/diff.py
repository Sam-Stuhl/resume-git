"""Diffing two resume JSON documents.

``summarize_changes`` gives a section-level summary (ported verbatim from the
CLI). ``diff_lines`` replaces the CLI's ANSI ``render_diff`` with structured
tokens the frontend can color itself.
"""

from __future__ import annotations

import difflib
import json


def summarize_changes(old: dict, new: dict) -> list[str]:
    """High-level summary of what changed between two resume JSONs."""
    changes: list[str] = []

    def section(label: str, before, after, count_key: str | None = None) -> None:
        if before == after:
            return
        if count_key is None:
            changes.append(f"{label} modified")
        else:
            b = len(before) if hasattr(before, "__len__") else "?"
            a = len(after) if hasattr(after, "__len__") else "?"
            if b != a:
                changes.append(f"{label}: {b} → {a} {count_key}")
            else:
                changes.append(f"{label} reworded ({b} {count_key})")

    if old.get("summary") != new.get("summary"):
        ob = len(old.get("summary") or "")
        nb = len(new.get("summary") or "")
        changes.append(f"Summary rewritten ({ob} → {nb} chars)")

    section("Experience", old.get("experience"), new.get("experience"), "roles")
    section("Projects", old.get("projects"), new.get("projects"), "projects")
    section("Leadership", old.get("leadership"), new.get("leadership"), "roles")
    section("Education", old.get("education"), new.get("education"), "schools")

    old_skills = old.get("skills") or {}
    new_skills = new.get("skills") or {}
    if old_skills != new_skills:
        added = set(new_skills) - set(old_skills)
        removed = set(old_skills) - set(new_skills)
        for k in added:
            changes.append(f"Skills: added category '{k}'")
        for k in removed:
            changes.append(f"Skills: removed category '{k}'")
        for k in set(old_skills) & set(new_skills):
            if old_skills[k] != new_skills[k]:
                changes.append(f"Skills.{k} updated")

    if not changes:
        changes.append("No structural changes detected")
    return changes


def diff_lines(old: dict, new: dict, context: int = 2) -> list[dict]:
    """Structured unified diff of two JSON documents.

    Returns a list of ``{"tag": ..., "text": ...}`` where ``tag`` is one of
    ``"meta"`` (file/header lines), ``"hunk"`` (``@@`` markers), ``"add"``,
    ``"del"``, or ``"ctx"`` (unchanged context). The frontend maps tags to
    colors; no ANSI is emitted here.
    """
    old_text = json.dumps(old, indent=2, ensure_ascii=False).splitlines()
    new_text = json.dumps(new, indent=2, ensure_ascii=False).splitlines()
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
