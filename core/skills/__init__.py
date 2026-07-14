"""Skill registry — one self-describing unit per intent, loaded from SKILL.md files.

Each file is YAML-ish frontmatter (name/description/allowed_tools) + an instructions
body. Kept SKILL.md-shaped so it could port to the real Skills system later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    allowed_tools: list[str]
    instructions: str


def _parse(md: str) -> Skill:
    assert md.startswith("---"), "SKILL.md must start with frontmatter"
    _, front, body = md.split("---", 2)
    meta: dict = {}
    for line in front.strip().splitlines():
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if key == "allowed_tools":
            val = [t.strip() for t in val.strip("[]").split(",") if t.strip()]
        meta[key] = val
    return Skill(name=meta["name"], description=meta["description"],
                 allowed_tools=meta["allowed_tools"], instructions=body.strip())


REGISTRY: dict[str, Skill] = {
    (s := _parse(p.read_text())).name: s for p in sorted(_DIR.glob("*.md"))
}


def get_skill(name: str | None) -> Skill | None:
    return REGISTRY.get(name) if name else None


def skill_list() -> list[dict]:
    return [{"name": s.name, "description": s.description} for s in REGISTRY.values()]
