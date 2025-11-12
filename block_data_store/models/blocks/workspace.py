"""Workspace block definition."""

from __future__ import annotations

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class WorkspaceProps(BlockProperties):
    title: str


class WorkspaceBlock(Block):
    type: BlockType = Field(default=BlockType.WORKSPACE, frozen=True)
    properties: WorkspaceProps


__all__ = ["WorkspaceBlock", "WorkspaceProps"]
