"""Orchestration shared by the API (and available to the CLI).

This is the transaction boundary: validate -> hash -> insert version -> set
current. It ports the bodies of the CLI's ``cmd_base`` / ``cmd_tailor`` /
``cmd_restore`` minus all terminal I/O.
"""

from __future__ import annotations

import datetime as dt
import os

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from core import schema
from core.util import hash_json
from db import repo
from db.models import Config, Version

# Per-user stored-version cap for the open deployment. 0 = unlimited. Every new
# version is non-destructive (history is a product value), so at the cap we
# *reject* rather than prune.
MAX_VERSIONS_PER_USER = int(os.environ.get("MAX_VERSIONS_PER_USER", "0") or "0")


class NoBaseError(Exception):
    """No base resume exists yet; create one before tailoring."""


class QuotaExceededError(Exception):
    """The user is at ``MAX_VERSIONS_PER_USER``; no new version can be created."""

    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(f"version quota reached ({count})")


async def _enforce_version_quota(session: AsyncSession, user_id: int) -> None:
    if MAX_VERSIONS_PER_USER:
        count = await repo.count_versions(session, user_id)
        if count >= MAX_VERSIONS_PER_USER:
            raise QuotaExceededError(count)


class AlreadyHasDataError(Exception):
    """User already has versions; importing needs replace=True to overwrite."""

    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(f"account already has {count} versions")


async def create_base(
    session: AsyncSession, user_id: int, data: dict, label: str | None
) -> Version:
    """Save ``data`` as a new base version and make it current."""
    data = schema.validate(data)  # normalizes to the section model
    await _enforce_version_quota(session, user_id)
    v = await repo.next_version(session, user_id)
    row = await repo.insert_version(
        session, user_id,
        version=v, data=data, json_hash=hash_json(data),
        label=label or "Base update", jd_text=None,
        is_base=True, forked_from=None,
    )
    await repo.set_current_version(session, user_id, v)
    await session.commit()
    return row


async def create_tailor(
    session: AsyncSession,
    user_id: int,
    data: dict,
    label: str | None,
    jd_text: str | None,
) -> Version:
    """Save ``data`` as a tailored fork of the latest base and make it current."""
    data = schema.validate(data)  # normalizes to the section model
    base = await repo.latest_base_version(session, user_id)
    if base is None:
        raise NoBaseError()
    await _enforce_version_quota(session, user_id)
    v = await repo.next_version(session, user_id)
    row = await repo.insert_version(
        session, user_id,
        version=v, data=data, json_hash=hash_json(data),
        label=label, jd_text=jd_text,
        is_base=False, forked_from=base,
    )
    await repo.set_current_version(session, user_id, v)
    await session.commit()
    return row


async def restore(session: AsyncSession, user_id: int, v: int) -> Version | None:
    """Non-destructively promote v: create a new version copying its contents."""
    src = await repo.get_version(session, user_id, v)
    if src is None:
        return None
    await _enforce_version_quota(session, user_id)
    new_v = await repo.next_version(session, user_id)
    row = await repo.insert_version(
        session, user_id,
        version=new_v, data=src.data, json_hash=src.json_hash,
        label=f"Restored from v{v:04d}", jd_text=None,
        is_base=src.is_base, forked_from=v,
    )
    await repo.set_current_version(session, user_id, new_v)
    await session.commit()
    return row


def _parse_dt(value) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


async def import_bundle(
    session: AsyncSession,
    user_id: int,
    versions: list[dict],
    current_version: int | None,
    replace: bool,
) -> int:
    """Import an exported CLI bundle, preserving version numbers and lineage.

    Raises :class:`AlreadyHasDataError` if the account has data and ``replace``
    is False. With ``replace=True`` the user's existing versions/config are
    cleared first. Returns the number of versions imported.
    """
    existing = await repo.list_versions(session, user_id)
    if existing:
        if not replace:
            raise AlreadyHasDataError(len(existing))
        await session.execute(delete(Version).where(Version.user_id == user_id))
        await session.execute(delete(Config).where(Config.user_id == user_id))
        await session.flush()

    count = 0
    for v in sorted(versions, key=lambda x: x["version"]):
        data = v["data"]
        schema.validate(data)  # reject anything that isn't a valid resume
        session.add(
            Version(
                user_id=user_id,
                version=v["version"],
                created_at=_parse_dt(v.get("created_at")),
                label=v.get("label"),
                jd_text=v.get("jd_text"),
                json_hash=v.get("json_hash") or hash_json(data),
                is_base=bool(v.get("is_base")),
                forked_from=v.get("forked_from"),
                data=data,
            )
        )
        count += 1

    if current_version is not None:
        await repo.set_config(session, user_id, repo.CURRENT_KEY, str(current_version))
    await session.commit()
    return count


async def set_current(session: AsyncSession, user_id: int, v: int) -> bool:
    """Point ``current`` at an existing version. Returns False if not found."""
    if await repo.get_version(session, user_id, v) is None:
        return False
    await repo.set_current_version(session, user_id, v)
    await session.commit()
    return True
