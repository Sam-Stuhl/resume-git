"""Request identity.

In production the app sits behind Cloudflare Access (Google IdP, email
allowlist). Access injects the authenticated email header and a signed JWT. We
trust the email for per-user scoping and, when configured, verify the JWT
against the Access signing keys as defense-in-depth. For local development
(outside Access), set ``DEV_USER_EMAIL`` to impersonate a user.
"""

from __future__ import annotations

import os
import time

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db import repo
from db.models import User
from db.session import get_session

ACCESS_EMAIL_HEADER = "cf-access-authenticated-user-email"
ACCESS_JWT_HEADER = "cf-access-jwt-assertion"

CF_TEAM_DOMAIN = os.environ.get("CF_ACCESS_TEAM_DOMAIN", "").rstrip("/")
CF_AUD = os.environ.get("CF_ACCESS_AUD", "")
DEV_USER_EMAIL = os.environ.get("DEV_USER_EMAIL", "")

_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL = 3600


async def _verify_access_jwt(token: str) -> None:
    """Verify a Cloudflare Access JWT. No-op if CF_ACCESS_* aren't configured."""
    if not (CF_TEAM_DOMAIN and CF_AUD):
        return  # verification not configured; trust the edge (tunnel-only ingress)
    now = time.time()
    if not _jwks_cache["keys"] or now - _jwks_cache["fetched_at"] > _JWKS_TTL:
        url = f"{CF_TEAM_DOMAIN}/cdn-cgi/access/certs"
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            _jwks_cache["keys"] = resp.json()["keys"]
            _jwks_cache["fetched_at"] = now
    try:
        header = jwt.get_unverified_header(token)
        key = next(k for k in _jwks_cache["keys"] if k["kid"] == header["kid"])
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        jwt.decode(token, public_key, algorithms=["RS256"], audience=CF_AUD)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid Access token") from exc


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    email = request.headers.get(ACCESS_EMAIL_HEADER)
    token = request.headers.get(ACCESS_JWT_HEADER)

    if email and token:
        await _verify_access_jwt(token)
    elif not email:
        if DEV_USER_EMAIL:
            email = DEV_USER_EMAIL
        else:
            raise HTTPException(status_code=401, detail="Not authenticated")

    user = await repo.get_or_create_user(session, email)
    await session.commit()
    return user
