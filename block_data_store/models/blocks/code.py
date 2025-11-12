"""Code block definition."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class CodeProps(BlockProperties):
    language: str | None = None
    groups: tuple[UUID, ...] = Field(default_factory=tuple)


class CodeBlock(Block):
    type: BlockType = Field(default=BlockType.CODE, frozen=True)
    properties: CodeProps = Field(default_factory=CodeProps)


__all__ = ["CodeBlock", "CodeProps"]
