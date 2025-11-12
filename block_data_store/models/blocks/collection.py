"""Collection block definition."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class CollectionProps(BlockProperties):
    title: str


class CollectionBlock(Block):
    type: BlockType = Field(default=BlockType.COLLECTION, frozen=True)
    properties: CollectionProps


__all__ = ["CollectionBlock", "CollectionProps"]
