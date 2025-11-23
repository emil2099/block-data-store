"""Factory helpers for constructing the document store façade."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from block_data_store.repositories.block_repository import BlockRepository
from block_data_store.repositories.relationship_repository import RelationshipRepository

from .document_store import DocumentStore


def create_document_store(session_factory: sessionmaker[Session]) -> DocumentStore:
    """Build a DocumentStore with the default repository implementation."""
    repository = BlockRepository(session_factory)
    relationship_repository = RelationshipRepository(session_factory)
    return DocumentStore(repository, relationship_repository)


__all__ = ["create_document_store"]
