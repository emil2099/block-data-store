"""Object block definition."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class ObjectProps(BlockProperties):
    category: str | None = None
    groups: list[UUID] = Field(default_factory=list)


class ObjectBlock(Block):
    type: BlockType = Field(default=BlockType.OBJECT, frozen=True)
    properties: ObjectProps = Field(default_factory=ObjectProps)


__all__ = ["ObjectBlock", "ObjectProps"]
