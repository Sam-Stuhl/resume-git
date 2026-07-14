"""Flexible resume model: a header plus an ordered list of typed sections.

Instead of seven hard-coded keys, a resume is ``{personal, sections: [...]}``
where each section declares a ``type`` from a curated palette of rendering
patterns. ``normalize`` upgrades the legacy fixed-schema shape to this model on
read, so old stored versions keep working without a destructive migration.
"""

from __future__ import annotations

# Curated rendering patterns. Each maps to a renderer in core.latex and an
# editor in the frontend.
SECTION_TYPES = ("text", "roles", "projects", "skills", "education", "bullets")

# Legacy fixed keys -> (type, default title), in the order the old template used.
_LEGACY_ORDER = [
    ("summary", "text", "Summary"),
    ("experience", "roles", "Experience"),
    ("projects", "projects", "Projects"),
    ("leadership", "roles", "Leadership & Extracurriculars"),
    ("skills", "skills", "Technical Skills"),
    ("education", "education", "Education"),
]


def is_new_model(data: dict) -> bool:
    return isinstance(data, dict) and isinstance(data.get("sections"), list)


def _legacy_to_sections(data: dict) -> list[dict]:
    sections: list[dict] = []
    for key, type_, title in _LEGACY_ORDER:
        value = data.get(key)
        if not value:
            continue  # skip empty, matching old "render nothing" behavior
        if type_ == "text":
            sections.append({"type": "text", "title": title, "text": value})
        elif type_ == "roles":
            sections.append({"type": "roles", "title": title, "entries": value})
        elif type_ == "projects":
            sections.append({"type": "projects", "title": title, "entries": value})
        elif type_ == "education":
            sections.append({"type": "education", "title": title, "entries": value})
        elif type_ == "skills":
            groups = [{"category": k, "items": v} for k, v in value.items()]
            sections.append({"type": "skills", "title": title, "groups": groups})
    return sections


def normalize(data: dict) -> dict:
    """Return the resume in the ``{personal, sections}`` model (idempotent)."""
    if not isinstance(data, dict):
        return {"personal": {}, "sections": []}
    personal = data.get("personal") or {}
    if is_new_model(data):
        return {"personal": personal, "sections": data["sections"]}
    return {"personal": personal, "sections": _legacy_to_sections(data)}
