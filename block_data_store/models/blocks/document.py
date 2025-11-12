"""Document block definition."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class DocumentProps(BlockProperties):
    title: str | None = None
    category: str | None = None


class DocumentBlock(Block):
    type: BlockType = Field(default=BlockType.DOCUMENT, frozen=True)
    properties: DocumentProps


__all__ = ["DocumentBlock", "DocumentProps"]
