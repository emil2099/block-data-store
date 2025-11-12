"""Shared building blocks for typed Decipher blocks."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class BlockType(str, Enum):
    WORKSPACE = "workspace"
    COLLECTION = "collection"
    DOCUMENT = "document"
    DATASET = "dataset"
    DERIVED_CONTENT_CONTAINER = "derived_content_container"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    BULLETED_LIST_ITEM = "bulleted_list_item"
    NUMBERED_LIST_ITEM = "numbered_list_item"
    RECORD = "record"
    QUOTE = "quote"
    CODE = "code"
    TABLE = "table"
    HTML = "html"
    OBJECT = "object"
    GROUP_INDEX = "group_index"
    PAGE_GROUP = "page_group"
    CHUNK_GROUP = "chunk_group"
    UNSUPPORTED = "unsupported"


class Content(BaseModel):
    """Simplified multi-part content payload."""

    plain_text: str | None = None
    object: dict[str, Any] | None = None
    data: dict[str, Any] | None = None


class BlockProperties(BaseModel):
    """Base class for typed block properties."""

    model_config = ConfigDict(extra="allow")


ResolveOne = Callable[[UUID | None], "Block | None"]
ResolveMany = Callable[[Sequence[UUID]], list["Block"]]


class Block(BaseModel):
    """Immutable representation of a block node."""

    id: UUID
    type: BlockType
    parent_id: UUID | None
    root_id: UUID
    children_ids: tuple[UUID, ...] = Field(default_factory=tuple)
    workspace_id: UUID | None = None
    in_trash: bool = False
    version: int = 0
    created_time: datetime
    last_edited_time: datetime
    created_by: UUID | None = None
    last_edited_by: UUID | None = None
    properties: BlockProperties
    metadata: dict[str, Any] = Field(default_factory=dict)
    content: Content | None = None
    properties_version: int | None = None

    _resolve_one: ResolveOne = PrivateAttr(default=lambda _id: None)
    _resolve_many: ResolveMany = PrivateAttr(default=lambda ids: [])

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    def parent(self) -> Block | None:
        return self._resolve_one(self.parent_id) if self.parent_id else None

    def children(self) -> list[Block]:
        if not self.children_ids:
            return []
        return self._resolve_many(self.children_ids)

    def with_resolvers(
        self,
        *,
        resolve_one: ResolveOne | None = None,
        resolve_many: ResolveMany | None = None,
    ) -> Block:
        clone = self.model_copy()
        if resolve_one is not None:
            object.__setattr__(clone, "_resolve_one", resolve_one)
        if resolve_many is not None:
            object.__setattr__(clone, "_resolve_many", resolve_many)
        return clone


__all__ = ["Block", "BlockProperties", "BlockType", "Content", "ResolveOne", "ResolveMany"]
