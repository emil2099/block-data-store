"""Page block definition."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class PageProps(BlockProperties):
    title: str | None = None


class PageBlock(Block):
    type: BlockType = Field(default=BlockType.PAGE, frozen=True)
    properties: PageProps


__all__ = ["PageBlock", "PageProps"]
