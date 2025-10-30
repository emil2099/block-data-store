"""Paragraph block definition."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class ParagraphProps(BlockProperties):
    pass


class ParagraphBlock(Block):
    type: BlockType = Field(default=BlockType.PARAGRAPH, frozen=True)
    properties: ParagraphProps


__all__ = ["ParagraphBlock", "ParagraphProps"]
