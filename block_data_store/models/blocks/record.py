"""Record block definition."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class RecordProps(BlockProperties):
    pass


class RecordBlock(Block):
    type: BlockType = Field(default=BlockType.RECORD, frozen=True)
    properties: RecordProps


__all__ = ["RecordBlock", "RecordProps"]
