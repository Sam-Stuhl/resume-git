"""Async engine + session factory, driven by ``DATABASE_URL``.

Local dev defaults to a SQLite file; production sets ``DATABASE_URL`` to a Neon
Postgres URL (a ``postgres://`` / ``postgresql://`` URL is normalized to the
asyncpg driver automatically).
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)

from db.models import Base

DEFAULT_SQLITE = "sqlite+aiosqlite:///./data/resume.db"

# libpq query params asyncpg doesn't understand (Neon appends these).
_LIBPQ_ONLY = ("sslmode", "channel_binding")
# sslmode values that mean "use TLS" — asyncpg wants ssl=True instead.
_SSL_MODES = ("require", "verify-ca", "verify-full", "prefer")


def _build_url_and_connect_args(raw: str):
    """Normalize DATABASE_URL for the asyncpg driver.

    Coerces ``postgres://``/``postgresql://`` to the async driver and, crucially,
    strips libpq-only query params (``sslmode``/``channel_binding``) that asyncpg
    rejects — translating an SSL-requiring ``sslmode`` into ``ssl=True``. This is
    what makes Neon connection strings work out of the box.
    """
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://"):]

    url = make_url(raw)
    connect_args: dict = {}
    if url.drivername.endswith("asyncpg"):
        query = dict(url.query)
        sslmode = query.pop("sslmode", None)
        query.pop("channel_binding", None)
        url = url.set(query=query)
        if sslmode in _SSL_MODES:
            connect_args["ssl"] = True
        # Neon's pooled (pgbouncer) endpoint breaks asyncpg's prepared-statement
        # cache; disabling it is safe and cheap at this scale.
        connect_args["statement_cache_size"] = 0
    return url, connect_args


DATABASE_URL, _CONNECT_ARGS = _build_url_and_connect_args(
    os.environ.get("DATABASE_URL", DEFAULT_SQLITE)
)

# For the SQLite default, make sure the parent directory exists.
if DATABASE_URL.drivername.startswith("sqlite"):
    Path("./data").mkdir(parents=True, exist_ok=True)

engine = create_async_engine(DATABASE_URL, connect_args=_CONNECT_ARGS, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Create tables if they do not exist (MVP; Alembic can supersede later)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """FastAPI dependency yielding a session."""
    async with SessionLocal() as session:
        yield session
