"""Per-user data access — the async, multi-user port of the CLI's DB layer.

Every function takes an ``AsyncSession`` and a ``user_id`` (except user lookup).
No global state, no files: version JSON lives in ``Version.data``.
"""

from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Config, User, Version

CURRENT_KEY = "current_version"


# ── Users ───────────────────────────────────────────────────────────────────
async def get_or_create_user(session: AsyncSession, email: str) -> User:
    email = email.strip().lower()
    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if user is None:
        user = User(email=email)
        session.add(user)
        await session.flush()
    return user


# ── Config ──────────────────────────────────────────────────────────────────
async def get_config(session: AsyncSession, user_id: int, key: str) -> str | None:
    row = (
        await session.execute(
            select(Config.value).where(Config.user_id == user_id, Config.key == key)
        )
    ).scalar_one_or_none()
    return row


async def set_config(session: AsyncSession, user_id: int, key: str, value: str) -> None:
    existing = (
        await session.execute(
            select(Config).where(Config.user_id == user_id, Config.key == key)
        )
    ).scalar_one_or_none()
    if existing:
        existing.value = value
    else:
        session.add(Config(user_id=user_id, key=key, value=value))
    await session.flush()


async def current_version(session: AsyncSession, user_id: int) -> int | None:
    val = await get_config(session, user_id, CURRENT_KEY)
    return int(val) if val else None


async def set_current_version(session: AsyncSession, user_id: int, v: int) -> None:
    await set_config(session, user_id, CURRENT_KEY, str(v))


# ── Versions ─────────────────────────────────────────────────────────────────
async def next_version(session: AsyncSession, user_id: int) -> int:
    row = (
        await session.execute(
            select(func.max(Version.version)).where(Version.user_id == user_id)
        )
    ).scalar_one()
    return (row or 0) + 1


async def latest_base_version(session: AsyncSession, user_id: int) -> int | None:
    row = (
        await session.execute(
            select(func.max(Version.version)).where(
                Version.user_id == user_id, Version.is_base.is_(True)
            )
        )
    ).scalar_one()
    return row or None


async def list_versions(session: AsyncSession, user_id: int) -> list[Version]:
    rows = (
        await session.execute(
            select(Version)
            .where(Version.user_id == user_id)
            .order_by(Version.version.desc())
        )
    ).scalars().all()
    return list(rows)


async def get_version(session: AsyncSession, user_id: int, v: int) -> Version | None:
    return (
        await session.execute(
            select(Version).where(
                Version.user_id == user_id, Version.version == v
            )
        )
    ).scalar_one_or_none()


async def insert_version(
    session: AsyncSession,
    user_id: int,
    *,
    version: int,
    data: dict,
    json_hash: str,
    label: str | None,
    jd_text: str | None,
    is_base: bool,
    forked_from: int | None,
) -> Version:
    row = Version(
        user_id=user_id,
        version=version,
        data=data,
        json_hash=json_hash,
        label=label,
        jd_text=jd_text,
        is_base=is_base,
        forked_from=forked_from,
    )
    session.add(row)
    await session.flush()
    return row
