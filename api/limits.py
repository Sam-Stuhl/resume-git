"""In-process, per-user resource guards for the open, self-serve deployment.

Because AI runs on each user's *own* credential, the resources we protect here
are ours: CPU (pdflatex compiles) and the database. Two primitives:

- ``RateLimiter`` — a sliding-window cap of N events per window per key.
- per-user compile locks — one in-flight compile per user, so a single user
  can't occupy every global pdflatex slot.

State lives in *this process only*. The console runs a single container, so this
is sufficient today. If the app is ever scaled horizontally, these become
per-instance and should move to a shared store (Redis / Postgres).
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from fastapi import HTTPException

# Env-tunable knobs (read once at import).
import os

COMPILE_RATE_PER_MIN = int(os.environ.get("COMPILE_RATE_PER_MIN", "30") or "30")
CHAT_RATE_PER_MIN = int(os.environ.get("CHAT_RATE_PER_MIN", "30") or "30")


class RateLimiter:
    """Sliding-window limiter: at most ``max_events`` per ``window_seconds`` per key."""

    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window = window_seconds
        self._events: dict = defaultdict(deque)

    def allow(self, key) -> bool:
        now = time.monotonic()
        q = self._events[key]
        cutoff = now - self.window
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= self.max_events:
            return False
        q.append(now)
        return True

    def hit(self, key, *, detail: str = "Rate limit exceeded. Try again shortly.") -> None:
        """Record an event, raising 429 if the key is over its limit."""
        if not self.allow(key):
            raise HTTPException(status_code=429, detail=detail)


compile_rate = RateLimiter(COMPILE_RATE_PER_MIN, 60.0)
chat_rate = RateLimiter(CHAT_RATE_PER_MIN, 60.0)


# ── Per-user compile concurrency ──────────────────────────────────────────────
_user_compile_locks: dict = defaultdict(lambda: asyncio.Semaphore(1))


def user_compile_lock(user_id: int) -> asyncio.Semaphore:
    return _user_compile_locks[user_id]
