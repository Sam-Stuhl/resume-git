"""Self-serve auth: Google sign-in + a stateless session cookie.

The app used to get its identity from Cloudflare Access at the edge. That gate is
gone, so the app authenticates users itself:

- **Sign-in** is Google OAuth (Authorization Code flow). Google verifies the email,
  so existing accounts (keyed by email) carry over and there's no email-squatting.
- **Sessions** are a JWT signed with ``SESSION_SECRET``, carried in an httpOnly,
  Secure, SameSite=Lax cookie. Stateless on purpose: containers are ephemeral and
  replaced on every deploy, so nothing session-related lives in memory or on disk.

Config (all from env; secrets set in the console):
  SESSION_SECRET        signs the session cookie (REQUIRED in prod)
  GOOGLE_CLIENT_ID      OAuth client id
  GOOGLE_CLIENT_SECRET  OAuth client secret
  APP_BASE_URL          public origin, used to build the OAuth redirect URI and to
                        decide whether cookies get the Secure flag (https only)
"""

from __future__ import annotations

import os
import secrets as pysecrets
import time
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db import repo
from db.models import User
from db.session import get_session

router = APIRouter(prefix="/api/auth")

# The public origin is env-driven (set APP_BASE_URL in console.toml for prod). The
# default is a local-dev fallback only: http:// keeps Secure cookies off for localhost.
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8080").rstrip("/")
SESSION_SECRET = os.environ.get("SESSION_SECRET") or "dev-insecure-session-secret-change-me"
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
MAX_USERS = int(os.environ.get("MAX_USERS", "0") or "0")

SECURE_COOKIES = APP_BASE_URL.startswith("https")
SESSION_COOKIE = "session"
STATE_COOKIE = "oauth_state"
SESSION_TTL = 30 * 24 * 3600  # 30 days
STATE_TTL = 600               # 10 minutes to complete the round-trip

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
REDIRECT_URI = f"{APP_BASE_URL}/api/auth/google/callback"

_jwk_client = jwt.PyJWKClient(GOOGLE_CERTS_URL)


# ── Session cookie ────────────────────────────────────────────────────────────
def create_session_token(user_id: int) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + SESSION_TTL},
        SESSION_SECRET, algorithm="HS256",
    )


def session_user_id(request: Request) -> int | None:
    """Return the signed-in user's id from the session cookie, or None."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        claims = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
        return int(claims["sub"])
    except Exception:  # noqa: BLE001 — any invalid/expired token means "not signed in"
        return None


def set_session_cookie(resp, token: str) -> None:
    resp.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_TTL, httponly=True,
        secure=SECURE_COOKIES, samesite="lax", path="/",
    )


def clear_session_cookie(resp) -> None:
    resp.delete_cookie(SESSION_COOKIE, path="/")


# ── User resolution (shared cap logic) ────────────────────────────────────────
async def resolve_or_create_user(
    session: AsyncSession, email: str, name: str | None = None
) -> User:
    """Find the user by email, creating on first sign-in unless MAX_USERS is hit."""
    user = await repo.get_user(session, email)
    if user is None:
        if MAX_USERS and await repo.count_users(session) >= MAX_USERS:
            raise HTTPException(status_code=403, detail="Signups are currently full.")
        try:
            user = await repo.create_user(session, email)
        except IntegrityError:
            await session.rollback()
            user = await repo.get_user(session, email)
            if user is None:
                raise
    if name and not user.display_name:
        user.display_name = name[:200]
    return user


# ── Google OAuth ──────────────────────────────────────────────────────────────
@router.get("/google/login")
async def google_login():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, "Google sign-in is not configured.")
    state = pysecrets.token_urlsafe(24)
    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    })
    resp = RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}", status_code=302)
    # CSRF: the callback must present this same state, proving the round-trip is ours.
    resp.set_cookie(
        STATE_COOKIE, state, max_age=STATE_TTL, httponly=True,
        secure=SECURE_COOKIES, samesite="lax", path="/api/auth",
    )
    return resp


async def _exchange_code(code: str) -> dict:
    """Trade the authorization code for tokens at Google's token endpoint."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        })
    if resp.status_code != 200:
        raise HTTPException(401, "Token exchange failed.")
    return resp.json()


async def _verify_google_id_token(id_token: str) -> dict:
    signing_key = await run_in_threadpool(_jwk_client.get_signing_key_from_jwt, id_token)
    claims = jwt.decode(id_token, signing_key.key, algorithms=["RS256"], audience=GOOGLE_CLIENT_ID)
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise HTTPException(401, "Bad token issuer.")
    return claims


@router.get("/google/callback")
async def google_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error or not code:
        return RedirectResponse("/?auth=failed", status_code=302)
    if not state or state != request.cookies.get(STATE_COOKIE):
        raise HTTPException(400, "Invalid or missing OAuth state.")

    # Exchange the authorization code for tokens, then verify the id_token.
    id_token = (await _exchange_code(code)).get("id_token")
    if not id_token:
        raise HTTPException(401, "No id_token from Google.")

    claims = await _verify_google_id_token(id_token)
    email = (claims.get("email") or "").strip().lower()
    if not email or not claims.get("email_verified"):
        raise HTTPException(401, "Google account has no verified email.")

    user = await resolve_or_create_user(session, email, claims.get("name"))
    await session.commit()

    resp = RedirectResponse("/", status_code=302)
    set_session_cookie(resp, create_session_token(user.id))
    resp.delete_cookie(STATE_COOKIE, path="/api/auth")
    return resp


@router.post("/logout")
async def logout():
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"ok": True})
    clear_session_cookie(resp)
    return resp
