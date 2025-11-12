"""Derived content container block definition."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class DerivedContentContainerProps(BlockProperties):
    category: str


class DerivedContentContainerBlock(Block):
    type: BlockType = Field(default=BlockType.DERIVED_CONTENT_CONTAINER, frozen=True)
    properties: DerivedContentContainerProps


__all__ = [
    "DerivedContentContainerBlock",
    "DerivedContentContainerProps",
]
