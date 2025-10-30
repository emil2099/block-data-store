"""Dataset block definition."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class DatasetProps(BlockProperties):
    dataset_type: str | None = None


class DatasetBlock(Block):
    type: BlockType = Field(default=BlockType.DATASET, frozen=True)
    properties: DatasetProps


__all__ = ["DatasetBlock", "DatasetProps"]
