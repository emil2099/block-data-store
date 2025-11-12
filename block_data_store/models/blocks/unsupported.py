"""Unsupported block definition."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class UnsupportedProps(BlockProperties):
    pass


class UnsupportedBlock(Block):
    type: BlockType = Field(default=BlockType.UNSUPPORTED, frozen=True)
    properties: UnsupportedProps = Field(default_factory=UnsupportedProps)


__all__ = ["UnsupportedBlock", "UnsupportedProps"]
