"""SQLAlchemy-backed repository for Relationship models."""

from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import and_, or_, tuple_
from sqlalchemy.orm import Session, aliased, sessionmaker

from block_data_store.db.schema import DbBlock, DbRelationship
from block_data_store.models.relationship import Relationship
from block_data_store.repositories.block_repository import RepositoryError


class RelationshipNotFoundError(RepositoryError):
    """Raised when a relationship cannot be found."""


class RelationshipRepository:
    """Repository that persists and hydrates Relationship models."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def upsert_relationships(self, relationships: Sequence[Relationship]) -> None:
        """Batch insert or update relationships."""
        if not relationships:
            return

        payloads = [self._to_record(rel) for rel in relationships]

        with self._session_factory() as session:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            
            bind = session.get_bind()
            if bind.dialect.name == "postgresql":
                stmt = pg_insert(DbRelationship).values(payloads)
                # On conflict, update metadata and timestamps
                update_cols = {
                    "metadata": stmt.excluded.metadata,
                    "last_edited_time": stmt.excluded.last_edited_time,
                    "last_edited_by": stmt.excluded.last_edited_by,
                    "version": DbRelationship.version + 1
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=["source_block_id", "target_block_id", "rel_type"],
                    set_=update_cols
                )
            else:
                # SQLite
                stmt = sqlite_insert(DbRelationship).values(payloads)
                update_cols = {
                    "metadata": stmt.excluded.metadata,
                    "last_edited_time": stmt.excluded.last_edited_time,
                    "last_edited_by": stmt.excluded.last_edited_by,
                    "version": DbRelationship.version + 1
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=["source_block_id", "target_block_id", "rel_type"],
                    set_=update_cols
                )
                
            session.execute(stmt)
            session.commit()

    def delete_relationships(
        self,
        keys: Sequence[tuple[UUID, UUID, str]],
    ) -> bool:
        """Batch delete relationships by (source, target, type) keys.
        
        Returns True if any were deleted.
        """
        if not keys:
            return False

        with self._session_factory() as session:
            # Construct composite IN clause
            # tuple_ is imported
            
            tuple_keys = [(str(s), str(t), r) for s, t, r in keys]
            
            result = (
                session.query(DbRelationship)
                .filter(
                    tuple_(
                        DbRelationship.source_block_id, 
                        DbRelationship.target_block_id, 
                        DbRelationship.rel_type
                    ).in_(tuple_keys)
                )
                .delete(synchronize_session=False)
            )
            session.commit()
            return result > 0

    def get_relationships(
        self,
        block_id: UUID,
        direction: str = "all",  # 'all', 'outgoing', 'incoming'
        include_trashed: bool = False,
    ) -> list[Relationship]:
        """Get relationships for a block, optionally filtering by direction and trash status."""
        with self._session_factory() as session:
            query = session.query(DbRelationship)

            # Direction filter
            b_id = str(block_id)
            if direction == "outgoing":
                query = query.filter(DbRelationship.source_block_id == b_id)
            elif direction == "incoming":
                query = query.filter(DbRelationship.target_block_id == b_id)
            else:  # all
                query = query.filter(
                    or_(
                        DbRelationship.source_block_id == b_id,
                        DbRelationship.target_block_id == b_id,
                    )
                )

            # Trash filter (visibility)
            if not include_trashed:
                # Join with DbBlock for source and target to check in_trash
                SourceBlock = aliased(DbBlock)
                TargetBlock = aliased(DbBlock)

                query = (
                    query.join(SourceBlock, DbRelationship.source_block_id == SourceBlock.id)
                    .join(TargetBlock, DbRelationship.target_block_id == TargetBlock.id)
                    .filter(
                        SourceBlock.in_trash.is_(False),
                        TargetBlock.in_trash.is_(False),
                    )
                )

            rows = query.all()
            return [self._to_model(row) for row in rows]

    @staticmethod
    def _to_model(record: DbRelationship) -> Relationship:
        return Relationship(
            id=record.id,
            workspace_id=record.workspace_id,
            source_block_id=record.source_block_id,
            target_block_id=record.target_block_id,
            rel_type=record.rel_type,
            metadata=record.metadata_json or {},
            version=record.version,
            created_time=record.created_time,
            last_edited_time=record.last_edited_time,
            created_by=record.created_by,
            last_edited_by=record.last_edited_by,
        )

    @staticmethod
    def _to_record(rel: Relationship) -> dict[str, Any]:
        return {
            "id": rel.id,
            "workspace_id": rel.workspace_id,
            "source_block_id": rel.source_block_id,
            "target_block_id": rel.target_block_id,
            "rel_type": rel.rel_type,
            "metadata_json": rel.metadata,
            "version": rel.version,
            "created_time": rel.created_time,
            "last_edited_time": rel.last_edited_time,
            "created_by": rel.created_by,
            "last_edited_by": rel.last_edited_by,
        }
