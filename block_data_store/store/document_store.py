"""Lightweight orchestration layer that composes repository primitives."""

from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID

from block_data_store.models.block import Block, BlockType
from block_data_store.models.relationship import Relationship
from block_data_store.repositories.block_repository import BlockRepository
from block_data_store.repositories.relationship_repository import RelationshipRepository
from block_data_store.repositories.filters import (
    FilterExpression,
    ParentFilter,
    RootFilter,
    WhereClause,
)


class DocumentStoreError(RuntimeError):
    """Raised when DocumentStore operations encounter invalid state."""


class DocumentStore:
    """Thin façade around the repository that coordinates multi-entity actions."""

    def __init__(
        self,
        repository: BlockRepository,
        relationship_repository: RelationshipRepository,
    ):
        """Internal constructor; prefer ``create_document_store`` for public use."""
        self._repository = repository
        self._relationship_repository = relationship_repository

    # ------------------------------------------------------------------ Queries
    def get_root_tree(
        self,
        root_block_id: UUID,
        *,
        depth: int | None = 1,
        include_trashed: bool = False,
    ) -> Block:
        """Return the main block tree anchored at ``root_block_id``."""
        root_block = self._require_block(root_block_id, depth=depth, include_trashed=include_trashed)
        if root_block.type not in {BlockType.DOCUMENT, BlockType.DATASET}:
            raise DocumentStoreError(f"Block {root_block_id} is not a supported root type.")
        return root_block

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
        root: RootFilter | None = None,
        limit: int | None = None,
    ) -> list[Block]:
        """Delegate block queries so higher layers only depend on the store."""
        return self._repository.query_blocks(
            where=where,
            property_filter=property_filter,
            parent=parent,
            root=root,
            limit=limit,
        )

    def get_relationships(
        self,
        block_id: UUID,
        direction: str = "all",
        include_trashed: bool = False,
    ) -> list[Relationship]:
        """Get relationships for a block."""
        return self._relationship_repository.get_relationships(
            block_id, direction=direction, include_trashed=include_trashed
        )

    # ----------------------------------------------------------- Mutating ops
    def upsert_relationships(self, relationships: Sequence[Relationship]) -> None:
        """Batch insert or update relationships."""
        self._relationship_repository.upsert_relationships(relationships)

    def delete_relationships(
        self,
        keys: Sequence[tuple[UUID, UUID, str]],
    ) -> bool:
        """Batch delete relationships."""
        return self._relationship_repository.delete_relationships(keys)

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

    def upsert_blocks(
        self,
        blocks: Sequence[Block],
        *,
        parent_id: UUID | None = None,
        insert_after: UUID | None = None,
        top_level_only: bool = True,
    ) -> None:
        """Persist blocks and, optionally, attach top-level ones to a parent."""
        if not blocks:
            return

        if parent_id is None:
            self._repository.upsert_blocks(blocks)
            return  # pure upsert

        parent = self._require_block(parent_id)

        # Identify which blocks become direct children
        if top_level_only:
            block_ids_set = {b.id for b in blocks}
            blocks_to_append = [
                b for b in blocks
                if b.parent_id is None or b.parent_id not in block_ids_set
            ]
        else:
            blocks_to_append = list(blocks)

        append_ids = {b.id for b in blocks_to_append}
        updated_blocks = []

        for block in blocks:
            if block.id in append_ids:
                # Attach to parent; preserve existing root_id if present
                new_root = block.root_id or parent.root_id
                updated_blocks.append(
                    block.model_copy(update={
                        "parent_id": parent_id,
                        "root_id": new_root,
                    })
                )
            else:
                # Keep existing hierarchy for nested blocks
                updated_blocks.append(block)

        # Persist all blocks first
        self._repository.upsert_blocks(updated_blocks)

        # Refresh parent to get latest version/children
        parent_fresh = self._require_block(parent_id)
        current_children = list(parent_fresh.children_ids)
        new_child_ids = [b.id for b in blocks_to_append]

        if insert_after is None:
            # Append to end
            updated_children = current_children + new_child_ids
        else:
            # Insert after specified block
            try:
                insert_index = current_children.index(insert_after) + 1
            except ValueError:
                raise DocumentStoreError(
                    f"insert_after block {insert_after} not found in parent {parent_id}'s children"
                )
            updated_children = (
                current_children[:insert_index]
                + new_child_ids
                + current_children[insert_index:]
            )

        # Structural update with optimistic concurrency and validation
        self._repository.set_children(
            parent_id,
            updated_children,
            expected_version=parent_fresh.version,
        )



    def set_in_trash(self, block_ids: Sequence[UUID], *, in_trash: bool) -> None:
        """Toggle the trash flag for supplied blocks and their descendants."""
        if not block_ids:
            return

        self._repository.set_in_trash(block_ids, in_trash=in_trash, cascade=True)

    def get_block(
        self,
        block_id: UUID,
        *,
        depth: int | None = 0,
        include_trashed: bool = False,
    ) -> Block | None:
        """Fetch an individual block via the store."""
        return self._repository.get_block(block_id, depth=depth, include_trashed=include_trashed)

    # ----------------------------------------------------------------- Helpers
    def _require_block(
        self,
        block_id: UUID,
        *,
        depth: int | None = 0,
        include_trashed: bool = False,
    ) -> Block:
        block = self._repository.get_block(block_id, depth=depth, include_trashed=include_trashed)
        if block is None:
            raise DocumentStoreError(f"Block {block_id} does not exist.")
        return block

__all__ = [
    "DocumentStore",
    "DocumentStoreError",
]
