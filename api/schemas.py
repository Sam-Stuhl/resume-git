"""Pydantic request/response models for the API."""

from __future__ import annotations

from pydantic import BaseModel


class Me(BaseModel):
    email: str
    ai_enabled: bool
    default_model: str
    credential_kind: str | None = None  # "api" | "oauth" | None (no credential set)


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
    jd_text: str | None = None


class TailorPreviewIn(BaseModel):
    jd_text: str
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


class ApiKeyIn(BaseModel):
    api_key: str


class ImportIn(BaseModel):
    versions: list[dict]
    current_version: int | None = None
    replace: bool = False


class PreviewIn(BaseModel):
    data: dict


# ── Resume Copilot chat ───────────────────────────────────────────────────────
class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    proposal: dict | None = None
    created_at: str


class ChatSendIn(BaseModel):
    message: str
    model: str | None = None
    current_data: dict | None = None  # the resume in the editor (viewed branch)
