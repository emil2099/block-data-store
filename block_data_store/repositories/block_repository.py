"""SQLAlchemy-backed repository for Block models."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, aliased, sessionmaker

from block_data_store.db.schema import DbBlock
from block_data_store.models.block import Block, BlockType, Content, block_class_for
from block_data_store.repositories.filters import (
    FilterExpression,
    ParentFilter,
    PropertyFilter,
    RootFilter,
    WhereClause,
    apply_structural_filters,
    build_filter_expression,
)


class RepositoryError(RuntimeError):
    """Base class for repository-level errors."""


class BlockNotFoundError(RepositoryError):
    """Raised when a block cannot be found for a requested operation."""


class VersionConflictError(RepositoryError):
    """Raised when optimistic concurrency checks fail."""


class InvalidChildrenError(RepositoryError):
    """Raised when structural edits violate hierarchy requirements."""


class BlockRepository:
    """Repository that persists and hydrates Block models from the database."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def get_block(
        self,
        block_id: UUID,
        *,
        depth: int | None = 0,
        include_trashed: bool = False,
    ) -> Block | None:
        """Fetch a block by identifier with optional depth prefetch."""
        if depth is not None and depth < 0:
            raise ValueError("Depth must be a non-negative integer or None.")

        with self._session_factory() as session:
            query = session.query(DbBlock).filter(DbBlock.id == str(block_id))
            if not include_trashed:
                query = query.filter(DbBlock.in_trash.is_(False))
            db_row = query.one_or_none()
            if db_row is None:
                return None

            if depth == 0:
                return self._with_resolvers(self._to_model(db_row))

            if depth is None:
                return self._hydrate_full_root(session, db_row, include_trashed)

            cache: dict[UUID, Block] = {}
            self._hydrate_subgraph(
                session,
                db_row,
                depth,
                cache,
                include_trashed=include_trashed,
            )
            wired_cache = self._wire_cache(cache)
            return wired_cache.get(UUID(db_row.id))

    def query_blocks(
        self,
        *,
        where: WhereClause | None = None,
        property_filter: FilterExpression | None = None,
        parent: ParentFilter | None = None,
        root: RootFilter | None = None,
        limit: int | None = None,
        include_trashed: bool = False,
    ) -> list[Block]:
        """Return blocks matching structural and semantic filters."""
        with self._session_factory() as session:
            query = session.query(DbBlock)

            query = self._apply_related_filters(query, relation="root", filter_spec=root)
            query = self._apply_related_filters(query, relation="parent", filter_spec=parent)
            query = self._apply_filters(query, DbBlock, where=where, property_filter=property_filter)

            if not include_trashed:
                query = query.filter(DbBlock.in_trash.is_(False))

            if limit is not None:
                query = query.limit(limit)

            rows = query.all()

        return [self._with_resolvers(self._to_model(row)) for row in rows]

    def upsert_blocks(
        self,
        blocks: Sequence[Block],
    ) -> None:
        """Insert or update blocks in bulk (no structural updates)."""
        if not blocks:
            return

        with self._session_factory() as session:
            payloads = [self._to_record(block) for block in blocks]
            bind = session.get_bind()

            if bind is not None and bind.dialect.name == "postgresql":
                if payloads:
                    stmt = pg_insert(DbBlock).values(payloads)
                    update_cols = {
                        col.name: getattr(stmt.excluded, col.name)
                        for col in DbBlock.__table__.columns
                        if col.name != "id"
                    }
                    session.execute(
                        stmt.on_conflict_do_update(
                            index_elements=[DbBlock.id],
                            set_=update_cols
                        )
                    )
            else:
                for payload in payloads:
                    session.merge(DbBlock(**payload))

            session.commit()

    def set_in_trash(
        self,
        block_ids: Sequence[UUID],
        *,
        in_trash: bool,
        cascade: bool = False,
    ) -> None:
        """Update the trash flag for provided blocks (optionally cascading to descendants)."""
        id_list = [str(block_id) for block_id in block_ids]
        if not id_list:
            return

        with self._session_factory() as session:
            # Ensure all requested roots exist.
            existing_rows = session.query(DbBlock.id).filter(DbBlock.id.in_(id_list)).all()
            existing_ids = {row_id for (row_id,) in existing_rows}
            missing = sorted(block_id for block_id in id_list if block_id not in existing_ids)
            if missing:
                raise BlockNotFoundError(f"Block(s) {missing} do not exist.")

            target_ids = existing_ids if not cascade else self._collect_descendant_ids(session, existing_ids)
            if not target_ids:
                return

            session.query(DbBlock).filter(DbBlock.id.in_(target_ids)).update(
                {
                    DbBlock.in_trash: in_trash,
                    DbBlock.version: DbBlock.version + 1,
                },
                synchronize_session=False,
            )
            session.commit()

    def set_children(
        self,
        parent_id: UUID,
        children_ids: Sequence[UUID],
        *,
        expected_version: int,
    ) -> None:
        """Replace the canonical children for a parent block.

        Validates optimistic concurrency, existence, duplicate IDs, cycles, and root alignment.
        """
        child_uuid_list = list(children_ids)
        if len(child_uuid_list) != len(set(child_uuid_list)):
            raise InvalidChildrenError("Duplicate child identifiers are not allowed.")

        with self._session_factory() as session:
            parent_row = session.get(DbBlock, str(parent_id))
            if parent_row is None:
                raise BlockNotFoundError(f"Parent block {parent_id} does not exist.")
            if parent_row.version != expected_version:
                raise VersionConflictError(
                    f"Parent {parent_id} version mismatch: "
                    f"expected {expected_version}, found {parent_row.version}."
                )

            ancestor_ids = self._collect_ancestor_ids(session, parent_row)
            child_rows: list[DbBlock] = []
            for child_id in child_uuid_list:
                if child_id == parent_id:
                    raise InvalidChildrenError("A block cannot be a child of itself.")
                child_row = session.get(DbBlock, str(child_id))
                if child_row is None:
                    raise InvalidChildrenError(f"Child block {child_id} does not exist.")
                if child_row.id in ancestor_ids:
                    raise InvalidChildrenError(
                        f"Child {child_row.id} would introduce a cycle under parent {parent_row.id}."
                    )
                child_rows.append(child_row)

            new_children_ids_str = [child_row.id for child_row in child_rows]
            current_children_ids_str = list(parent_row.children_ids or [])

            current_children_set = set(current_children_ids_str)
            new_children_set = set(new_children_ids_str)

            # Any children removed from the list have their parent cleared.
            removed_child_ids = current_children_set - new_children_set
            if removed_child_ids:
                for removed_id in removed_child_ids:
                    removed_row = session.get(DbBlock, removed_id)
                    if removed_row is not None and removed_row.parent_id == parent_row.id:
                        removed_row.parent_id = None

            # Update parent references for new/current children in the desired order.
            for child_row in child_rows:
                child_row.parent_id = parent_row.id

            parent_row.children_ids = new_children_ids_str
            parent_row.version += 1

            session.commit()

    def reorder_children(
        self,
        parent_id: UUID,
        new_order: Sequence[UUID],
        *,
        expected_version: int,
    ) -> None:
        """Reorder existing children for the given parent."""
        with self._session_factory() as session:
            parent_row = session.get(DbBlock, str(parent_id))
            if parent_row is None:
                raise BlockNotFoundError(f"Parent block {parent_id} does not exist.")

            current_children_ids = tuple(parent_row.children_ids or [])
            if set(map(str, new_order)) != set(current_children_ids):
                raise InvalidChildrenError(
                    "Reorder operation must reference the same child IDs as currently stored."
                )

        self.set_children(parent_id, new_order, expected_version=expected_version)

    def move_block(
        self,
        block_id: UUID,
        new_parent_id: UUID,
        index: int,
        *,
        expected_block_version: int | None = None,
        expected_new_parent_version: int,
        expected_old_parent_version: int | None = None,
    ) -> None:
        """Move a block to a new parent at a specific index.

        Requires callers to supply optimistic versions for the affected entities.
        """
        with self._session_factory() as session:
            block_row = session.get(DbBlock, str(block_id))
            if block_row is None:
                raise BlockNotFoundError(f"Block {block_id} does not exist.")
            if expected_block_version is not None and block_row.version != expected_block_version:
                raise VersionConflictError(
                    f"Block {block_id} version mismatch: "
                    f"expected {expected_block_version}, found {block_row.version}."
                )

            new_parent_row = session.get(DbBlock, str(new_parent_id))
            if new_parent_row is None:
                raise BlockNotFoundError(f"Target parent {new_parent_id} does not exist.")
            if new_parent_row.version != expected_new_parent_version:
                raise VersionConflictError(
                    f"Parent {new_parent_id} version mismatch: "
                    f"expected {expected_new_parent_version}, found {new_parent_row.version}."
                )

            if new_parent_row.root_id != block_row.root_id:
                raise InvalidChildrenError(
                    f"Cannot move block {block_row.id} from root {block_row.root_id} "
                    f"to parent in root {new_parent_row.root_id}."
                )

            ancestor_ids = self._collect_ancestor_ids(session, new_parent_row)
            if block_row.id in ancestor_ids:
                raise InvalidChildrenError(
                    f"Moving block {block_row.id} under parent {new_parent_row.id} creates a cycle."
                )

            self._move_within_session(
                session,
                block_row,
                new_parent_row=new_parent_row,
                index=index,
                expected_old_parent_version=expected_old_parent_version,
            )

            session.commit()

    def _resolve_one(self, block_id: UUID | None) -> Block | None:
        if block_id is None:
            return None
        return self.get_block(block_id)

    def _resolve_many(self, block_ids: Iterable[UUID]) -> list[Block]:
        resolved: list[Block] = []
        for block_id in block_ids:
            block = self._resolve_one(block_id)
            if block is not None:
                resolved.append(block)
        return resolved

    @staticmethod
    def _to_model(record: DbBlock) -> Block:
        children_raw = record.children_ids or []
        block_type = BlockType(record.type)
        block_cls = block_class_for(block_type)
        content = Content(**record.content) if record.content else None
        return block_cls(
            id=UUID(record.id),
            type=block_type,
            parent_id=UUID(record.parent_id) if record.parent_id else None,
            root_id=UUID(record.root_id),
            children_ids=tuple(UUID(child_id) for child_id in children_raw),
            workspace_id=UUID(record.workspace_id) if record.workspace_id else None,
            in_trash=record.in_trash,
            version=record.version,
            created_time=record.created_time,
            last_edited_time=record.last_edited_time,
            created_by=UUID(record.created_by) if record.created_by else None,
            last_edited_by=UUID(record.last_edited_by) if record.last_edited_by else None,
            properties=record.properties or {},
            metadata=record.metadata_json or {},
            content=content,
            properties_version=record.properties_version,
        )

    @staticmethod
    def _to_record(block: Block) -> dict[str, object]:
        content_payload = (
            block.content.model_dump(mode="json") if block.content else None
        )
        if hasattr(block.properties, "model_dump"):
            properties_payload = block.properties.model_dump(mode="json")
        else:
            properties_payload = _jsonable(block.properties)
        type_value = block.type.value if isinstance(block.type, BlockType) else str(block.type)

        return {
            "id": str(block.id),
            "type": type_value,
            "parent_id": str(block.parent_id) if block.parent_id else None,
            "root_id": str(block.root_id),
            "children_ids": [str(child_id) for child_id in block.children_ids],
            "workspace_id": str(block.workspace_id) if block.workspace_id else None,
            "in_trash": block.in_trash,
            "version": block.version,
            "created_time": block.created_time,
            "last_edited_time": block.last_edited_time,
            "created_by": str(block.created_by) if block.created_by else None,
            "last_edited_by": str(block.last_edited_by) if block.last_edited_by else None,
            "properties": properties_payload,
            "metadata_json": _jsonable(block.metadata),
            "content": content_payload,
            "properties_version": block.properties_version,
        }

    @staticmethod
    def _collect_ancestor_ids(session: Session, block_row: DbBlock) -> set[str]:
        """Return the set of ancestor block ids (including the immediate parent)."""
        ancestors: set[str] = set()
        current_parent_id = block_row.parent_id
        while current_parent_id:
            if current_parent_id in ancestors:
                # Defensive: break potential existing cycles.
                break
            ancestors.add(current_parent_id)
            parent_row = session.get(DbBlock, current_parent_id)
            if parent_row is None:
                break
            current_parent_id = parent_row.parent_id
        return ancestors

    def _move_within_session(
        self,
        session: Session,
        block_row: DbBlock,
        new_parent_row: DbBlock,
        index: int,
        expected_old_parent_version: int | None,
    ) -> None:
        """Execute the move using an existing session transaction."""
        current_parent_id = block_row.parent_id
        if current_parent_id == new_parent_row.id:
            # Pure reorder inside the same parent.
            updated_order = list(new_parent_row.children_ids or [])
            block_id_str = block_row.id
            if block_id_str in updated_order:
                updated_order.remove(block_id_str)
            insertion_index = max(0, min(index, len(updated_order)))
            updated_order.insert(insertion_index, block_id_str)
            # Bypass reorder validation by writing within the same session.
            new_parent_row.children_ids = updated_order
            new_parent_row.version += 1
            block_row.version += 1
            return

        block_id_str = block_row.id

        # Update old parent state if one exists.
        if current_parent_id is not None:
            old_parent_row = session.get(DbBlock, current_parent_id)
            if old_parent_row is None:
                raise BlockNotFoundError(f"Existing parent {current_parent_id} does not exist.")
            if expected_old_parent_version is not None and old_parent_row.version != expected_old_parent_version:
                raise VersionConflictError(
                    f"Parent {current_parent_id} version mismatch: "
                    f"expected {expected_old_parent_version}, found {old_parent_row.version}."
                )
            old_children = list(old_parent_row.children_ids or [])
            if block_id_str in old_children:
                old_children.remove(block_id_str)
                old_parent_row.children_ids = old_children
                old_parent_row.version += 1

        # Prepare new parent children list and insert at requested index.
        updated_new_children = list(new_parent_row.children_ids or [])
        if block_id_str in updated_new_children:
            updated_new_children.remove(block_id_str)
        insertion_index = max(0, min(index, len(updated_new_children)))
        updated_new_children.insert(insertion_index, block_id_str)
        new_parent_row.children_ids = updated_new_children
        new_parent_row.version += 1

        block_row.parent_id = new_parent_row.id
        block_row.version += 1

    def _hydrate_subgraph(
        self,
        session: Session,
        root_row: DbBlock,
        depth: int | None,
        cache: dict[UUID, Block],
        *,
        include_trashed: bool,
    ) -> None:
        """Populate cache with blocks up to the requested depth."""
        if root_row.in_trash and not include_trashed:
            return

        block = self._to_model(root_row)
        cache[block.id] = block

        if depth is not None and depth == 0:
            return

        next_depth = None if depth is None else depth - 1

        children_ids: list[str] = list(root_row.children_ids or [])
        if not children_ids:
            return

        child_rows = (
            session.query(DbBlock)
            .filter(DbBlock.id.in_(children_ids))
            .all()
        )
        row_by_id = {row.id: row for row in child_rows}

        for child_id in children_ids:
            child_row = row_by_id.get(child_id)
            if child_row is None:
                continue
            if child_row.in_trash and not include_trashed:
                continue
            child_uuid = UUID(child_row.id)
            if child_uuid in cache:
                continue
            self._hydrate_subgraph(
                session,
                child_row,
                next_depth,
                cache,
                include_trashed=include_trashed,
            )

    def _hydrate_full_root(
        self,
        session: Session,
        root_row: DbBlock,
        include_trashed: bool,
    ) -> Block | None:
        query = session.query(DbBlock).filter(DbBlock.root_id == root_row.root_id)
        if not include_trashed:
            query = query.filter(DbBlock.in_trash.is_(False))
        rows = query.all()
        cache: dict[UUID, Block] = {}
        for row in rows:
            block = self._to_model(row)
            cache[block.id] = block
        wired_cache = self._wire_cache(cache)
        return wired_cache.get(UUID(root_row.id))

    def _wire_cache(self, cache: dict[UUID, Block]) -> dict[UUID, Block]:
        """Attach shared resolvers to a cached block subgraph."""
        if not cache:
            return {}

        wired_cache: dict[UUID, Block] = {}

        def resolve_one(block_id: UUID | None) -> Block | None:
            if block_id is None:
                return None
            block = wired_cache.get(block_id)
            if block is not None:
                return block
            return self.get_block(block_id, depth=0)

        def resolve_many(block_ids: Iterable[UUID]) -> list[Block]:
            resolved: list[Block] = []
            for block_id in block_ids:
                block = resolve_one(block_id)
                if block is not None:
                    resolved.append(block)
            return resolved

        for block in cache.values():
            wired_cache[block.id] = block

        for block_id, block in list(wired_cache.items()):
            wired_cache[block_id] = block.with_resolvers(
                resolve_one=resolve_one,
                resolve_many=resolve_many,
            )

        return wired_cache

    def _bulk_upsert_postgres(self, session: Session, payloads: list[dict[str, Any]]) -> None:
        if not payloads:
            return

        stmt = pg_insert(DbBlock).values(payloads)
        update_cols = {
            column.name: getattr(stmt.excluded, column.name)
            for column in DbBlock.__table__.columns
            if column.name != "id"
        }
        session.execute(
            stmt.on_conflict_do_update(index_elements=[DbBlock.id], set_=update_cols)
        )
        session.commit()

    def _collect_descendant_ids(self, session: Session, root_ids: Iterable[str]) -> set[str]:
        """Return every descendant id reachable from ``root_ids`` (including the roots)."""
        pending = list(root_ids)
        seen: set[str] = set()

        while pending:
            current_id = pending.pop()
            if current_id in seen:
                continue
            seen.add(current_id)
            row = session.get(DbBlock, current_id)
            if row is None:
                continue
            pending.extend(row.children_ids or [])

        return seen


    def _apply_filters(
        self,
        query,
        model,
        *,
        where: WhereClause | None = None,
        property_filter: FilterExpression | None = None,
    ):
        if where is not None:
            query = apply_structural_filters(query, model, where)
        if property_filter is not None:
            query = query.filter(build_filter_expression(model, property_filter))
        return query

    def _apply_related_filters(self, query, *, relation: str, filter_spec):
        if filter_spec is None:
            return query

        alias = aliased(DbBlock)
        if relation == "root":
            query = query.join(alias, DbBlock.root_id == alias.id)
        elif relation == "parent":
            query = query.join(alias, DbBlock.parent_id == alias.id)
        else:
            raise ValueError(f"Unsupported relation filter: {relation}")

        return self._apply_filters(
            query,
            alias,
            where=getattr(filter_spec, "where", None),
            property_filter=getattr(filter_spec, "property_filter", None),
        )

    def _with_resolvers(self, block: Block) -> Block:
        """Attach navigation resolvers to a block instance."""
        return block.with_resolvers(
            resolve_one=lambda _id: self._resolve_one(_id),
            resolve_many=lambda ids: self._resolve_many(ids),
        )

__all__ = [
    "BlockRepository",
    "BlockNotFoundError",
    "VersionConflictError",
    "InvalidChildrenError",
    "RepositoryError",
]


def _jsonable(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value
