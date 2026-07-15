"""Pydantic request/response models for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Upper bounds on free-text inputs, so unbounded Text columns can't be stuffed.
MAX_JD_LEN = 20_000
MAX_MESSAGE_LEN = 12_000


class Me(BaseModel):
    email: str
    ai_enabled: bool
    default_model: str
    credential_kind: str | None = None  # "api" | "oauth" | None (no credential set)
    display_name: str | None = None     # account display name (users.display_name)
    created_at: str | None = None        # ISO8601, "member since"


class VersionMeta(BaseModel):
    version: int
    created_at: str
    label: str | None
    is_base: bool
    forked_from: int | None
    json_hash: str


class VersionDetail(VersionMeta):
    jd_text: str | None
    data: dict


class BaseIn(BaseModel):
    data: dict
    label: str | None = None


class TailorIn(BaseModel):
    data: dict
    label: str | None = None
    jd_text: str | None = Field(default=None, max_length=MAX_JD_LEN)


class TailorPreviewIn(BaseModel):
    jd_text: str = Field(max_length=MAX_JD_LEN)
    model: str | None = None


class TailorPreviewOut(BaseModel):
    data: dict
    diff: list[dict]
    summary: list[str]


class SetCurrentIn(BaseModel):
    version: int


class DiffOut(BaseModel):
    summary: list[str]
    lines: list[dict]


class SettingsIn(BaseModel):
    default_model: str | None = None
    ai_enabled: bool | None = None
    display_name: str | None = Field(default=None, max_length=200)


class ApiKeyIn(BaseModel):
    api_key: str


class ImportIn(BaseModel):
    versions: list[dict]
    current_version: int | None = None
    replace: bool = False


class PreviewIn(BaseModel):
    data: dict


# ── Copy-paste (keyless) assistant ────────────────────────────────────────────
class CopyPromptIn(BaseModel):
    intent: str  # "tailor" | "base-update" | "ask" | "ats"
    jd_text: str | None = Field(default=None, max_length=MAX_JD_LEN)
    note: str | None = Field(default=None, max_length=MAX_MESSAGE_LEN)


class PastePreviewIn(BaseModel):
    text: str = Field(max_length=200_000)  # a pasted Claude reply (JSON + maybe prose)
    intent: str = "base-update"  # "tailor" -> diff vs base; else diff vs base too


class PastePreviewOut(BaseModel):
    data: dict
    diff: list[dict]
    summary: list[str]


# ── Resume Copilot chat ───────────────────────────────────────────────────────
class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    proposal: dict | None = None
    created_at: str


class ChatSendIn(BaseModel):
    message: str = Field(max_length=MAX_MESSAGE_LEN)
    model: str | None = None
    current_data: dict | None = None  # the resume in the editor (viewed branch)
    skill: str | None = None


class ChatContinueIn(BaseModel):
    tool: str                        # "checkout" | "restore"
    args: dict
    approved: bool
    model: str | None = None
    current_data: dict | None = None


class SkillOut(BaseModel):
    name: str
    description: str
