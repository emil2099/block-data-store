"""SQLAlchemy declarative schema for the block data store."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, Integer, String, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql.sqltypes import JSON


class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative mappings."""


class DbBlock(Base):
    """ORM mapping for the canonical block record."""

    __tablename__ = "blocks"
    __table_args__ = (
        # Core structural indexes used in most queries
        Index("ix_blocks_root_type", "root_id", "type"),
        Index("ix_blocks_parent", "parent_id"),
        Index("ix_blocks_workspace_root", "workspace_id", "root_id"),
        Index("ix_blocks_in_trash", "in_trash"),
        # Postgres-specific GIN index for properties JSON (ignored by SQLite)
        Index(
            "ix_blocks_properties_gin",
            "properties",
            postgresql_using="gin",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    root_id: Mapped[str] = mapped_column(String(36), nullable=False)
    children_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    in_trash: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_edited_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_edited_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    content: Mapped[Any] = mapped_column(JSON, nullable=True)
    properties_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


def create_all(engine: Engine) -> None:
    """Create database tables for the schema."""
    Base.metadata.create_all(engine, checkfirst=True)


__all__ = ["Base", "DbBlock", "create_all"]
