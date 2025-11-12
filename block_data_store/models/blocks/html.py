"""HTML block definition."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class HtmlProps(BlockProperties):
    groups: tuple[UUID, ...] = Field(default_factory=tuple)


class HtmlBlock(Block):
    type: BlockType = Field(default=BlockType.HTML, frozen=True)
    properties: HtmlProps = Field(default_factory=HtmlProps)


__all__ = ["HtmlBlock", "HtmlProps"]
