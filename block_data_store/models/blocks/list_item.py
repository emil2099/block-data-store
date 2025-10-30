"""List item block definitions."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class ListItemProps(BlockProperties):
    pass


class BulletedListItemBlock(Block):
    type: BlockType = Field(default=BlockType.BULLETED_LIST_ITEM, frozen=True)
    properties: ListItemProps = Field(default_factory=ListItemProps)


class NumberedListItemBlock(Block):
    type: BlockType = Field(default=BlockType.NUMBERED_LIST_ITEM, frozen=True)
    properties: ListItemProps = Field(default_factory=ListItemProps)


__all__ = ["ListItemProps", "BulletedListItemBlock", "NumberedListItemBlock"]
