"""Unit tests for the copy-paste prompt strings in core/prompts.py."""

from core.prompts import ONBOARDING_BUILD_PROMPT, ONBOARDING_PROMPT


def test_build_prompt_exists_and_is_from_scratch():
    p = ONBOARDING_BUILD_PROMPT
    assert isinstance(p, str) and len(p) > 200
    # Interviews the user rather than converting an attached resume.
    assert "interview" in p.lower() or "ask me" in p.lower()
    # Same strict JSON schema contract as the convert prompt.
    assert '"personal"' in p and '"sections"' not in p  # schema uses experience/projects/... like ONBOARDING_PROMPT
    assert "Return ONLY" in p or "return only" in p.lower()
    # No em dashes anywhere in product copy (u2014 = em dash).
    assert "\u2014" not in p


def test_build_prompt_is_chat_agnostic():
    assert "Claude" not in ONBOARDING_BUILD_PROMPT


def test_build_prompt_shares_schema_with_convert_prompt():
    # Both prompts must emit an identical JSON schema block: same top-level
    # keys, nesting, and field placeholders.
    schema_marker = "REQUIRED SCHEMA:\n\n"
    rules_marker = "\n\nCONVERSION RULES"

    def json_schema_block(prompt: str) -> str:
        start = prompt.index(schema_marker) + len(schema_marker)
        end = prompt.index(rules_marker)
        return prompt[start:end]

    assert json_schema_block(ONBOARDING_BUILD_PROMPT) == json_schema_block(ONBOARDING_PROMPT)

    # Same nine numbered conversion rules present in both (verbatim, aside
    # from ASCII-safe punctuation swapped in for the source prompt's stray
    # em dashes, per rule 5's own "replace em-dashes" guidance).
    for i in range(1, 10):
        rule_marker = f"\n{i}. **"
        assert rule_marker in ONBOARDING_BUILD_PROMPT
        assert rule_marker in ONBOARDING_PROMPT
