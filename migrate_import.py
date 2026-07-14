"""One-off: import the legacy CLI's ``resume_data/`` into the app database.

Reads the old SQLite index + per-version JSON files and inserts them under a
single user (your email) in the target ``DATABASE_URL``. Version numbers,
labels, dates, JD text, and base/tailor flags are preserved; ``forked_from`` is
inferred (a tailored version forks from the most recent base at or below it).

Usage:
    DATABASE_URL=postgresql://...  python migrate_import.py you@example.com
    # local test:
    DATABASE_URL=sqlite+aiosqlite:///./data/resume.db python migrate_import.py you@example.com --force
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

from db import repo
from db.models import Version
from db.session import SessionLocal, init_db

LEGACY_ROOT = Path(__file__).resolve().parent / "resume_data"
LEGACY_DB = LEGACY_ROOT / "resume.db"
LEGACY_VERSIONS = LEGACY_ROOT / "versions"


async def main(email: str, force: bool) -> None:
    if not LEGACY_DB.exists():
        sys.exit(f"Legacy DB not found at {LEGACY_DB}")

    old = sqlite3.connect(LEGACY_DB)
    rows = old.execute(
        "SELECT version, created_at, label, jd_text, json_hash, is_base "
        "FROM versions ORDER BY version ASC"
    ).fetchall()
    cur_cfg = old.execute(
        "SELECT value FROM config WHERE key='current_version'"
    ).fetchone()
    old.close()

    await init_db()
    async with SessionLocal() as session:
        user = await repo.get_or_create_user(session, email)
        await session.commit()

        existing = await repo.list_versions(session, user.id)
        if existing and not force:
            sys.exit(
                f"User {email} already has {len(existing)} versions. "
                "Re-run with --force to import anyway."
            )

        base_so_far: int | None = None
        imported = 0
        for version, created_at, label, jd_text, json_hash, is_base in rows:
            vfile = LEGACY_VERSIONS / f"v{version:04d}.json"
            if not vfile.exists():
                print(f"  ! skipping v{version:04d}: {vfile.name} missing")
                continue
            data = json.loads(vfile.read_text(encoding="utf-8"))
            forked_from = None if is_base else base_so_far
            row = Version(
                user_id=user.id,
                version=version,
                created_at=_parse_dt(created_at),
                label=label,
                jd_text=jd_text,
                json_hash=json_hash,
                is_base=bool(is_base),
                forked_from=forked_from,
                data=data,
            )
            session.add(row)
            if is_base:
                base_so_far = version
            imported += 1
            print(f"  + v{version:04d} {'BASE' if is_base else 'tailor':6} {label or ''}")

        if cur_cfg:
            await repo.set_config(session, user.id, repo.CURRENT_KEY, cur_cfg[0])
        await session.commit()
        print(f"\nImported {imported} versions for {email}. Current = {cur_cfg[0] if cur_cfg else '?'}")


def _parse_dt(value: str) -> dt.datetime:
    try:
        return dt.datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return dt.datetime.now()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        sys.exit("Usage: python migrate_import.py <email> [--force]")
    asyncio.run(main(args[0], force="--force" in sys.argv))
