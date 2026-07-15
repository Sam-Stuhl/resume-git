"""Request identity.

The app authenticates users itself (see ``api.auth``): identity comes from a
signed session cookie issued after Google sign-in. ``get_current_user`` decodes
that cookie and loads the user.

For local development, set ``DEV_USER_EMAIL`` to impersonate a user without going
through Google. It is a no-op in production (the env var simply isn't set there).
"""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api import auth
from db import repo
from db.models import User
from db.session import get_session

DEV_USER_EMAIL = os.environ.get("DEV_USER_EMAIL", "")


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    uid = auth.session_user_id(request)
    if uid is not None:
        user = await repo.get_user_by_id(session, uid)
        if user is not None:
            return user
        # Cookie is validly signed but the user is gone (deleted account): reject.

    # Local-dev shim: no valid session, but an impersonation email is configured.
    if DEV_USER_EMAIL:
        user = await auth.resolve_or_create_user(session, DEV_USER_EMAIL)
        await session.commit()
        return user

    raise HTTPException(status_code=401, detail="Not authenticated")
