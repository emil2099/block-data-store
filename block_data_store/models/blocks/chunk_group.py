"""Chunk group block definition."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class ChunkGroupProps(BlockProperties):
    title: str | None = None


class ChunkGroupBlock(Block):
    type: BlockType = Field(default=BlockType.CHUNK_GROUP, frozen=True)
    properties: ChunkGroupProps


__all__ = ["ChunkGroupBlock", "ChunkGroupProps"]
