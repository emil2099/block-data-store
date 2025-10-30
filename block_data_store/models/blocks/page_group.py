"""Page group block definition."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class PageGroupProps(BlockProperties):
    title: str | None = None


class PageGroupBlock(Block):
    type: BlockType = Field(default=BlockType.PAGE_GROUP, frozen=True)
    properties: PageGroupProps


__all__ = ["PageGroupBlock", "PageGroupProps"]
