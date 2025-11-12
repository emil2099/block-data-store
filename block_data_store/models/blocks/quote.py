"""Quote block definition."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class QuoteProps(BlockProperties):
    groups: tuple[UUID, ...] = Field(default_factory=tuple)


class QuoteBlock(Block):
    type: BlockType = Field(default=BlockType.QUOTE, frozen=True)
    properties: QuoteProps = Field(default_factory=QuoteProps)


__all__ = ["QuoteBlock", "QuoteProps"]
