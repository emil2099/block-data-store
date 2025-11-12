"""Group index block definition."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class GroupIndexProps(BlockProperties):
    group_index_type: Literal["page", "chunk"]


class GroupIndexBlock(Block):
    type: BlockType = Field(default=BlockType.GROUP_INDEX, frozen=True)
    properties: GroupIndexProps


__all__ = ["GroupIndexBlock", "GroupIndexProps"]
