"""Typed block exports and helpers."""

from __future__ import annotations

from typing import Annotated, Union

from pydantic import Field

from .base import Block, BlockProperties, BlockType, Content
from .code import CodeBlock, CodeProps
from .collection import CollectionBlock, CollectionProps
from .chunk_group import ChunkGroupBlock, ChunkGroupProps
from .dataset import DatasetBlock, DatasetProps
from .derived_content_container import (
    DerivedContentContainerBlock,
    DerivedContentContainerProps,
)
from .document import DocumentBlock, DocumentProps
from .group_index import GroupIndexBlock, GroupIndexProps
from .heading import HeadingBlock, HeadingProps
from .html import HtmlBlock, HtmlProps
from .list_item import BulletedListItemBlock, ListItemProps, NumberedListItemBlock
from .object_block import ObjectBlock, ObjectProps
from .page_group import PageGroupBlock, PageGroupProps
from .paragraph import ParagraphBlock, ParagraphProps
from .quote import QuoteBlock, QuoteProps
from .record import RecordBlock, RecordProps
from .table import TableBlock, TableProps
from .unsupported import UnsupportedBlock, UnsupportedProps
from .system_container import SystemContainerBlock, SystemContainerProps
from .workspace import WorkspaceBlock, WorkspaceProps

AnyBlock = Annotated[
    Union[
        WorkspaceBlock,
        CollectionBlock,
        DocumentBlock,
        DatasetBlock,
        DerivedContentContainerBlock,
        HeadingBlock,
        ParagraphBlock,
        BulletedListItemBlock,
        NumberedListItemBlock,
        QuoteBlock,
        CodeBlock,
        TableBlock,
        HtmlBlock,
        ObjectBlock,
        RecordBlock,
        GroupIndexBlock,
        PageGroupBlock,
        ChunkGroupBlock,
        SystemContainerBlock,
        UnsupportedBlock,
    ],
    Field(discriminator="type"),
]

BLOCK_CLASS_MAP = {
    BlockType.WORKSPACE: WorkspaceBlock,
    BlockType.COLLECTION: CollectionBlock,
    BlockType.DOCUMENT: DocumentBlock,
    BlockType.DATASET: DatasetBlock,
    BlockType.DERIVED_CONTENT_CONTAINER: DerivedContentContainerBlock,
    BlockType.HEADING: HeadingBlock,
    BlockType.PARAGRAPH: ParagraphBlock,
    BlockType.BULLETED_LIST_ITEM: BulletedListItemBlock,
    BlockType.NUMBERED_LIST_ITEM: NumberedListItemBlock,
    BlockType.RECORD: RecordBlock,
    BlockType.QUOTE: QuoteBlock,
    BlockType.CODE: CodeBlock,
    BlockType.TABLE: TableBlock,
    BlockType.HTML: HtmlBlock,
    BlockType.OBJECT: ObjectBlock,
    BlockType.GROUP_INDEX: GroupIndexBlock,
    BlockType.PAGE_GROUP: PageGroupBlock,
    BlockType.CHUNK_GROUP: ChunkGroupBlock,
    BlockType.SYSTEM_CONTAINER: SystemContainerBlock,
    BlockType.UNSUPPORTED: UnsupportedBlock,
}

PROPERTIES_CLASS_MAP = {
    BlockType.WORKSPACE: WorkspaceProps,
    BlockType.COLLECTION: CollectionProps,
    BlockType.DOCUMENT: DocumentProps,
    BlockType.DATASET: DatasetProps,
    BlockType.DERIVED_CONTENT_CONTAINER: DerivedContentContainerProps,
    BlockType.HEADING: HeadingProps,
    BlockType.PARAGRAPH: ParagraphProps,
    BlockType.BULLETED_LIST_ITEM: ListItemProps,
    BlockType.NUMBERED_LIST_ITEM: ListItemProps,
    BlockType.RECORD: RecordProps,
    BlockType.QUOTE: QuoteProps,
    BlockType.CODE: CodeProps,
    BlockType.TABLE: TableProps,
    BlockType.HTML: HtmlProps,
    BlockType.OBJECT: ObjectProps,
    BlockType.GROUP_INDEX: GroupIndexProps,
    BlockType.PAGE_GROUP: PageGroupProps,
    BlockType.CHUNK_GROUP: ChunkGroupProps,
    BlockType.SYSTEM_CONTAINER: SystemContainerProps,
    BlockType.UNSUPPORTED: UnsupportedProps,
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
    "WorkspaceBlock",
    "WorkspaceProps",
    "CollectionBlock",
    "CollectionProps",
    "DocumentBlock",
    "DocumentProps",
    "DatasetBlock",
    "DatasetProps",
    "DerivedContentContainerBlock",
    "DerivedContentContainerProps",
    "HeadingBlock",
    "HeadingProps",
    "ParagraphBlock",
    "ParagraphProps",
    "BulletedListItemBlock",
    "NumberedListItemBlock",
    "ListItemProps",
    "QuoteBlock",
    "QuoteProps",
    "CodeBlock",
    "CodeProps",
    "TableBlock",
    "TableProps",
    "HtmlBlock",
    "HtmlProps",
    "ObjectBlock",
    "ObjectProps",
    "RecordBlock",
    "RecordProps",
    "GroupIndexBlock",
    "GroupIndexProps",
    "PageGroupBlock",
    "PageGroupProps",
    "ChunkGroupBlock",
    "ChunkGroupProps",
    "SystemContainerBlock",
    "SystemContainerProps",
    "UnsupportedBlock",
    "UnsupportedProps",
    "block_class_for",
    "properties_model_for",
]
