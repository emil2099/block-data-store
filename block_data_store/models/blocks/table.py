"""Table block definition."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class TableProps(BlockProperties):
    groups: list[UUID] = Field(default_factory=list)


class TableBlock(Block):
    type: BlockType = Field(default=BlockType.TABLE, frozen=True)
    properties: TableProps = Field(default_factory=TableProps)


__all__ = ["TableBlock", "TableProps"]
