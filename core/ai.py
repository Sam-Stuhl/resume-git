"""In-app AI tailoring via the Claude API.

Reuses the exact ``SESSION_PROMPT_TEMPLATE`` (with the baseline injected) as the
system prompt and sends a ``[TAILOR]`` turn, mirroring the copy-paste flow. The
anthropic SDK is imported lazily so the app runs fine without a key/package.
"""

from __future__ import annotations

import json
import re

from core import schema
from core.prompts import build_session_prompt

DEFAULT_MODEL = "claude-sonnet-5"
KNOWN_MODELS = ["claude-sonnet-5", "claude-opus-4-8", "claude-haiku-4-5-20251001"]

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class AIError(Exception):
    """AI tailoring failed. ``raw`` holds the model's text for manual fallback."""

    def __init__(self, message: str, raw: str = "") -> None:
        super().__init__(message)
        self.raw = raw


def _extract_json(text: str) -> dict:
    stripped = _FENCE_RE.sub("", text.strip())
    # If there's leading/trailing prose, grab the outermost object.
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise AIError("Model did not return JSON.", raw=text)
    try:
        return json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AIError(f"Could not parse model JSON: {exc}", raw=text) from exc


def tailor_with_claude(
    baseline: dict, jd_text: str, api_key: str, model: str | None = None
) -> dict:
    """Return a schema-valid tailored resume dict, or raise :class:`AIError`."""
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise AIError("anthropic SDK not installed on the server.") from exc

    client = anthropic.Anthropic(api_key=api_key)
    system = build_session_prompt(baseline)
    try:
        resp = client.messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=8000,
            system=system,
            messages=[{"role": "user", "content": f"[TAILOR]\n\n{jd_text}"}],
        )
    except Exception as exc:  # noqa: BLE001 — surface any SDK/network error
        raise AIError(f"Claude API call failed: {exc}") from exc

    text = "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    )
    data = _extract_json(text)
    try:
        schema.validate(data)
    except schema.SchemaError as exc:
        raise AIError(f"Tailored JSON failed validation: {exc}", raw=text) from exc
    return data
