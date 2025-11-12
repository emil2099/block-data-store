"""Paragraph block definition."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class ParagraphProps(BlockProperties):
    groups: list[UUID] = Field(default_factory=list)


class ParagraphBlock(Block):
    type: BlockType = Field(default=BlockType.PARAGRAPH, frozen=True)
    properties: ParagraphProps


__all__ = ["ParagraphBlock", "ParagraphProps"]
