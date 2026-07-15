"""Per-user data access — the async, multi-user port of the CLI's DB layer.

Every function takes an ``AsyncSession`` and a ``user_id`` (except user lookup).
No global state, no files: version JSON lives in ``Version.data``.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Config, Message, User, Version

CURRENT_KEY = "current_version"


# ── Users ───────────────────────────────────────────────────────────────────
async def get_user(session: AsyncSession, email: str) -> User | None:
    email = email.strip().lower()
    return (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()


async def create_user(session: AsyncSession, email: str) -> User:
    user = User(email=email.strip().lower())
    session.add(user)
    await session.flush()
    return user


async def count_users(session: AsyncSession) -> int:
    return (
        await session.execute(select(func.count()).select_from(User))
    ).scalar_one()


async def get_or_create_user(session: AsyncSession, email: str) -> User:
    user = await get_user(session, email)
    if user is None:
        user = await create_user(session, email)
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


async def count_versions(session: AsyncSession, user_id: int) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(Version).where(Version.user_id == user_id)
        )
    ).scalar_one()


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


# ── Chat messages (Resume Copilot) ────────────────────────────────────────────
async def add_message(
    session: AsyncSession,
    user_id: int,
    thread_key: str,
    role: str,
    content: str,
    proposal: dict | None = None,
) -> Message:
    row = Message(
        user_id=user_id,
        thread_key=thread_key,
        role=role,
        content=content,
        proposal=proposal,
    )
    session.add(row)
    await session.flush()
    return row


async def list_messages(
    session: AsyncSession, user_id: int, thread_key: str
) -> list[Message]:
    rows = (
        await session.execute(
            select(Message)
            .where(Message.user_id == user_id, Message.thread_key == thread_key)
            .order_by(Message.id.asc())
        )
    ).scalars().all()
    return list(rows)


async def clear_thread(
    session: AsyncSession, user_id: int, thread_key: str
) -> None:
    await session.execute(
        delete(Message).where(
            Message.user_id == user_id, Message.thread_key == thread_key
        )
    )
    await session.flush()
