"""All API routes, scoped to the signed-in user (see api.auth / api.deps)."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

import services
from api import limits, schemas
from api.deps import get_current_user
from core import agent, ai, prompts, schema
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


def _QUOTA_DETAIL(count: int) -> dict:
    return {
        "error": "version_quota_reached",
        "count": count,
        "message": (
            f"You've reached the {count}-version limit for this account. History is "
            "never deleted automatically — remove versions you no longer need, or "
            "reach out to raise the cap."
        ),
    }


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
        display_name=user.display_name,
        created_at=user.created_at.isoformat() if user.created_at else None,
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
    if body.display_name is not None:
        user.display_name = body.display_name.strip() or None  # empty clears it
    await session.commit()
    return {"ok": True}


@router.delete("/account")
async def delete_account(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Permanently delete the signed-in account and all its data."""
    await repo.delete_user(session, user.id)
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
    except services.QuotaExceededError as e:
        raise HTTPException(403, _QUOTA_DETAIL(e.count))
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
    except services.QuotaExceededError as e:
        raise HTTPException(403, _QUOTA_DETAIL(e.count))
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
    try:
        row = await services.restore(session, user.id, v)
    except services.QuotaExceededError as e:
        raise HTTPException(403, _QUOTA_DETAIL(e.count))
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


# ── Resume Assistant chat ─────────────────────────────────────────────────────
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


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


async def _agent_context(session: AsyncSession, user_id: int) -> tuple[dict, dict | None]:
    """Baseline resume + current HEAD (version/branch) for the agent's context.

    HEAD matters because confirmed checkouts aren't recorded in the chat thread, so
    without it the model can misjudge state from stale history.
    """
    base = await repo.latest_base_version(session, user_id)
    baseline = (
        (await repo.get_version(session, user_id, base)).data
        if base is not None else {"personal": {}, "sections": []}
    )
    cur = await repo.current_version(session, user_id)
    head = None
    if cur is not None:
        row = await repo.get_version(session, user_id, cur)
        if row is not None:
            head = {
                "version": row.version,
                "branch": agent_tools.branch_of(row.label, row.is_base),
                "is_base": row.is_base,
            }
    return baseline, head


