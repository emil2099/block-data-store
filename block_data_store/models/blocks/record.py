"""Record block definition."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class RecordProps(BlockProperties):
    groups: tuple[UUID, ...] = Field(default_factory=tuple)


class RecordBlock(Block):
    type: BlockType = Field(default=BlockType.RECORD, frozen=True)
    properties: RecordProps


__all__ = ["RecordBlock", "RecordProps"]
