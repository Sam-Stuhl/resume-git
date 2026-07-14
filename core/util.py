"""Small pure helpers shared across the core library."""

from __future__ import annotations

import hashlib
import json


def hash_json(data: dict) -> str:
    """Stable 12-char content hash of a resume dict (used for dedup)."""
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:12]
