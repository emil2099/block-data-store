"""Dataset block definition."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from .base import Block, BlockProperties, BlockType


class DatasetProps(BlockProperties):
    model_config = ConfigDict(protected_namespaces=())

    title: str | None = None
    data_schema: dict[str, Any] | None = None
    category: str | None = None


class DatasetBlock(Block):
    type: BlockType = Field(default=BlockType.DATASET, frozen=True)
    properties: DatasetProps


__all__ = ["DatasetBlock", "DatasetProps"]
