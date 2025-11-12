"""Heading block definition."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class HeadingProps(BlockProperties):
    level: int = Field(default=2, ge=1, le=6)
    groups: tuple[UUID, ...] = Field(default_factory=tuple)


class HeadingBlock(Block):
    type: BlockType = Field(default=BlockType.HEADING, frozen=True)
    properties: HeadingProps = Field(default_factory=HeadingProps)


__all__ = ["HeadingBlock", "HeadingProps"]
