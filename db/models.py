"""SQLAlchemy 2.0 models — mirrors the console's stack (async SQLAlchemy).

Data is scoped per user. Resume JSON lives in the ``versions.data`` column (no
files), and PDFs are never stored — they are recompiled on demand from ``data``.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    versions: Mapped[list["Version"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Version(Base):
    __tablename__ = "versions"
    __table_args__ = (UniqueConstraint("user_id", "version", name="uq_user_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    json_hash: Mapped[str] = mapped_column(String(32))
    is_base: Mapped[bool] = mapped_column(Boolean, default=False)
    forked_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data: Mapped[dict] = mapped_column(JSON)

    user: Mapped["User"] = relationship(back_populates="versions")


class Config(Base):
    __tablename__ = "config"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
