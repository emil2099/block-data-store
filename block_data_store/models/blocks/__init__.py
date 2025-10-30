"""Typed block exports and helpers."""

from __future__ import annotations

from typing import Annotated, Union

from pydantic import Field

from .base import Block, BlockProperties, BlockType, Content
from .chunk_group import ChunkGroupBlock, ChunkGroupProps
from .dataset import DatasetBlock, DatasetProps
from .document import DocumentBlock, DocumentProps
from .heading import HeadingBlock, HeadingProps
from .list_item import BulletedListItemBlock, ListItemProps, NumberedListItemBlock
from .page import PageBlock, PageProps
from .page_group import PageGroupBlock, PageGroupProps
from .paragraph import ParagraphBlock, ParagraphProps
from .record import RecordBlock, RecordProps
from .synced import SyncedBlock, SyncedProps

AnyBlock = Annotated[
    Union[
        DocumentBlock,
        HeadingBlock,
        ParagraphBlock,
        BulletedListItemBlock,
        NumberedListItemBlock,
        DatasetBlock,
        RecordBlock,
        PageGroupBlock,
        ChunkGroupBlock,
        PageBlock,
        SyncedBlock,
    ],
    Field(discriminator="type"),
]

BLOCK_CLASS_MAP = {
    BlockType.DOCUMENT: DocumentBlock,
    BlockType.HEADING: HeadingBlock,
    BlockType.PARAGRAPH: ParagraphBlock,
    BlockType.BULLETED_LIST_ITEM: BulletedListItemBlock,
    BlockType.NUMBERED_LIST_ITEM: NumberedListItemBlock,
    BlockType.DATASET: DatasetBlock,
    BlockType.RECORD: RecordBlock,
    BlockType.PAGE_GROUP: PageGroupBlock,
    BlockType.CHUNK_GROUP: ChunkGroupBlock,
    BlockType.PAGE: PageBlock,
    BlockType.SYNCED: SyncedBlock,
}

PROPERTIES_CLASS_MAP = {
    BlockType.DOCUMENT: DocumentProps,
    BlockType.HEADING: HeadingProps,
    BlockType.PARAGRAPH: ParagraphProps,
    BlockType.BULLETED_LIST_ITEM: ListItemProps,
    BlockType.NUMBERED_LIST_ITEM: ListItemProps,
    BlockType.DATASET: DatasetProps,
    BlockType.RECORD: RecordProps,
    BlockType.PAGE_GROUP: PageGroupProps,
    BlockType.CHUNK_GROUP: ChunkGroupProps,
    BlockType.PAGE: PageProps,
    BlockType.SYNCED: SyncedProps,
}


def block_class_for(block_type: BlockType | str) -> type[Block]:
    normalized = BlockType(block_type) if not isinstance(block_type, BlockType) else block_type
    return BLOCK_CLASS_MAP.get(normalized, Block)


def properties_model_for(block_type: BlockType | str) -> type[BlockProperties]:
    normalized = BlockType(block_type) if not isinstance(block_type, BlockType) else block_type
    return PROPERTIES_CLASS_MAP.get(normalized, BlockProperties)


__all__ = [
    "AnyBlock",
    "Block",
    "BlockProperties",
    "BlockType",
    "Content",
    "DocumentBlock",
    "DocumentProps",
    "HeadingBlock",
    "HeadingProps",
    "ParagraphBlock",
    "ParagraphProps",
    "BulletedListItemBlock",
    "NumberedListItemBlock",
    "ListItemProps",
    "DatasetBlock",
    "DatasetProps",
    "RecordBlock",
    "RecordProps",
    "PageGroupBlock",
    "PageGroupProps",
    "ChunkGroupBlock",
    "ChunkGroupProps",
    "PageBlock",
    "PageProps",
    "SyncedBlock",
    "SyncedProps",
    "block_class_for",
    "properties_model_for",
]