def _agent_stream(*, thread_key, uid, key, model, baseline, head, history, user_message, current_data, skill=None):
    """Run one agent turn as SSE and persist the assistant message. Shared by send + continue."""
    async def gen():
        parts: list[str] = []
        proposal = None
        actions: list[dict] = []
        async with SessionLocal() as s2:
            async def read_dispatch(name: str, args: dict) -> dict:
                return await agent_tools.dispatch_read(s2, uid, name, args)
            async for kind, payload in agent.stream_chat(
                credential=key, model=model, baseline=baseline, history=history,
                user_message=user_message, current_data=current_data,
                skill=skill, head=head, read_dispatch=read_dispatch,
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

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/chat/{thread_key}")
async def chat_send(
    thread_key: str,
    body: schemas.ChatSendIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    limits.chat_rate.hit(user.id, detail="Too many assistant requests. Please slow down.")
    key = await repo.get_config(session, user.id, KEY_API)
    if not key:
        raise HTTPException(400, "No Claude API key or token configured. Add one in Settings.")
    baseline, head = await _agent_context(session, user.id)
    model = body.model or await repo.get_config(session, user.id, KEY_MODEL)
    # Replay only prior *text* turns as history (tool round-trips are ephemeral).
    prior = await repo.list_messages(session, user.id, thread_key)
    history = [{"role": m.role, "content": m.content} for m in prior if m.content]
    # Persist the user's message before streaming (committed on the request session).
    await repo.add_message(session, user.id, thread_key, "user", body.message)
    await session.commit()
    return _agent_stream(
        thread_key=thread_key, uid=user.id, key=key, model=model, baseline=baseline,
        head=head, history=history, user_message=body.message,
        current_data=body.current_data, skill=body.skill,
    )


@router.post("/chat/{thread_key}/continue")
async def chat_continue(
    thread_key: str,
    body: schemas.ChatContinueIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Resolve a confirmed structural action (checkout/restore), then let the agent
    keep going in the same conversation — so a permission prompt doesn't dead-end."""
    limits.chat_rate.hit(user.id, detail="Too many assistant requests. Please slow down.")
    key = await repo.get_config(session, user.id, KEY_API)
    if not key:
        raise HTTPException(400, "No Claude API key or token configured. Add one in Settings.")

    outcome = f"The user declined the {body.tool}."
    if body.approved:
        v = int(body.args.get("version", 0))
        if body.tool == "checkout":
            ok = await services.set_current(session, user.id, v)
            outcome = f"Checkout done — HEAD is now v{v:04d}." if ok else f"Checkout failed — v{v:04d} not found."
        elif body.tool == "restore":
            row = await services.restore(session, user.id, v)
            outcome = (f"Restored v{v:04d} as new commit v{row.version:04d}." if row
                       else f"Restore failed — v{v:04d} not found.")
        else:
            outcome = f"Unknown action '{body.tool}'."
        await session.commit()

    baseline, head = await _agent_context(session, user.id)
    model = body.model or await repo.get_config(session, user.id, KEY_MODEL)
    prior = await repo.list_messages(session, user.id, thread_key)
    history = [{"role": m.role, "content": m.content} for m in prior if m.content]
    # Ephemeral context (not persisted as a user turn) — the outcome + a nudge to continue.
    note = (f"(System note, not from the user: {outcome}) Acknowledge in one short line and "
            "continue helping. Do NOT call that same action again.")
    return _agent_stream(
        thread_key=thread_key, uid=user.id, key=key, model=model, baseline=baseline,
        head=head, history=history, user_message=note, current_data=body.current_data,
    )


# ── PDF ──────────────────────────────────────────────────────────────────────
async def _compile(data: dict, user_id: int) -> bytes:
    # Per-user rate limit + one in-flight compile per user (so a single user
    # can't monopolize the global pdflatex slots), then the global cap.
    limits.compile_rate.hit(
        user_id, detail="Too many PDF compiles. Please wait a moment and retry."
    )
    lock = limits.user_compile_lock(user_id)
    if lock.locked():
        raise HTTPException(429, "A PDF compile is already in progress. Please wait.")
    async with lock:
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
    pdf = await _compile(row.data, user.id)
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
    pdf = await _compile(data, user.id)
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
    pdf = await _compile(row.data, user.id)
    return _pdf_response(pdf, compute_archive_name(row.data, cur))


# ── Prompts (copy-paste fallback) ────────────────────────────────────────────
@router.get("/prompts/onboarding")
async def prompt_onboarding():
    return {"prompt": prompts.ONBOARDING_PROMPT}


@router.get("/prompts/onboarding-build")
async def prompt_onboarding_build():
    return {"prompt": prompts.ONBOARDING_BUILD_PROMPT}


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


@router.post("/prompts/copy")
async def prompt_copy(
    body: schemas.CopyPromptIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Full, ready-to-paste prompt for one keyless intent (JD/note injected)."""
    if body.intent not in prompts.COPY_INTENTS:
        raise HTTPException(422, f"unknown intent {body.intent!r}")
    base = await repo.latest_base_version(session, user.id)
    if base is None:
        raise HTTPException(400, "No base resume yet.")
    baseline = (await repo.get_version(session, user.id, base)).data
    return {
        "prompt": prompts.build_oneshot_prompt(
            baseline, body.intent, jd_text=body.jd_text, note=body.note
        )
    }


@router.post("/paste/preview", response_model=schemas.PastePreviewOut)
async def paste_preview(
    body: schemas.PastePreviewIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Turn a pasted Claude reply into a reviewable diff.

    Fence-strips + schema-validates the JSON and diffs it against the current
    baseline (empty if none yet, e.g. the keyless onboarding bootstrap). The
    caller commits the returned ``data`` via ``/api/base`` or ``/api/tailor``.
    """
    from core.schema import SchemaError
    try:
        data = ai.extract_json(body.text)
    except ai.AIError as e:
        raise HTTPException(422, {"error": str(e), "raw": e.raw})
    try:
        data = schema.validate(data)  # returns data normalized to the section model
    except SchemaError as e:
        raise HTTPException(422, {"problems": e.problems})

    base = await repo.latest_base_version(session, user.id)
    baseline = (
        (await repo.get_version(session, user.id, base)).data
        if base is not None else {"personal": {}, "sections": []}
    )
    return schemas.PastePreviewOut(
        data=data,
        diff=diff_lines(baseline, data),
        summary=summarize_changes(baseline, data),
    )
