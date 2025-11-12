"""Dataset block definition."""

from __future__ import annotations

import warnings
from typing import Any

from pydantic import ConfigDict, Field

from .base import Block, BlockProperties, BlockType

warnings.filterwarnings(
    "ignore",
    message='Field name "schema" in "DatasetProps" shadows an attribute in parent "BlockProperties"',
)


class DatasetProps(BlockProperties):
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    title: str | None = None
    schema: dict[str, Any] | None = None
    category: str | None = Field(default=None, alias="dataset_type")

    @property
    def dataset_type(self) -> str | None:  # pragma: no cover - compatibility shim
        return self.category


class DatasetBlock(Block):
    type: BlockType = Field(default=BlockType.DATASET, frozen=True)
    properties: DatasetProps


__all__ = ["DatasetBlock", "DatasetProps"]
