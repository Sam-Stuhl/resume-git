import pytest


def test_registry_has_four_skills():
    from core.skills import REGISTRY, skill_list
    assert set(REGISTRY) == {"ask", "ats", "tailor", "base-update"}
    for s in skill_list():
        assert s["name"] and s["description"] and len(s["description"]) < 120


def test_tool_scoping():
    from core.skills import REGISTRY
    from core.tools import READ_TOOL_NAMES
    # ask/ats are read-only; tailor/base-update may propose.
    assert set(REGISTRY["ats"].allowed_tools) <= READ_TOOL_NAMES
    assert "propose_resume" in REGISTRY["tailor"].allowed_tools
    assert "propose_resume" in REGISTRY["base-update"].allowed_tools
    assert "propose_resume" not in REGISTRY["ask"].allowed_tools


def test_allowed_tools_are_real():
    from core.skills import REGISTRY
    from core.tools import ALL_TOOL_SCHEMAS_BY_NAME
    for s in REGISTRY.values():
        for t in s.allowed_tools:
            assert t in ALL_TOOL_SCHEMAS_BY_NAME, f"{s.name} references unknown tool {t}"


def test_instructions_present():
    from core.skills import get_skill
    assert get_skill("tailor").instructions.strip()
    assert get_skill(None) is None
    assert get_skill("bogus") is None
