"""Async engine + session factory, driven by ``DATABASE_URL``.

Local dev defaults to a SQLite file; production sets ``DATABASE_URL`` to a Neon
Postgres URL (a ``postgres://`` / ``postgresql://`` URL is normalized to the
asyncpg driver automatically).
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)

from db.models import Base

DEFAULT_SQLITE = "sqlite+aiosqlite:///./data/resume.db"


def _normalize_url(url: str) -> str:
    """Coerce a plain Postgres URL to the async asyncpg driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize_url(os.environ.get("DATABASE_URL", DEFAULT_SQLITE))

# For the SQLite default, make sure the parent directory exists.
if DATABASE_URL.startswith("sqlite"):
    Path("./data").mkdir(parents=True, exist_ok=True)

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Create tables if they do not exist (MVP; Alembic can supersede later)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """FastAPI dependency yielding a session."""
    async with SessionLocal() as session:
        yield session
