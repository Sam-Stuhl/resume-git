"""All API routes, scoped to the Cloudflare-Access-identified user."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

import services
from api import schemas
from api.deps import get_current_user
from core import agent, ai, prompts
from core import skills as skills_registry
from core import tools as agent_tools
from core.diff import diff_lines, summarize_changes
from core.pdf import CompileError, compile_pdf_bytes, compute_archive_name
from core.sections import normalize
from db import repo
from db.models import Message, User, Version
from db.session import SessionLocal, get_session

router = APIRouter(prefix="/api")

# pdflatex is CPU-bound and blocking; cap concurrent compiles.
_compile_sem = asyncio.Semaphore(3)

KEY_API = "anthropic_api_key"
KEY_MODEL = "default_model"
KEY_AI_ENABLED = "ai_enabled"


def _meta(v: Version) -> schemas.VersionMeta:
    return schemas.VersionMeta(
        version=v.version,
        created_at=v.created_at.isoformat() if v.created_at else "",
        label=v.label,
        is_base=v.is_base,
        forked_from=v.forked_from,
        json_hash=v.json_hash,
    )


def _detail(v: Version) -> schemas.VersionDetail:
    # Serve the section model so the editor works uniformly on old + new versions.
    return schemas.VersionDetail(
        **_meta(v).model_dump(), jd_text=v.jd_text, data=normalize(v.data)
    )


def _credential_kind(key: str | None) -> str | None:
    if not key:
        return None
    return "oauth" if agent.is_oauth_token(key) else "api"


async def _ai_state(session: AsyncSession, user_id: int) -> tuple[bool, str]:
    key = await repo.get_config(session, user_id, KEY_API)
    model = await repo.get_config(session, user_id, KEY_MODEL) or ai.DEFAULT_MODEL
    enabled = (await repo.get_config(session, user_id, KEY_AI_ENABLED)) != "0"
    return (bool(key) and enabled, model)


async def _me(session: AsyncSession, user: User) -> schemas.Me:
    ai_enabled, model = await _ai_state(session, user.id)
    key = await repo.get_config(session, user.id, KEY_API)
    return schemas.Me(
        email=user.email, ai_enabled=ai_enabled, default_model=model,
        credential_kind=_credential_kind(key),
    )


# ── Identity / settings ──────────────────────────────────────────────────────
@router.get("/me", response_model=schemas.Me)
async def me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _me(session, user)


@router.get("/settings", response_model=schemas.Me)
async def get_settings(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _me(session, user)


@router.put("/settings")
async def put_settings(
    body: schemas.SettingsIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if body.default_model is not None:
        await repo.set_config(session, user.id, KEY_MODEL, body.default_model)
    if body.ai_enabled is not None:
        await repo.set_config(session, user.id, KEY_AI_ENABLED, "1" if body.ai_enabled else "0")
    await session.commit()
    return {"ok": True}


@router.put("/settings/api-key")
async def put_api_key(
    body: schemas.ApiKeyIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await repo.set_config(session, user.id, KEY_API, body.api_key.strip())
    await session.commit()
    return {"ok": True}  # write-only: the key is never returned


# ── Versions ─────────────────────────────────────────────────────────────────
@router.get("/versions", response_model=list[schemas.VersionMeta])
async def list_versions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = await repo.list_versions(session, user.id)
    return [_meta(v) for v in rows]


@router.get("/versions/current", response_model=schemas.VersionDetail)
async def get_current(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    cur = await repo.current_version(session, user.id)
    if cur is None:
        raise HTTPException(404, "No current version")
    v = await repo.get_version(session, user.id, cur)
    if v is None:
        raise HTTPException(404, "Current version not found")
    return _detail(v)


@router.put("/versions/current")
async def set_current(
    body: schemas.SetCurrentIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if not await services.set_current(session, user.id, body.version):
        raise HTTPException(404, f"v{body.version:04d} not found")
    return {"ok": True}


@router.get("/versions/{v}", response_model=schemas.VersionDetail)
async def get_one(
    v: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    row = await repo.get_version(session, user.id, v)
    if row is None:
        raise HTTPException(404, f"v{v:04d} not found")
    return _detail(row)


@router.post("/base", response_model=schemas.VersionMeta)
async def create_base(
    body: schemas.BaseIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from core.schema import SchemaError
    try:
        row = await services.create_base(session, user.id, body.data, body.label)
    except SchemaError as e:
        raise HTTPException(422, {"problems": e.problems})
    return _meta(row)


@router.post("/tailor", response_model=schemas.VersionMeta)
async def create_tailor(
    body: schemas.TailorIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from core.schema import SchemaError
    try:
        row = await services.create_tailor(
            session, user.id, body.data, body.label, body.jd_text
        )
    except SchemaError as e:
        raise HTTPException(422, {"problems": e.problems})
    except services.NoBaseError:
        raise HTTPException(400, "No base resume yet. Create a base first.")
    return _meta(row)


@router.post("/tailor/preview", response_model=schemas.TailorPreviewOut)
async def tailor_preview(
    body: schemas.TailorPreviewIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    key = await repo.get_config(session, user.id, KEY_API)
    if not key:
        raise HTTPException(400, "No Claude API key configured.")
    base = await repo.latest_base_version(session, user.id)
    if base is None:
        raise HTTPException(400, "No base resume yet.")
    baseline = (await repo.get_version(session, user.id, base)).data
    model = body.model or await repo.get_config(session, user.id, KEY_MODEL)
    try:
        tailored = await run_in_threadpool(
            ai.tailor_with_claude, baseline, body.jd_text, key, model
        )
    except ai.AIError as e:
        raise HTTPException(422, {"error": str(e), "raw": e.raw})
    return schemas.TailorPreviewOut(
        data=tailored,
        diff=diff_lines(baseline, tailored),
        summary=summarize_changes(baseline, tailored),
    )


@router.post("/import")
async def import_data(
    body: schemas.ImportIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from core.schema import SchemaError
    try:
        n = await services.import_bundle(
            session, user.id, body.versions, body.current_version, body.replace
        )
    except services.AlreadyHasDataError as e:
        raise HTTPException(409, {"error": "account_not_empty", "count": e.count})
    except SchemaError as e:
        raise HTTPException(422, {"problems": e.problems})
    return {"imported": n}


@router.post("/versions/{v}/restore", response_model=schemas.VersionMeta)
async def restore(
    v: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    row = await services.restore(session, user.id, v)
    if row is None:
        raise HTTPException(404, f"v{v:04d} not found")
    return _meta(row)


@router.get("/versions/{a}/diff/{b}", response_model=schemas.DiffOut)
async def diff_versions(
    a: int,
    b: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    va = await repo.get_version(session, user.id, a)
    vb = await repo.get_version(session, user.id, b)
    if va is None or vb is None:
        raise HTTPException(404, "version not found")
    return schemas.DiffOut(
        summary=summarize_changes(va.data, vb.data),
        lines=diff_lines(va.data, vb.data),
    )


# ── Resume Copilot chat ───────────────────────────────────────────────────────
@router.get("/skills", response_model=list[schemas.SkillOut])
async def list_skills(user: User = Depends(get_current_user)):
    return skills_registry.skill_list()


def _chat_msg(m: Message) -> schemas.ChatMessageOut:
    return schemas.ChatMessageOut(
        id=m.id, role=m.role, content=m.content, proposal=m.proposal,
        created_at=m.created_at.isoformat() if m.created_at else "",
    )


@router.get("/chat/{thread_key}", response_model=list[schemas.ChatMessageOut])
async def chat_history(
    thread_key: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = await repo.list_messages(session, user.id, thread_key)
    return [_chat_msg(m) for m in rows]


@router.delete("/chat/{thread_key}")
async def chat_clear(
    thread_key: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await repo.clear_thread(session, user.id, thread_key)
    await session.commit()
    return {"ok": True}


@router.post("/chat/{thread_key}")
async def chat_send(
    thread_key: str,
    body: schemas.ChatSendIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    key = await repo.get_config(session, user.id, KEY_API)
    if not key:
        raise HTTPException(400, "No Claude API key or token configured. Add one in Settings.")

    base = await repo.latest_base_version(session, user.id)
    baseline = (
        (await repo.get_version(session, user.id, base)).data
        if base is not None else {"personal": {}, "sections": []}
    )
    model = body.model or await repo.get_config(session, user.id, KEY_MODEL)

    # Replay only prior *text* turns as history (proposals are UI-only, never
    # replayed as tool calls — keeps the Messages API history simple and valid).
    prior = await repo.list_messages(session, user.id, thread_key)
    history = [{"role": m.role, "content": m.content} for m in prior if m.content]

    # Persist the user's message before streaming (committed on the request session).
    await repo.add_message(session, user.id, thread_key, "user", body.message)
    await session.commit()

    uid = user.id

    async def gen():
        parts: list[str] = []
        proposal = None
        actions: list[dict] = []
        async with SessionLocal() as s2:
            async def read_dispatch(name: str, args: dict) -> dict:
                return await agent_tools.dispatch_read(s2, uid, name, args)
            async for kind, payload in agent.stream_chat(
                credential=key, model=model, baseline=baseline, history=history,
                user_message=body.message, current_data=body.current_data,
                skill=body.skill, read_dispatch=read_dispatch,
            ):
                if kind == "delta":
                    parts.append(payload)
                elif kind == "proposal":
                    proposal = payload
                elif kind == "action":
                    actions.append(payload)
                yield f"data: {json.dumps({'type': kind, 'data': payload})}\n\n"
            await repo.add_message(s2, uid, thread_key, "assistant", "".join(parts),
                                   proposal=proposal or ({"actions": actions} if actions else None))
            await s2.commit()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── PDF ──────────────────────────────────────────────────────────────────────
async def _compile(data: dict) -> bytes:
    async with _compile_sem:
        try:
            return await run_in_threadpool(compile_pdf_bytes, data)
        except CompileError as e:
            raise HTTPException(422, {"error": str(e), "log": e.log_tail})


def _pdf_response(pdf: bytes, filename: str) -> Response:
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/versions/{v}/pdf")
async def version_pdf(
    v: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    row = await repo.get_version(session, user.id, v)
    if row is None:
        raise HTTPException(404, f"v{v:04d} not found")
    pdf = await _compile(row.data)
    return _pdf_response(pdf, compute_archive_name(row.data, v))


@router.post("/preview/pdf")
async def preview_pdf(
    body: schemas.PreviewIn,
    user: User = Depends(get_current_user),
):
    """Compile arbitrary (unsaved) resume data to a PDF for the live preview.

    Lenient by design: renders whatever's there so the preview updates mid-edit.
    Requires only a ``personal`` object; commit-time validation is stricter.
    """
    data = body.data
    if not isinstance(data, dict) or not isinstance(data.get("personal"), dict):
        raise HTTPException(422, {"error": "resume must have a 'personal' object"})
    pdf = await _compile(data)
    return _pdf_response(pdf, "preview.pdf")


@router.get("/pdf/current")
async def current_pdf(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    cur = await repo.current_version(session, user.id)
    if cur is None:
        raise HTTPException(404, "No current version")
    row = await repo.get_version(session, user.id, cur)
    pdf = await _compile(row.data)
    return _pdf_response(pdf, compute_archive_name(row.data, cur))


# ── Prompts (copy-paste fallback) ────────────────────────────────────────────
@router.get("/prompts/onboarding")
async def prompt_onboarding():
    return {"prompt": prompts.ONBOARDING_PROMPT}


@router.get("/prompts/turns")
async def prompt_turns():
    return {"prompt": prompts.TURN_PROMPTS}


@router.get("/prompts/session")
async def prompt_session(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    base = await repo.latest_base_version(session, user.id)
    if base is None:
        raise HTTPException(400, "No base resume yet.")
    baseline = (await repo.get_version(session, user.id, base)).data
    return {"prompt": prompts.build_session_prompt(baseline)}
