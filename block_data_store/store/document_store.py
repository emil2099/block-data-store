"""Lightweight orchestration layer that composes repository primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, cast
from uuid import UUID

from block_data_store.models.block import (
    Block,
    BlockType,
    PageGroupBlock,
    SyncedBlock,
)
from block_data_store.repositories.block_repository import BlockRepository
from block_data_store.repositories.filters import (
    FilterExpression,
    ParentFilter,
    WhereClause,
)


class DocumentStoreError(RuntimeError):
    """Raised when DocumentStore operations encounter invalid state."""


@dataclass(frozen=True)
class ResolvedSyncedChild:
    """Pair a synced block with the canonical block it references."""

    synced: SyncedBlock
    target: Block


@dataclass(frozen=True)
class PageGroupView:
    """Materialised view of a page group and its resolved children."""

    page_group: PageGroupBlock
    synced_children: list[SyncedBlock]
    resolved_children: list[ResolvedSyncedChild]


class DocumentStore:
    """Thin façade around the repository that coordinates multi-entity actions."""

    def __init__(self, repository: BlockRepository):
        """Internal constructor; prefer ``create_document_store`` for public use."""
        self._repository = repository

    # ------------------------------------------------------------------ Queries
    def get_root_tree(
        self,
        root_block_id: UUID,
        *,
        depth: int | None = 1,
    ) -> Block:
        """Return the main block tree anchored at ``root_block_id``."""
        root_block = self._require_block(root_block_id, depth=depth)
        if root_block.type is not BlockType.DOCUMENT:
            raise DocumentStoreError(f"Block {root_block_id} is not a document root.")
        return root_block

    def get_slice(
        self,
        slice_id: UUID,
        *,
        depth: int | None = 1,
        resolve_synced: bool = True,
        target_depth: int | None = 1,
    ) -> PageGroupView:
        """Return a page-group slice along with its (optionally resolved) entries."""
        slice_block = self._require_block(slice_id, depth=depth)
        if slice_block.type is not BlockType.PAGE_GROUP:
            raise DocumentStoreError(f"Block {slice_id} is not a slice (page group).")
        page_group = cast(PageGroupBlock, slice_block)

        synced_children: list[SyncedBlock] = []
        for child_id in page_group.children_ids:
            child_block = self._require_block(child_id)
            if child_block.type is not BlockType.SYNCED:
                raise DocumentStoreError(
                    f"Slice {slice_id} has non-synced child {child_id}."
                )
            synced_children.append(cast(SyncedBlock, child_block))

        resolved_children: list[ResolvedSyncedChild] = []
        if resolve_synced:
            for synced_child in synced_children:
                target_block = self._resolve_synced_block(synced_child, depth=target_depth)
                resolved_children.append(
                    ResolvedSyncedChild(synced=synced_child, target=target_block)
                )

        return PageGroupView(
        page_group=page_group,
            synced_children=synced_children,
            resolved_children=resolved_children,
        )

    def list_documents(self, *, limit: int | None = None) -> list[Block]:
        """Return canonical documents ordered by repository defaults."""
        where = WhereClause(type=BlockType.DOCUMENT)
        return self._repository.query_blocks(where=where, limit=limit)

    def query_blocks(
        self,
        *,
        where: WhereClause | None = None,
        property_filter: FilterExpression | None = None,
        parent: ParentFilter | None = None,
        limit: int | None = None,
    ) -> list[Block]:
        """Delegate block queries so higher layers only depend on the store."""
        return self._repository.query_blocks(
            where=where,
            property_filter=property_filter,
            parent=parent,
            limit=limit,
        )

    # ----------------------------------------------------------- Mutating ops
    def set_children(
        self,
        parent_id: UUID,
        children_ids: Sequence[UUID],
        *,
        expected_version: int | None = None,
    ) -> None:
        """Replace ``parent_id`` children, auto-filling version when omitted."""
        version = (
            expected_version
            if expected_version is not None
            else self._require_block(parent_id).version
        )
        self._repository.set_children(parent_id, children_ids, expected_version=version)

    def move_block(
        self,
        block_id: UUID,
        new_parent_id: UUID,
        index: int,
        *,
        block_version: int | None = None,
        new_parent_version: int | None = None,
        old_parent_version: int | None = None,
    ) -> None:
        """Move ``block_id`` under ``new_parent_id`` at ``index`` with version defaults."""
        block = self._require_block(block_id)
        new_parent = self._require_block(new_parent_id)

        resolved_block_version = block.version if block_version is None else block_version
        resolved_new_parent_version = (
            new_parent.version if new_parent_version is None else new_parent_version
        )

        resolved_old_parent_version = old_parent_version
        if resolved_old_parent_version is None and block.parent_id is not None:
            resolved_old_parent_version = self._require_block(block.parent_id).version

        self._repository.move_block(
            block_id,
            new_parent_id,
            index,
            expected_block_version=resolved_block_version,
            expected_new_parent_version=resolved_new_parent_version,
            expected_old_parent_version=resolved_old_parent_version,
        )

    def save_blocks(self, blocks: Sequence[Block]) -> None:
        """Persist a collection of blocks (documents or fragments)."""
        if not blocks:
            return
        self._repository.upsert_blocks(blocks)

    def get_block(self, block_id: UUID, *, depth: int | None = 0) -> Block | None:
        """Fetch an individual block via the store."""
        return self._repository.get_block(block_id, depth=depth)

    # ----------------------------------------------------------------- Helpers
    def _resolve_synced_block(
        self,
        synced_block: SyncedBlock,
        *,
        depth: int | None = 0,
    ) -> Block:
        target_id = self._synced_target_id(synced_block)
        target = self._repository.get_block(target_id, depth=depth)
        if target is None:
            raise DocumentStoreError(
                f"Synced block {synced_block.id} references missing block {target_id}."
            )
        return target

    @staticmethod
    def _synced_target_id(synced_block: SyncedBlock) -> UUID:
        if synced_block.content and synced_block.content.synced_from:
            return synced_block.content.synced_from
        synced_from_prop = getattr(synced_block.properties, "synced_from", None)
        if synced_from_prop is not None:
            return synced_from_prop
        raise DocumentStoreError(
            f"Synced block {synced_block.id} does not provide a reference to canonical content."
        )

    def _require_block(self, block_id: UUID, *, depth: int | None = 0) -> Block:
        block = self._repository.get_block(block_id, depth=depth)
        if block is None:
            raise DocumentStoreError(f"Block {block_id} does not exist.")
        return block


__all__ = [
    "DocumentStore",
    "DocumentStoreError",
    "PageGroupView",
    "ResolvedSyncedChild",
]
