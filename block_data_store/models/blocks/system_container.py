"""System container block definition."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class SystemContainerProps(BlockProperties):
    category: str


class SystemContainerBlock(Block):
    type: BlockType = Field(default=BlockType.SYSTEM_CONTAINER, frozen=True)
    properties: SystemContainerProps


__all__ = [
    "SystemContainerBlock",
    "SystemContainerProps",
]
