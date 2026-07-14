"""Pydantic request/response models for the API."""

from __future__ import annotations

from pydantic import BaseModel


class Me(BaseModel):
    email: str
    ai_enabled: bool
    default_model: str


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
