"""Synced block definition."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from .base import Block, BlockProperties, BlockType


class SyncedProps(BlockProperties):
    synced_from: UUID | None = None


class SyncedBlock(Block):
    type: BlockType = Field(default=BlockType.SYNCED, frozen=True)
    properties: SyncedProps


__all__ = ["SyncedBlock", "SyncedProps"]
