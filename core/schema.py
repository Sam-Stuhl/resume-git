"""Canonical resume schema + validation.

Enforces the "schema is sacred" rule from the session prompt: the JSON that the
tool stores must have exactly the known top-level keys and the right shapes. The
CLI only checked for ``personal.name``; this centralizes a fuller check used by
both the manual-paste and AI-tailoring paths before anything is committed.
"""

from __future__ import annotations

TOP_LEVEL_KEYS = {
    "personal", "summary", "experience", "projects",
    "leadership", "skills", "education",
}

PERSONAL_KEYS = {"name", "email", "phone", "github", "linkedin"}


class SchemaError(ValueError):
    """Raised when resume data does not match the canonical schema.

    ``problems`` holds every issue found so the UI can show them all at once.
    """

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


def _is_role_list(value, label: str, problems: list[str]) -> None:
    if not isinstance(value, list):
        problems.append(f"{label} must be a list")
        return
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            problems.append(f"{label}[{i}] must be an object")
            continue
        if not item.get("title"):
            problems.append(f"{label}[{i}] missing 'title'")
        if not item.get("organization"):
            problems.append(f"{label}[{i}] missing 'organization'")
        if "bullets" in item and not isinstance(item["bullets"], list):
            problems.append(f"{label}[{i}].bullets must be a list")


def validate(data) -> dict:
    """Validate resume ``data`` against the canonical schema.

    Returns the data unchanged on success; raises :class:`SchemaError` listing
    every problem otherwise.
    """
    problems: list[str] = []

    if not isinstance(data, dict):
        raise SchemaError(["top-level value must be a JSON object"])

    unknown = set(data) - TOP_LEVEL_KEYS
    if unknown:
        problems.append(f"unknown top-level key(s): {', '.join(sorted(unknown))}")

    personal = data.get("personal")
    if not isinstance(personal, dict):
        problems.append("'personal' must be an object")
    else:
        if not personal.get("name"):
            problems.append("personal.name is required")
        unknown_p = set(personal) - PERSONAL_KEYS
        if unknown_p:
            problems.append(f"unknown personal key(s): {', '.join(sorted(unknown_p))}")

    if "summary" in data and not isinstance(data["summary"], str):
        problems.append("'summary' must be a string")

    if "experience" in data:
        _is_role_list(data["experience"], "experience", problems)
    if "leadership" in data:
        _is_role_list(data["leadership"], "leadership", problems)

    if "projects" in data:
        if not isinstance(data["projects"], list):
            problems.append("'projects' must be a list")
        else:
            for i, p in enumerate(data["projects"]):
                if not isinstance(p, dict):
                    problems.append(f"projects[{i}] must be an object")
                elif not p.get("name"):
                    problems.append(f"projects[{i}] missing 'name'")

    if "skills" in data and not isinstance(data["skills"], dict):
        problems.append("'skills' must be an object of category -> string")

    if "education" in data:
        if not isinstance(data["education"], list):
            problems.append("'education' must be a list")
        else:
            for i, ed in enumerate(data["education"]):
                if not isinstance(ed, dict):
                    problems.append(f"education[{i}] must be an object")
                elif not ed.get("school"):
                    problems.append(f"education[{i}] missing 'school'")

    if problems:
        raise SchemaError(problems)
    return data
