"""Validation for the flexible ``{personal, sections}`` resume model.

``validate`` normalizes first (so legacy fixed-schema data is accepted and
upgraded), then checks the header and every typed section. It returns the
normalized data, which the services layer stores — so new commits are saved in
the section model.
"""

from __future__ import annotations

from core.sections import SECTION_TYPES, normalize

PERSONAL_KEYS = {"name", "email", "phone", "github", "linkedin"}


class SchemaError(ValueError):
    """Raised when resume data does not match the schema. ``problems`` lists all."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


def _check_entries(entries, label: str, required: list[str], problems: list[str]) -> None:
    if not isinstance(entries, list):
        problems.append(f"{label}.entries must be a list")
        return
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            problems.append(f"{label}.entries[{i}] must be an object")
            continue
        for field in required:
            if not e.get(field):
                problems.append(f"{label}.entries[{i}] missing '{field}'")
        if "bullets" in e and not isinstance(e["bullets"], list):
            problems.append(f"{label}.entries[{i}].bullets must be a list")


def validate(data) -> dict:
    """Validate resume ``data``; return it normalized to the section model."""
    problems: list[str] = []
    data = normalize(data)

    personal = data.get("personal")
    if not isinstance(personal, dict):
        problems.append("'personal' must be an object")
    else:
        if not personal.get("name"):
            problems.append("personal.name is required")
        unknown = set(personal) - PERSONAL_KEYS
        if unknown:
            problems.append(f"unknown personal key(s): {', '.join(sorted(unknown))}")

    sections = data.get("sections")
    if not isinstance(sections, list):
        problems.append("'sections' must be a list")
    else:
        for i, s in enumerate(sections):
            label = f"sections[{i}]"
            if not isinstance(s, dict):
                problems.append(f"{label} must be an object")
                continue
            t = s.get("type")
            if t not in SECTION_TYPES:
                problems.append(f"{label} has unknown type {t!r}")
                continue
            if not isinstance(s.get("title", ""), str):
                problems.append(f"{label}.title must be a string")
            if t == "text":
                if not isinstance(s.get("text", ""), str):
                    problems.append(f"{label}.text must be a string")
            elif t == "roles":
                _check_entries(s.get("entries", []), label, ["title", "organization"], problems)
            elif t == "projects":
                _check_entries(s.get("entries", []), label, ["name"], problems)
            elif t == "education":
                _check_entries(s.get("entries", []), label, ["school"], problems)
            elif t == "skills":
                groups = s.get("groups", [])
                if not isinstance(groups, list):
                    problems.append(f"{label}.groups must be a list")
                else:
                    for j, g in enumerate(groups):
                        if not isinstance(g, dict) or not g.get("category"):
                            problems.append(f"{label}.groups[{j}] needs a 'category'")
            elif t == "bullets":
                if not isinstance(s.get("items", []), list):
                    problems.append(f"{label}.items must be a list")

    if problems:
        raise SchemaError(problems)
    return data
